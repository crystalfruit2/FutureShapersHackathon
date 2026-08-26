"""Live bridge -> cloud. The gateway half of the multi-tenant story.

Design rules, in priority order:

  1. NEVER raise into the bridge. handle_line() is on the serial hot path; a
     Firestore 503 or a dead venue Wi-Fi must not cost us a single telemetry
     frame, let alone the demo. Everything here is queue-and-forget, and every
     upload is wrapped.
  2. NEVER write at 1 Hz. The node emits telemetry every second; mirroring
     that verbatim is 86 400 writes/farm/day, which blows the Firestore free
     tier before lunch. Telemetry is batched into rolled-up samples, and only
     an event or a mode change gets to jump the queue.
  3. Degrade, don't disappear. When the store is the offline LocalStore this
     module behaves identically — the console and the app still read a real
     fleet, just one that isn't shared between machines.
"""
from __future__ import annotations

import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone

from . import CFG, open_store
from .fleet import RiskModel, featurize, forecast

# wire (firmware/bridge flat keys) -> cloud schema
WIRE_MAP = {"nh3": "nh3", "t1": "temp", "hum": "hum", "gas": "gas",
            "water": "water", "food": "food"}

ROLLUP_SEC = 20.0        # one cloud sample per 20 s of live telemetry
FLUSH_SEC = 15.0         # how often the queue is drained to the store
WINDOW = 3               # rolled-up samples the risk MODEL looks back over
TREND = 6                # samples kept for trend fitting — a slope fitted to
                         # three noisy points is a coin flip, and forecast()
                         # is written against a 6-sample tail
PER_HOUR = 3600.0 / ROLLUP_SEC
PEAK_DECAY = 0.82        # per bucket; ~70 s half-life on the held peak


def _iso(dt=None):
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


class CloudSink:
    def __init__(self):
        self.farm_id = CFG.farm_id
        self.q: queue.Queue = queue.Queue(maxsize=2000)
        self.buf: list[dict] = []            # live samples inside the rollup
        self.window: deque = deque(maxlen=TREND)
        self.model: RiskModel | None = None
        self.started = False
        self._bucket_t = 0.0
        self._lock = threading.Lock()
        self.stats = {"uploaded": 0, "queued": 0, "dropped": 0, "errors": 0,
                      "last_ok": "", "last_error": "", "risk": 0.0, "risk_now": 0.0,
                      "drivers": [], "forecast": []}

    # ── called from the bridge's hot path ────────────────────────────────
    def on_telemetry(self, tel: dict, mode: str):
        try:
            s = {}
            for wk, ck in WIRE_MAP.items():
                if wk in tel:
                    s[ck] = round(float(tel[wk]["v"]), 1)
            if not s:
                return
            s["mode"] = mode
            now = time.time()
            self.buf.append(s)
            if self._bucket_t == 0.0:
                self._bucket_t = now
            if now - self._bucket_t >= ROLLUP_SEC:
                self._close_bucket()
        except Exception:
            pass                              # rule 1: never raise upstream

    def on_event(self, ev: dict):
        try:
            sev = ev.get("sev", "INFO")
            raw = ev.get("raw", "")
            parts = raw.split("|")
            self._enqueue(("event", {
                "ts": _iso(), "raw": raw, "sev": sev,
                "zone": parts[2] if raw.startswith("EVT|") and len(parts) > 2 else "ctrl",
                "type": parts[3] if raw.startswith("EVT|") and len(parts) > 3
                        else (parts[1] if len(parts) > 1 else raw),
                "source": "live-node"}))
            if sev in ("ALERT", "EMERG", "SEC"):
                self._close_bucket(force=True)   # incidents don't wait 20 s
        except Exception:
            pass

    def on_mode(self, mode: str):
        try:
            self._enqueue(("farm", {"mode": mode, "last_seen": _iso()}))
        except Exception:
            pass

    # ── rollup + live scoring ────────────────────────────────────────────
    def _close_bucket(self, force: bool = False):
        with self._lock:
            if not self.buf:
                return
            keys = [k for k in WIRE_MAP.values()]
            n = len(self.buf)
            s = {k: round(sum(b.get(k, 0.0) for b in self.buf) / n, 1)
                 for k in keys if any(k in b for b in self.buf)}
            s["ts"] = _iso()
            s["mode"] = self.buf[-1].get("mode", "DAY")
            s["n"] = n
            self.buf = []
            self._bucket_t = time.time()
        self.window.append(s)
        self._score(s)
        self._enqueue(("telemetry", s))

    def _score(self, latest: dict):
        """Live risk from the FLEET model — the whole point of the cloud."""
        if self.model is None or len(self.window) < WINDOW:
            return
        try:
            hour = int(time.strftime("%H"))
            x = featurize(list(self.window)[-WINDOW:], hour)
            # the model was fitted on hourly steps; live buckets are 20 s, so
            # the slope features are rescaled to per-hour before inference.
            # z-clipping inside predict() stops a 15-second gas ramp from
            # extrapolating to a physically meaningless log-odds.
            for j in (1, 3, 6):
                x[j] *= PER_HOUR
            risk = round(100 * self.model.predict(x), 1)
            self.stats["risk_now"] = risk

            # Peak-hold with decay, the way a real alarm annunciator behaves.
            # The fleet model reasons in HOURS; the stage scripts compress an
            # hour of barn physics into fifteen seconds, so the 60 s window
            # empties as fast as it fills and the raw score flickers between
            # 70% and 0% between polls. Holding the peak and bleeding it off
            # over ~70 s makes the number readable without inventing it —
            # risk_now always carries the instantaneous value alongside.
            decayed = round(self.stats["risk"] * PEAK_DECAY, 1)
            if risk >= decayed:
                self.stats["risk"] = risk
                self.stats["drivers"] = self.model.explain(x)
            else:
                self.stats["risk"] = decayed      # keep the peak's drivers
            # trend needs the full tail; below TREND samples we simply have
            # no basis for a forecast and say nothing rather than guess
            fc = forecast(list(self.window), hours_per_step=ROLLUP_SEC / 3600.0) \
                if len(self.window) >= TREND else []
            if fc or risk >= decayed:
                self.stats["forecast"] = fc
            self._enqueue(("farm", {
                "risk_pct": self.stats["risk"],
                "risk_drivers": self.stats["drivers"],
                "forecast": self.stats["forecast"],
                "live": {k: v for k, v in latest.items()
                         if k in WIRE_MAP.values()},
                "mode": latest.get("mode", "DAY"),
                "last_seen": latest["ts"], "online": True}))
        except Exception as e:
            self.stats["last_error"] = f"score: {e}"

    def _enqueue(self, item):
        try:
            self.q.put_nowait(item)
            self.stats["queued"] = self.q.qsize()
        except queue.Full:
            self.stats["dropped"] += 1        # newest data matters most

    # ── uploader thread ──────────────────────────────────────────────────
    def start(self):
        if self.started:
            return
        self.started = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _load_model(self, store):
        try:
            self.model = RiskModel.from_doc(store.get_doc("fleet/model"))
        except Exception as e:
            self.stats["last_error"] = f"model: {e}"

    def _loop(self):
        store = open_store()
        self._load_model(store)
        backoff = 1.0
        while True:
            time.sleep(FLUSH_SEC)
            try:
                self._close_bucket()
                items, writes, farm_patch = [], [], {}
                while True:
                    try:
                        items.append(self.q.get_nowait())
                    except queue.Empty:
                        break
                if not items:
                    continue
                for kind, data in items:
                    if kind == "telemetry":
                        did = data["ts"].replace(":", "").replace("-", "")
                        writes.append(
                            (f"farms/{self.farm_id}/telemetry/{did}", data))
                    elif kind == "event":
                        did = (data["ts"].replace(":", "").replace("-", "")
                               + f"-{len(writes):04d}")
                        writes.append(
                            (f"farms/{self.farm_id}/events/{did}", data))
                    elif kind == "farm":
                        farm_patch.update(data)   # last write of the batch wins
                if farm_patch:
                    farm_patch.setdefault("farm_id", self.farm_id)
                    farm_patch["is_live_node"] = True
                    writes.append((f"farms/{self.farm_id}", farm_patch))
                store.commit(writes)
                self.stats["uploaded"] += len(writes)
                self.stats["last_ok"] = _iso()
                self.stats["queued"] = self.q.qsize()
                backoff = 1.0
            except Exception as e:
                self.stats["errors"] += 1
                self.stats["last_error"] = str(e)[:160]
                time.sleep(min(30.0, backoff))
                backoff *= 2

    def snapshot(self) -> dict:
        return dict(self.stats, farm_id=self.farm_id,
                    window=len(self.window),
                    model=(self.model.meta if self.model else None))


SINK = CloudSink()
