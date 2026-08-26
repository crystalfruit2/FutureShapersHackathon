#!/usr/bin/env python3
"""
BioGuard (Ferma Strajer) - supervisory bridge + FIRMWARE TEST BENCH (laptop side).

Roles:
  1. Serial bridge: owns the USB link to the Arduino, rebroadcasts as SSE.
  2. Browser dashboard: floor plan, events, sim sliders, cyber demo (fallback UI).
  3. Firmware test bench (for Oleksandr): port picker, raw protocol console,
     conformance counters (unparsed lines flagged), scripted test sequences.
  4. Bridge for the Flutter app (same SSE + POST endpoints).
  5. /fire - PITCH DEMO ONLY: fire-station dispatch screen (ISU Banat, Lugoj).
     Read-only SSE consumer: pre-alert on AI forecasts, full incoming-call
     dispatch on FLAME_DETECTED / GAS_CRITICAL. Open it in a second window.

Run:
    python3 app.py --fake              # no hardware - UI dev / demo rehearsal
    python3 app.py                     # real firmware: pick the port in the UI
Open http://localhost:5001   (0.0.0.0 binding is default so the phone can join)

Deps:  pip install flask pyserial
"""
import argparse, glob, json, queue, random, threading, time
from collections import deque
from flask import Flask, Response, request

# ── cloud layer (optional) ───────────────────────────────────────────────
# The bridge is the farm GATEWAY: it mirrors what it sees into Firestore under
# a farm id so many farms land in one project. Import failure is survivable by
# construction — the demo path must not depend on the cloud existing.
try:
    from cloud.sink import SINK as CLOUD_SINK
    from cloud.console import bp as cloud_bp
    CLOUD_OK = True
except Exception as _e:                                   # noqa: BLE001
    CLOUD_OK = False
    _CLOUD_ERR = _e
    class _NoCloud:
        def on_telemetry(self, *a, **k): pass
        def on_event(self, *a, **k): pass
        def on_mode(self, *a, **k): pass
        def start(self): pass
        def snapshot(self): return {"error": str(_e)}
    CLOUD_SINK = _NoCloud()

SECRET = b"STRAJER26"          # must match SECRET in the firmware

def crc8(data: bytes, crc: int = 0) -> int:
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def mac_for(counter: int, action: str) -> int:
    return crc8(SECRET, crc8(f"{counter}|{action}".encode()))

LOG_TYPES = {1:"BOOT",2:"MODE",3:"GAS",4:"INTRUDER",5:"TAMPER",
             6:"PIN_FAIL",7:"LOCKDOWN",8:"CMD_REJECT",9:"DISARM"}
KNOWN_UP = ("EVT|","TEL|","STATE|","SEC|","ACK|","NAK|","LOG|","AI|")

# ── shared state ─────────────────────────────────────────────────────────
state = {"mode":"?", "tel":{}, "log":[]}
events = deque(maxlen=200)
raw_log = deque(maxlen=400)          # {"dir":"rx"/"tx","line","t","ok"}
counters = {"rx":0, "tx":0, "unparsed":0}
subscribers = []
cmd_counter = int(time.time()) % 100000
last_sent = {"counter":0, "action":""}
lock = threading.Lock()

# ── access control (bridge = the supervisory security layer) ─────────────
# Enforced HERE, not in the UIs: a greyed-out button is cosmetics, a 403 with
# a SEC event on the wire is a control. Applies to real firmware and fake.
PIN_CODE = "1324"                    # mirrors the panel keypad code 1-3-2-4
ROLE_RANK = {"viewer":0, "operator":1, "admin":2}
security = {"pin_fails":0, "lockdown":False}

def fw_sig(ver: str) -> int:
    return crc8(SECRET, crc8(ver.encode()))

def sec_event(line: str):
    handle_line(f"SEC|{line}")

def send_signed(action: str):
    """Sign and send one command to the device with the bridge's counter."""
    global cmd_counter
    with lock:
        cmd_counter += 1
        last_sent.update(counter=cmd_counter, action=action)
        c = cmd_counter
    send_raw(f"CMD|{c}|{mac_for(c, action)}|{action}")

def enter_lockdown(reason: str):
    if security["lockdown"]: return
    security["lockdown"] = True
    sec_event(f"LOCKDOWN|{reason}")
    if ser:
        # real device (Pi node): it forces fan ON / pump OFF and emits
        # its own EVT + STATE|LOCKDOWN back up this same channel
        send_signed("LOCKDOWN")
        return
    if fake_on:
        if fake["mode"] not in ("LOCKDOWN", "EMERGENCY"):
            fake["premode"] = fake["mode"]
        fake["mode"] = "LOCKDOWN"; fake["fan"] = 1; fake["spr"] = 0
    handle_line("EVT|0|ctrl|LOCKDOWN|3|ALERT")
    handle_line("STATE|LOCKDOWN")

def clear_lockdown():
    security["lockdown"] = False
    security["pin_fails"] = 0
    if ser:
        send_signed("UNLOCK")     # node restores its pre-lockdown mode
        return
    if fake_on and fake["mode"] == "LOCKDOWN":
        fake["mode"] = fake.get("premode", "DAY")
    sec_event("LOCKDOWN_CLEARED|ADMIN_PIN")
    handle_line(f"STATE|{fake['mode'] if fake_on else state['mode']}")

ser = None                # live pyserial handle
ser_port = None
ser_stop = threading.Event()
fake_on = False

def publish(msg: dict):
    for q in list(subscribers):
        try: q.put_nowait(msg)
        except queue.Full: pass

def now_t():
    return time.strftime("%H:%M:%S")

def push_raw(direction: str, line: str, ok: bool = True):
    rec = {"dir":direction, "line":line, "t":now_t(), "ok":ok}
    raw_log.append(rec)
    counters["rx" if direction=="rx" else "tx"] += 1
    if not ok: counters["unparsed"] += 1
    publish({"type":"raw", "raw":rec, "counters":counters})

def handle_line(line: str, from_serial=False):
    line = line.strip()
    if not line: return
    parsed = line.startswith(KNOWN_UP)
    if from_serial:
        push_raw("rx", line, ok=parsed)
    parts = line.split("|")
    if parts[0] == "TEL" and len(parts) > 1:
        tel = {}
        for kv in parts[1].split(","):
            if "=" not in kv: continue
            k, v = kv.split("=", 1)
            sim = v.endswith("s")
            if sim: v = v[:-1]
            try: tel[k] = {"v": float(v), "sim": sim, "age": time.time()}
            except ValueError: pass
        state["tel"] = tel
        publish({"type":"tel", "tel":tel})
        analyst.ingest(tel)          # Tier-2 perception layer (advisory only)
        CLOUD_SINK.on_telemetry(tel, state["mode"])   # Tier-3: fleet (fail-open)
    elif parts[0] == "STATE" and len(parts) > 1:
        state["mode"] = parts[1]
        publish({"type":"state", "mode":parts[1]})
        CLOUD_SINK.on_mode(parts[1])
    elif parts[0] in ("EVT","SEC","ACK","NAK","AI"):
        ev = {"raw":line, "t":now_t(),
              "sev": parts[5] if parts[0] in ("EVT","AI") and len(parts)>5 else
                     ("SEC" if parts[0]=="SEC" else "INFO")}
        events.append(ev)
        publish({"type":"event", "event":ev})
        CLOUD_SINK.on_event(ev)
    elif parts[0] == "LOG":
        # a garbled LOG fragment (common on Arduino port-open reset) must never
        # escape into reader_loop's catch-all and drop the serial link
        try:
            if parts[1] == "END":
                publish({"type":"log", "log":state["log"]}); state["log"] = []
            elif len(parts) >= 6:
                state["log"].append({"slot":int(parts[1]),
                    "what":LOG_TYPES.get(int(parts[2]) if parts[2].isdigit() else -1, parts[2]),
                    "val":parts[3], "min":parts[4], "chain":parts[5]})
        except (IndexError, ValueError):
            pass

def send_raw(s: str):
    push_raw("tx", s)
    if ser:
        try: ser.write((s + "\n").encode())
        except Exception as e:
            publish({"type":"serial", "connected":False, "port":ser_port, "detail":f"write failed: {e}"})
    elif fake_on:
        try:
            fake_rx(s)
        except (ValueError, KeyError, IndexError):
            # garbage from the raw-line box must be *rejected*, not a 500 —
            # same contract the real firmware promises for malformed input
            handle_line("SEC|CMD_REJECTED|MALFORMED")

# ── serial management (test-bench core) ──────────────────────────────────
pi_host = None                # set by --pi; offered in the port picker

def list_ports():
    ports = []
    if pi_host:
        ports.append({"device": f"socket://{pi_host}:7777",
                      "desc": "BioGuard Pi node (TCP)"})
    try:
        from serial.tools import list_ports as lp
        ports += [{"device":p.device, "desc":p.description} for p in lp.comports()]
    except Exception:
        ports += [{"device":d, "desc":""} for d in glob.glob("/dev/cu.usb*")]
    return ports

def reader_loop(port, baud):
    global ser, ser_port
    import serial
    try:
        # serial_for_url: normal /dev/... paths behave exactly like Serial(),
        # and socket://host:7777 reaches the Raspberry Pi node over TCP
        ser = serial.serial_for_url(port, baudrate=baud, timeout=1)
    except Exception as e:
        publish({"type":"serial", "connected":False, "port":port, "detail":str(e)})
        return
    ser_port = port
    ser_stop.clear()
    publish({"type":"serial", "connected":True, "port":port, "detail":"connected"})
    events.append({"raw":f"DASH|serial connected {port}", "t":now_t(), "sev":"INFO"})
    try:
        while not ser_stop.is_set():
            line = ser.readline().decode(errors="replace")
            if line: handle_line(line, from_serial=True)
    except Exception as e:
        publish({"type":"serial", "connected":False, "port":port, "detail":f"lost: {e}"})
    finally:
        try: ser.close()
        except Exception: pass
        ser = None
        ser_port = None
        publish({"type":"serial", "connected":False, "port":None, "detail":"disconnected"})

# ── scripted test sequences (run against real firmware OR fake) ──────────
def script_gas_ramp():
    for v in (200, 350, 500, 650, 800, 900):
        send_raw(f"SIM|gas={v}"); time.sleep(1.5)
    time.sleep(4)
    for v in (500, 300, 120):
        send_raw(f"SIM|gas={v}"); time.sleep(1.5)

def script_replay():
    global cmd_counter
    with lock:
        cmd_counter += 1
        c = cmd_counter
    send_raw(f"CMD|{c}|{mac_for(c,'FAN_ON')}|FAN_ON"); time.sleep(1.5)
    send_raw(f"CMD|{c}|{mac_for(c,'FAN_ON')}|FAN_ON")          # replay -> reject
    time.sleep(1.5)
    send_raw(f"CMD|{c+999}|0|FAN_OFF")                          # bad MAC -> reject

def script_night_intruder():
    global cmd_counter
    with lock:
        cmd_counter += 1
        c = cmd_counter
    send_raw(f"CMD|{c}|{mac_for(c,'ARM')}|ARM"); time.sleep(2)
    send_raw("SIM|mot=1"); time.sleep(3); send_raw("SIM|mot=0")

def script_flame():
    send_raw("SIM|flame=1"); time.sleep(5); send_raw("SIM|flame=0")

def script_slow_creep():
    """The AI money shot: a leak too slow for a fixed threshold to see coming.
    Gas walks 120 -> 720 over ~72 s. The reflex layer only fires at 700; the
    analyst forecasts the crossing ~60 s earlier."""
    v = 120
    while v < 720:
        send_raw(f"SIM|gas={v}"); v += 20; time.sleep(2.5)
    time.sleep(6)
    send_raw("SIM|gas=120")

def script_nh3_drift():
    """Slow drift the fixed threshold NEVER sees: NH3 creeps 8 -> 22 ppm and
    stops below the 25 ppm limit. Only the learned baseline catches it.
    Requires the baseline to be learned first (watch the AI panel)."""
    for v in range(8, 23):
        send_raw(f"SIM|nh3={v}"); time.sleep(4)
    time.sleep(30)          # plateau: threshold silent, PREDICT lapses, DRIFT holds
    send_raw("SIM|nh3=8")

def script_fw_signed():
    ver = "1.4"
    send_raw(f"FW|{ver}|{fw_sig(ver)}")

def script_fw_unsigned():
    send_raw("FW|6.6|13")            # attacker-built image: signature doesn't verify

SCRIPTS = {"gas_ramp":script_gas_ramp, "replay":script_replay,
           "night_intruder":script_night_intruder, "flame":script_flame,
           "slow_creep":script_slow_creep, "nh3_drift":script_nh3_drift,
           "fw_signed":script_fw_signed, "fw_unsigned":script_fw_unsigned}

# ── fake-data generator ──────────────────────────────────────────────────
fake = {"gas":120,"nh3":8,"flame":0,"t1":24,"t2":24,"hum":55,"water":72,"food":58,
        "mot":0,"snd":0,"tamp":0,"fan":0,"relay":1,"vent":0,"cfan":0,"spr":0,
        "light":1,"mode":"DAY","ctr":0, "sim":set(["nh3","flame"])}

def fake_rx(s: str):
    if s.startswith("SIM|"):
        k, v = s[4:].split("=");  fake[k] = float(v); fake["sim"].add(k)
    elif s.startswith("FW|"):
        # signed-update demo: device only flashes an image whose signature
        # verifies against the shared secret (same primitive as the CMD MAC)
        _, ver, sig = s.split("|")
        if int(sig) == fw_sig(ver):
            fake["fw"] = ver
            handle_line(f"EVT|0|ctrl|FW_VERIFIED|v{ver}|INFO")
        else:
            handle_line("SEC|FW_REJECTED|BAD_SIGNATURE")
        return
    elif s.startswith("CMD|"):
        _, ctr, mac, action = s.split("|")
        ctr = int(ctr)
        if ctr <= fake["ctr"]:
            handle_line("SEC|REPLAY_REJECTED|STALE_COUNTER"); return
        if int(mac) != mac_for(ctr, action):
            handle_line("SEC|CMD_REJECTED|BAD_MAC"); return
        fake["ctr"] = ctr
        if fake["mode"] == "LOCKDOWN" and action != "FAN_ON":
            # tamper lockdown: device itself refuses non-essential commands,
            # even ones with a valid MAC (raw-console bypass covered too)
            handle_line(f"SEC|CMD_REJECT|LOCKDOWN|{action}"); return
        handle_line(f"ACK|{ctr}")
        if action == "ARM": fake["mode"] = "NIGHT"
        elif action == "DISARM": fake["mode"] = "DAY"
        elif action == "FAN_ON": fake["fan"] = 1
        elif action == "FAN_OFF": fake["fan"] = 0
        elif action == "VENT": fake["vent"] ^= 1
        elif action == "CFAN_ON": fake["cfan"] = 1
        elif action == "CFAN_OFF": fake["cfan"] = 0
        elif action == "LIGHT_ON": fake["light"] = 1
        elif action == "LIGHT_OFF": fake["light"] = 0
        elif action == "SPRINKLER_ON": fake["spr"] = 1
        elif action == "SPRINKLER_OFF": fake["spr"] = 0
        elif action == "REFILL_WATER":
            fake["water"] = 100
            handle_line("EVT|0|hall|WATER_REFILLED|100|INFO")
        elif action == "REFILL_FOOD":
            fake["food"] = 100
            handle_line("EVT|0|hall|FOOD_REFILLED|100|INFO")
        elif action == "DUMPLOG":
            for i,(w,c) in enumerate([("BOOT","OK"),("MODE","OK"),("GAS","OK"),("CMD_REJECT","OK")]):
                state["log"].append({"slot":i,"what":w,"val":"0","min":str(i),"chain":c})
            publish({"type":"log","log":state["log"]}); state["log"] = []
        handle_line(f"STATE|{fake['mode']}")

def fake_loop():
    handle_line("STATE|DAY")
    while True:
        if ser:                       # real serial wins; fake sleeps
            time.sleep(1); continue
        f = fake
        if "gas" not in f["sim"]:
            # mean-reverting around ambient: a sealed pit doesn't wander to 500 on its own,
            # and a free random walk would let the analyst forecast a leak that isn't there
            f["gas"] = max(80, f["gas"] + (120 - f["gas"]) * 0.15 + random.uniform(-5, 5))
        # A fire heats the building. A flat 24 C during a flame event is what
        # made our own tier-2 analyst flag our own dispatch as "sensor fault or
        # spoofed input" -- the thermal channel is what corroborates the flame
        # pin, so it has to actually move.
        if f["flame"]:
            f["t1"] = min(64.0, float(f["t1"]) + random.uniform(1.2, 2.0))
        elif float(f["t1"]) > 25.5:
            f["t1"] = max(24.0, float(f["t1"]) - random.uniform(0.8, 1.4))
        else:
            f["t1"] = 24 + random.randint(-1, 1)
        f["t2"] = f["t1"] + random.choice([0, 0, 1])
        if f["gas"] >= 700 and f["mode"] != "EMERGENCY":
            f["premode"] = f["mode"]   # a night-armed farm stays armed after the episode
            f["mode"] = "EMERGENCY"; f["relay"] = 0; f["fan"] = 1; f["vent"] = 1
            handle_line(f"EVT|0|pit|GAS_CRITICAL|{int(f['gas'])}|EMERG")
            handle_line("STATE|EMERGENCY")
        if f["gas"] < 400 and not f["flame"] and f["mode"] == "EMERGENCY":
            f["mode"] = f.get("premode", "DAY"); f["relay"] = 1; f["spr"] = 0
            handle_line("EVT|0|pit|GAS_CLEARED|0|INFO"); handle_line(f"STATE|{f['mode']}")
        if f["flame"] and f["mode"] != "EMERGENCY":
            f["premode"] = f["mode"]
            f["mode"] = "EMERGENCY"; f["relay"] = 0; f["fan"] = 1; f["vent"] = 1; f["spr"] = 1
            handle_line("EVT|0|store|FLAME_DETECTED|1|EMERG"); handle_line("STATE|EMERGENCY")
        if f["nh3"] >= 25:
            f["fan"] = 1               # auto ventilation — mirrors the app's fake source
        if f["mot"] and f["mode"] == "NIGHT":
            handle_line("EVT|0|perim|INTRUDER|1|ALERT"); f["mot"] = 0
        tel = ",".join(f"{k}={int(f[k])}{'s' if k in f['sim'] else ''}"
                       for k in ("gas","nh3","flame","t1","t2","hum","water","food","light","mot","snd","tamp"))
        handle_line(f"TEL|{tel},fan={f['fan']},relay={f['relay']},vent={f['vent']},"
                    f"cfan={f['cfan']},spr={f['spr']},saved_pct={random.randint(60,70)}")
        time.sleep(1)

# ── Tier-2 analyst: prediction · baseline drift · plausibility ───────────
# Deterministic, offline, no external deps. Reads the same TEL stream the
# dashboard reads and emits AI| lines back into the event bus, so the web UI
# and the Flutter app both get it for free. It NEVER actuates: no CMD| is ever
# produced here. The reflex layer (firmware) owns the relay; this layer only
# tells the farmer what it thinks is about to happen.
#
#   AI|<kind>|<zone>|<what>|<message>|<sev>      kind: PREDICT DRIFT PLAUS STUCK
#
# sev stays in the firmware's vocabulary (INFO/WARN/ALERT/EMERG) so both UIs
# colour it with the rules they already have.

# channel -> (zone, label, unit, rising critical limit or None)
AI_CHANNELS = {
    "gas":   ("pit",   "CH4",      "",      700.0),
    "nh3":   ("hall",  "NH3",      " ppm",  25.0),
    "t1":    ("hall",  "temp",     "°",     32.0),
    "t2":    ("hall",  "temp 2",   "°",     32.0),
    "hum":   ("hall",  "humidity", "%",     None),
    "water": ("store", "water",    "",      None),
}

def fmt_eta(sec: float) -> str:
    sec = int(sec)
    return f"{sec}s" if sec < 60 else f"{sec//60}m{sec%60:02d}s"

class Analyst:
    ALPHA_V  = 0.35     # value smoothing (samples arrive ~1 Hz)
    ALPHA_S  = 0.25     # slope smoothing
    ETA_WARN = 300.0    # s — start forecasting once critical is <5 min out
    ETA_ALERT= 90.0     # s — escalate inside 90 s
    Z_WARN   = 4.0      # sigma off the learned baseline
    Z_HOLD   = 3        # consecutive samples before drift is called
    STUCK_N  = 25       # identical samples (while the farm moves) => frozen
    REPEAT_S = 20.0     # don't repeat the same finding faster than this
    MIN_N    = 8        # samples before the EWMA slope is trusted

    def __init__(self, baseline_secs: float = 45.0):
        self.baseline_secs = baseline_secs
        self.findings = deque(maxlen=8)
        self.reset()

    def reset(self):
        self.ch = {}
        self.t0 = None
        self.last_t = None
        self.learned_at = None
        self.learning = True
        self.fan_since = None
        self._emitted = {}

    def relearn(self):
        """Re-learn what 'normal' looks like from now (venue calibration)."""
        self.reset()
        self.findings.append({"t": now_t(), "kind": "BASELINE", "sev": "INFO",
                              "msg": f"re-learning baseline for {int(self.baseline_secs)}s"})

    # ── per-channel state ────────────────────────────────────────────────
    def _st(self, k):
        if k not in self.ch:
            self.ch[k] = {"s": None, "slope": 0.0, "last": None, "n": 0,
                          "stuck": 0, "z_hold": 0, "rise": 0, "lively": False,
                          "mu": None, "sd": None, "bn": 0, "bsum": 0.0, "bsq": 0.0}
        return self.ch[k]

    def _emit_ok(self, key, sev):
        """Dedupe: same finding at most every REPEAT_S, unless it escalated."""
        prev = self._emitted.get(key)
        t = time.time()
        if prev and t - prev[0] < self.REPEAT_S and prev[1] == sev:
            return False
        self._emitted[key] = (t, sev)
        return True

    # ── main entry, called from handle_line's TEL branch ─────────────────
    def ingest(self, tel: dict):
        t = time.time()
        dt = 1.0 if self.last_t is None else min(5.0, max(0.2, t - self.last_t))
        self.last_t = t
        if self.t0 is None:
            self.t0 = t
        emerg = state.get("mode") == "EMERGENCY"
        if self.learning and (t - self.t0 >= self.baseline_secs) and not emerg:
            self._freeze_baseline()

        moved = False
        for k in AI_CHANNELS:
            if k in tel and self._st(k)["last"] is not None:
                if tel[k]["v"] != self._st(k)["last"]:
                    moved = True

        out = []
        for k, (zone, label, unit, limit) in AI_CHANNELS.items():
            if k not in tel:
                continue
            v = tel[k]["v"]
            st = self._st(k)
            # EWMA value + slope (per second)
            if st["s"] is None:
                st["s"] = v
            else:
                prev = st["s"]
                st["s"] += self.ALPHA_V * (v - st["s"])
                st["slope"] += self.ALPHA_S * (((st["s"] - prev) / dt) - st["slope"])
            st["n"] += 1
            st["rise"] = st["rise"] + 1 if st["slope"] > 0 else 0
            # frozen-channel counter only advances while the rest of the farm moves
            # a slider-pinned SIM channel is *supposed* to sit still — only a real
            # (or fake-generated) channel going flat means a dead/replayed probe
            st["stuck"] = st["stuck"] + 1 if (moved and st["last"] == v
                                              and not tel[k].get("sim")) else 0
            st["last"] = v
            if self.learning and not emerg:
                st["bn"] += 1; st["bsum"] += v; st["bsq"] += v * v

            if not emerg:
                out += self._predict(k, st, zone, label, unit, limit)
                out += self._drift(k, st, zone, label, unit)
            out += self._stuck(k, st, zone, label, unit)

        out += self._plausibility(tel)

        for kind, zone, what, msg, sev in out:
            self.findings.append({"t": now_t(), "kind": kind, "sev": sev, "msg": msg})
            handle_line(f"AI|{kind}|{zone}|{what}|{msg}|{sev}")
        publish({"type": "ai", "ai": self.snapshot()})

    def _freeze_baseline(self):
        for k, st in self.ch.items():
            if st["bn"] < 5:
                continue
            mu = st["bsum"] / st["bn"]
            var = max(0.0, st["bsq"] / st["bn"] - mu * mu)
            raw_sd = var ** 0.5
            # a probe that never moved while we watched is *supposed* to sit still —
            # only a normally-lively one going silent means a dead probe
            st["lively"] = raw_sd > 0.5
            # floor sigma: a perfectly quiet channel must not yield infinite z
            st["mu"], st["sd"] = mu, max(raw_sd, 1.0, abs(mu) * 0.02)
        self.learning = False
        self.learned_at = now_t()
        self.findings.append({"t": now_t(), "kind": "BASELINE", "sev": "INFO",
                              "msg": f"baseline learned from {int(self.baseline_secs)}s of normal operation"})
        handle_line(f"AI|BASELINE|farm|LEARNED|normal operation profiled over {int(self.baseline_secs)}s|INFO")

    # ── detector 1: rate of rise -> time to threshold ────────────────────
    def _predict(self, k, st, zone, label, unit, limit):
        if limit is None or st["n"] < self.MIN_N or st["s"] >= limit:
            return []
        per_min = st["slope"] * 60.0
        if per_min < max(1.0, 0.02 * limit):        # floor: ignore trivial slopes
            return []
        # a forecast needs a *sustained* climb, not one noisy sample
        if st["rise"] < (5 if st["mu"] is not None else 10):
            return []
        # ...and the channel must have left its own learned noise band, or jitter
        # on a quiet probe would forecast a crossing that never comes
        if st["mu"] is not None and (st["s"] - st["mu"]) < 2.0 * st["sd"]:
            return []
        eta = (limit - st["s"]) / st["slope"]
        if eta <= 0 or eta > self.ETA_WARN:
            return []
        sev = "ALERT" if eta <= self.ETA_ALERT else "WARN"
        msg = (f"{label} rising {per_min:+.0f}{unit}/min → critical "
               f"({limit:.0f}{unit}) in {fmt_eta(eta)}")
        return [("PREDICT", zone, k.upper(), msg, sev)] if self._emit_ok(("PREDICT", k), sev) else []

    # ── detector 2: z-score vs frozen baseline (slow drift) ──────────────
    def _drift(self, k, st, zone, label, unit):
        if st["mu"] is None:
            return []
        p = self._emitted.get(("PREDICT", k))
        if p and time.time() - p[0] < self.REPEAT_S:
            return []
        z = (st["s"] - st["mu"]) / st["sd"]
        st["z_hold"] = st["z_hold"] + 1 if abs(z) >= self.Z_WARN else 0
        if st["z_hold"] < self.Z_HOLD:
            return []
        lim = AI_CHANNELS[k][3]
        tail = ("still under the fixed limit, but not normal"
                if lim is not None and st["s"] < lim else "off its learned normal")
        msg = (f"{label} drifted {st['mu']:.0f}{unit} → {st['s']:.0f}{unit} "
               f"({z:+.1f}σ off the baseline learned at {self.learned_at}) — {tail}")
        sev = "WARN"
        return [("DRIFT", zone, k.upper(), msg, sev)] if self._emit_ok(("DRIFT", k), sev) else []

    # ── detector 3a: frozen channel (dead probe or replayed telemetry) ───
    def _stuck(self, k, st, zone, label, unit):
        if st["stuck"] < self.STUCK_N or not st["lively"]:
            return []
        msg = (f"{label} frozen at {st['last']:.0f}{unit} for {st['stuck']}s while the rest "
               f"of the farm moves — disconnected probe or replayed telemetry")
        return [("STUCK", zone, k.upper(), msg, "WARN")] if self._emit_ok(("STUCK", k), "WARN") else []

    # ── detector 3b: cross-sensor plausibility ───────────────────────────
    def _plausibility(self, tel):
        out = []
        g = lambda k: tel[k]["v"] if k in tel else None
        t1, t2, flame, fan = g("t1"), g("t2"), g("flame"), g("fan")

        # fire asserted with no thermal signature => fault or spoofed input
        st1 = self.ch.get("t1", {})
        if flame and flame >= 1 and t1 is not None and st1.get("mu") is not None:
            rise = t1 - st1["mu"]
            if rise < 1.5 and self._emit_ok(("PLAUS", "flame"), "WARN"):
                out.append(("PLAUS", "store", "FLAME_IMPLAUSIBLE",
                            f"flame asserted but hall temp is flat at {t1:.0f}° "
                            f"({rise:+.1f}° vs baseline) — sensor fault or spoofed input, "
                            f"treating as suspect", "WARN"))

        # two probes in the same room disagreeing => one of them is lying
        if t1 is not None and t2 is not None and abs(t1 - t2) >= 6:
            if self._emit_ok(("PLAUS", "twin"), "WARN"):
                out.append(("PLAUS", "hall", "PROBE_DISAGREE",
                            f"hall temp probes disagree by {abs(t1-t2):.0f}° "
                            f"({t1:.0f}° vs {t2:.0f}°) — one probe is faulty", "WARN"))

        # mitigation running but the channel is not responding
        now = time.time()
        self.fan_since = (self.fan_since or now) if fan else None
        if self.fan_since and now - self.fan_since >= 30:
            for k in ("gas", "nh3"):
                lim = AI_CHANNELS[k][3]
                st = self.ch.get(k)
                if not st or st["s"] is None or st["s"] < 0.6 * lim:
                    continue
                if st["slope"] * 60 >= -0.5 and self._emit_ok(("PLAUS", k), "ALERT"):
                    out.append(("PLAUS", AI_CHANNELS[k][0], "VENT_INEFFECTIVE",
                                f"extraction has run {int(now-self.fan_since)}s and "
                                f"{AI_CHANNELS[k][1]} is still {st['slope']*60:+.0f}/min — "
                                f"check the fan belt or the inlet", "ALERT"))
        return out

    # ── snapshot for the live UI panel ───────────────────────────────────
    def snapshot(self):
        chans = []
        for k, (zone, label, unit, limit) in AI_CHANNELS.items():
            st = self.ch.get(k)
            if not st or st["s"] is None:
                continue
            per_min = st["slope"] * 60.0
            eta = None
            if limit and st["slope"] > 0 and st["s"] < limit and st["n"] >= self.MIN_N:
                e = (limit - st["s"]) / st["slope"]
                if 0 < e <= 3600:
                    eta = e
            z = (st["s"] - st["mu"]) / st["sd"] if st["mu"] is not None else None
            if st["stuck"] >= self.STUCK_N:      stt = "stuck"
            elif eta is not None and eta <= self.ETA_ALERT: stt = "alert"
            elif eta is not None and eta <= self.ETA_WARN:  stt = "predict"
            elif z is not None and abs(z) >= self.Z_WARN:   stt = "drift"
            else: stt = "ok"
            chans.append({"k": k, "label": label, "zone": zone, "unit": unit,
                          "v": round(st["s"], 1), "per_min": round(per_min, 1),
                          "eta": None if eta is None else fmt_eta(eta),
                          "z": None if z is None else round(z, 1),
                          "limit": limit, "state": stt})
        prog = 0.0
        if self.learning and self.t0:
            prog = min(1.0, (time.time() - self.t0) / self.baseline_secs)
        return {"learning": self.learning, "learned_at": self.learned_at,
                "progress": round(prog, 2), "baseline_secs": int(self.baseline_secs),
                "channels": chans, "findings": list(self.findings)}

analyst = Analyst()

# ── flask ────────────────────────────────────────────────────────────────
app = Flask(__name__)

if CLOUD_OK:
    app.register_blueprint(cloud_bp)      # /cloud + /cloud/api/*
    CLOUD_SINK.start()
else:
    print(f"[cloud] disabled: {_CLOUD_ERR}")

@app.route("/stream")
def stream():
    q = queue.Queue(maxsize=200)
    subscribers.append(q)
    def gen():
        q.put({"type":"hello",
               "state":{"mode":state["mode"], "tel":state["tel"]},
               "events":list(events)[-30:], "raws":list(raw_log)[-100:],
               "counters":counters, "ai":analyst.snapshot(),
               "serial":{"connected":ser is not None, "port":ser_port}})
        try:
            while True:
                yield f"data: {json.dumps(q.get())}\n\n"
        finally:
            subscribers.remove(q)
    return Response(gen(), mimetype="text/event-stream")

@app.route("/ports")
def ports():
    return {"ports": list_ports(), "connected": ser is not None, "port": ser_port}

@app.route("/connect", methods=["POST"])
def connect():
    port = request.json["port"]
    if ser: ser_stop.set(); time.sleep(1.2)
    threading.Thread(target=reader_loop, args=(port, 115200), daemon=True).start()
    return {"ok": True}

@app.route("/disconnect", methods=["POST"])
def disconnect():
    ser_stop.set()
    return {"ok": True}

@app.route("/raw", methods=["POST"])
def raw():
    send_raw(request.json["line"].strip())
    return {"ok": True}

script_busy = {"name": None}   # two interleaved scripts fight over SIM|gas

def _run_script(name):
    try:
        SCRIPTS[name]()
    finally:
        script_busy["name"] = None

@app.route("/script", methods=["POST"])
def script():
    name = request.json["name"]
    if name not in SCRIPTS: return {"ok": False}, 404
    if name.startswith("fw_") and request.json.get("role", "admin") != "admin":
        sec_event(f"CMD_REJECTED|ADMIN_ONLY|FW_UPDATE")
        return {"ok": False, "err": "firmware updates need admin"}, 403
    if script_busy["name"]:
        events.append({"raw":f"DASH|'{script_busy['name']}' still running — wait for it to finish",
                       "t":now_t(), "sev":"INFO"})
        publish({"type":"event","event":events[-1]})
        return {"ok": False, "err": "script running"}, 409
    script_busy["name"] = name
    events.append({"raw":f"DASH|test sequence: {name}", "t":now_t(), "sev":"INFO"})
    publish({"type":"event","event":events[-1]})
    threading.Thread(target=_run_script, args=(name,), daemon=True).start()
    return {"ok": True}

@app.route("/cmd", methods=["POST"])
def cmd():
    global cmd_counter
    d = request.json
    action = d["action"]
    role = d.get("role", "admin")        # legacy clients keep full access; the UIs always send a role
    pin = str(d.get("pin", "") or "")
    rank = ROLE_RANK.get(role, 0)
    critical = state["mode"] in ("EMERGENCY", "LOCKDOWN")

    if security["lockdown"] and action != "UNLOCK":
        sec_event(f"CMD_REJECTED|LOCKDOWN_ACTIVE|{action}")
        return {"ok": False, "err": "lockdown: only admin UNLOCK accepted"}, 403
    if rank < 1:
        sec_event(f"CMD_REJECTED|ROLE_VIEWER|{action}")
        return {"ok": False, "err": "viewer role cannot send commands"}, 403
    if action == "UNLOCK" and rank < 2:
        sec_event(f"CMD_REJECTED|ADMIN_ONLY|{action}")
        return {"ok": False, "err": "UNLOCK needs admin"}, 403
    if action.endswith("_OFF") and critical and rank < 2:
        # an operator may never de-energise safety actuators mid-incident
        sec_event(f"CMD_REJECTED|OFF_IN_{state['mode']}|{action}")
        return {"ok": False, "err": f"{action} needs admin while {state['mode']}"}, 403

    needs_pin = action in ("DISARM", "UNLOCK") or (action.endswith("_OFF") and critical)
    if needs_pin:
        if pin != PIN_CODE:
            security["pin_fails"] += 1
            sec_event(f"PIN_FAIL|ATTEMPT_{security['pin_fails']}|{action}")
            if security["pin_fails"] >= 3:
                enter_lockdown("REPEATED_PIN_FAILURES")
            return {"ok": False, "err": "wrong PIN"}, 403
        security["pin_fails"] = 0

    if action == "UNLOCK":
        clear_lockdown()
        return {"ok": True}
    with lock:
        cmd_counter += 1
        last_sent.update(counter=cmd_counter, action=action)
        send_raw(f"CMD|{cmd_counter}|{mac_for(cmd_counter, action)}|{action}")
    return {"ok": True}

@app.route("/attack", methods=["POST"])
def attack():
    with lock:
        if not last_sent["counter"]:
            # nothing captured yet — forging counter 1 would make the "attack"
            # pass the replay check and actually execute (the exact anti-demo)
            events.append({"raw":"DASH|replay attack needs a captured command — send one first",
                           "t":now_t(), "sev":"INFO"})
            publish({"type":"event","event":events[-1]})
            return {"ok": False, "err": "send a command first"}
        c, a = last_sent["counter"], last_sent["action"]
        send_raw(f"CMD|{c}|{mac_for(c, a)}|{a}")
    return {"ok": True}

@app.route("/ai/relearn", methods=["POST"])
def ai_relearn():
    """Re-profile what 'normal' looks like in THIS room. Venue calibration."""
    analyst.relearn()
    publish({"type":"ai", "ai":analyst.snapshot()})
    return {"ok": True}

@app.route("/sim", methods=["POST"])
def sim():
    d = request.json
    send_raw(f"SIM|{d['name']}={int(float(d['value']))}")
    return {"ok": True}

@app.route("/")
def index():
    return PAGE

@app.route("/fire")
def fire():
    return FIRE_PAGE

# BioGuard web app (flutter build web), served same-origin at /app/
import os
from flask import send_from_directory
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "flutter_app", "build", "web")

@app.route("/app/")
@app.route("/app/<path:path>")
def flutter_web(path="index.html"):
    return send_from_directory(WEB_DIR, path)

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioGuard — Bridge & Test Bench</title>
<style>
 /* Industrial control-room skin (ISA-101-flavored): status colors mean STATE
    and nothing else; sans-serif for chrome, monospace only for wire data. */
 :root{--bg:#0B0E12;--card:#151A21;--inset:#0A0D11;--line:#28313D;--edge:#33404F;
       --tx:#F2F6FA;--dim:#95A1AF;--ok:#35C46F;--warn:#F0A72E;--alert:#FF5449;
       --sim:#B18CFF;--acc:#41A8FF;
       --sans:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
       --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--tx);padding:14px 16px;
   font-family:var(--sans);font-size:13.5px}
 #topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;
   flex-wrap:wrap;padding:2px 2px 12px;border-bottom:1px solid var(--line)}
 .brand{display:flex;align-items:center;gap:11px}
 .brand-tick{width:4px;height:36px;background:var(--acc);border-radius:2px}
 .brand-name{font-weight:800;font-size:19px;line-height:1;letter-spacing:.14em}
 .brand-sub{font-size:11.5px;color:var(--dim);margin-top:4px;letter-spacing:.02em}
 .topbar-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
 .navlink{color:var(--alert);font-weight:700;font-size:11px;letter-spacing:.08em;
   text-decoration:none;border:1px solid var(--alert);border-radius:4px;padding:6px 11px}
 .navlink:hover{background:#FF54491A}
 .dim{color:var(--dim);font-size:12px}
 .card>.dim:first-child{font-weight:700;font-size:10.5px;letter-spacing:.1em;
   text-transform:uppercase;color:var(--dim)}
 .row{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;flex:1;min-width:300px}
 #mode{display:block;text-align:center;font-weight:800;font-size:23px;letter-spacing:.13em;
   padding:15px 10px;border-radius:6px;border:1px solid var(--line)}
 .DAY{background:#123457;color:#8FC7FF;border-color:#1F5FA0!important}
 .NIGHT{background:#291F50;color:#C9B8FF;border-color:#4A3A8C!important}
 .EMERGENCY{background:#571512;color:#FFB4AE;border-color:var(--alert)!important;animation:bl 1s infinite;
   background-image:repeating-linear-gradient(-45deg,transparent 0 12px,#FF544918 12px 24px)}
 .LOCKDOWN{background:#453104;color:#FFD98A;border-color:var(--warn)!important;
   background-image:repeating-linear-gradient(-45deg,transparent 0 12px,#F0A72E1C 12px 24px)}
 @keyframes bl{50%{opacity:.4}}
 .zones{display:grid;grid-template-columns:1fr 1fr;gap:9px}
 .zone{background:var(--inset);border:1px solid var(--line);border-left:3px solid var(--edge);
   border-radius:6px;padding:10px 12px;min-height:84px}
 .zone h3{margin:0 0 7px;font-size:10.5px;font-weight:700;letter-spacing:.09em;color:var(--dim)}
 .zone.warn{border-left-color:var(--warn)}
 .zone.alert{border-left-color:var(--alert);animation:bl 1s infinite}
 .v{font-family:var(--mono);font-size:13px;line-height:1.65;font-variant-numeric:tabular-nums}
 .simtag{color:var(--sim);font-size:9.5px;font-family:var(--sans);font-weight:700;
   border:1px solid var(--sim);border-radius:3px;padding:0 4px;margin-left:4px;letter-spacing:.05em}
 button{background:#1C242E;color:var(--tx);border:1px solid var(--edge);border-radius:6px;
   padding:8px 13px;cursor:pointer;font-family:var(--sans);font-weight:600;font-size:12px;
   letter-spacing:.02em;margin:2px}
 button:hover{background:#26303C;border-color:#4A5A6D}
 button:active{transform:translateY(1px)}
 button.red{border-color:#7A2B27;color:#FF8A82} button.red:hover{border-color:var(--alert);background:#2A1210}
 button.acc{border-color:#1F5FA0;color:#8FC7FF} button.acc:hover{border-color:var(--acc);background:#0F2237}
 select,input[type=text]{background:var(--inset);color:var(--tx);border:1px solid var(--edge);
   border-radius:6px;padding:8px 10px;font-family:var(--mono);font-size:12.5px}
 #log{height:200px;overflow-y:auto;font-family:var(--mono);font-size:11.5px;line-height:1.6}
 #console{height:260px;overflow-y:auto;font-family:var(--mono);font-size:11.5px;line-height:1.5;
   background:var(--inset);border:1px solid var(--line);border-radius:6px;padding:9px;margin-top:8px}
 .rx{color:#7EE787}.tx{color:#79C0FF}.bad{color:var(--alert);font-weight:bold}
 .EMERG{color:var(--alert);font-weight:bold}.ALERT{color:var(--alert)}
 .WARN{color:var(--warn)}.SEC{color:var(--sim);font-weight:bold}.INFO{color:var(--dim)}
 input[type=range]{width:100%;accent-color:var(--acc)}
 .sl{margin:9px 0} .sl label{font-size:11.5px;color:var(--dim);font-weight:600;letter-spacing:.03em}
 table{width:100%;font-family:var(--mono);font-size:11.5px;border-collapse:collapse;
   font-variant-numeric:tabular-nums}
 td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}
 th{font-family:var(--sans);font-size:10px;font-weight:700;letter-spacing:.08em;
   text-transform:uppercase;color:var(--dim)}
 .OK{color:var(--ok)}.BROKEN{color:var(--alert);font-weight:bold}
 #energy{font-family:var(--mono);font-size:30px;color:var(--ok);font-weight:700}
 #banner{display:none;position:fixed;inset:0 0 auto 0;z-index:9;padding:17px;text-align:center;
   font-weight:800;font-size:20px;letter-spacing:.05em;cursor:pointer;
   border-bottom:4px solid #0006}
 #banner.EMERG{display:block;background:#C6362C;color:#fff;animation:bl 1s infinite}
 #banner.ALERT{display:block;background:#C98A1B;color:#140D00}
 #banner.SEC{display:block;background:#6D4FC4;color:#fff}
 #banner.AIB{display:block;background:#1F6FB8;color:#EAF5FF}
 .noenter{color:#FF8A82;font-weight:700;font-size:13px;font-family:var(--sans);
   border:1px dashed var(--alert);border-radius:5px;padding:3px 8px;display:inline-block;margin-top:5px}
 .pill{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:3px 9px;
   font-family:var(--mono);font-size:11px}
 .pill.on{border-color:#1E5C38;color:#5FD68F;background:#0D2417}
 .pill.off{border-color:#6B4E12;color:#F0C36A;background:#241A05}
 .aitag{color:var(--acc);border:1px solid #1F5FA0;border-radius:3px;padding:0 5px;
   font-size:9.5px;font-family:var(--sans);font-weight:700;letter-spacing:.05em}
 tr.ai-alert td{color:var(--alert)} tr.ai-predict td{color:var(--warn)}
 tr.ai-drift td,tr.ai-stuck td{color:var(--sim)}
</style></head><body>
<div id="banner" onclick="this.className=''"></div>
<header id="topbar">
 <div class="brand"><span class="brand-tick"></span>
  <div>
   <div class="brand-name">BIO GUARD</div>
   <div class="brand-sub">Ferma Străjer — supervisory bridge &amp; firmware test bench</div>
  </div>
 </div>
 <div class="topbar-right">
  <span class="dim" id="stats" style="font-family:var(--mono);font-size:11px"></span>
  <span id="serialpill" class="pill off">serial: none</span>
  <a href="/fire" target="_blank" class="navlink">112 DISPATCH</a>
 </div>
</header>

<div class="row">
 <div class="card" style="flex:2">
  <div class="dim">ENGINEER — FIRMWARE TEST BENCH</div>
  <div style="margin:8px 0">
   <select id="ports" style="min-width:260px"></select>
   <button onclick="loadPorts()">refresh</button>
   <button class="acc" onclick="connectSer()">CONNECT</button>
   <button onclick="fetch('/disconnect',{method:'POST',headers:H})">disconnect</button>
  </div>
  <div class="dim">Test sequences (work on real firmware AND fake mode):</div>
  <div style="margin:6px 0">
   <button onclick="script('gas_ramp')">GAS RAMP 200→900→clear</button>
   <button onclick="script('replay')">CMD + REPLAY + BAD MAC</button>
   <button onclick="script('night_intruder')">ARM + INTRUDER</button>
   <button onclick="script('flame')">FLAME 5s</button><br>
   <button class="acc" onclick="script('slow_creep')">AI · SLOW GAS CREEP (predicted ~60s early)</button>
   <button class="acc" onclick="script('nh3_drift')">AI · NH3 DRIFT (never crosses the limit)</button>
   <button onclick="cmd('DUMPLOG')">AUDIT DUMP</button><br>
   <button class="acc" onclick="script('fw_signed')">FW UPDATE v1.4 (signed)</button>
   <button class="red" onclick="script('fw_unsigned')">FW UPDATE (unsigned — attack)</button>
  </div>
  <div id="console"></div>
  <div style="margin-top:8px;display:flex;gap:6px">
   <input type="text" id="rawline" placeholder="raw line to firmware, e.g. SIM|gas=750 or garbage to test tolerance" style="flex:1"
     onkeydown="if(event.key=='Enter')sendRawLine()">
   <button class="acc" onclick="sendRawLine()">SEND</button>
  </div>
 </div>
 <div class="card" style="flex:0 0 260px"><div class="dim">MODE</div><div id="mode" class="DAY">—</div>
  <div style="margin:8px 0 2px" class="dim">signed in as
   <select id="role"><option>admin</option><option>operator</option><option>viewer</option></select>
   <input type="text" id="pin" placeholder="PIN" style="width:58px" maxlength="4"></div>
  <div style="margin-top:6px">
   <button onclick="cmd('ARM')">ARM night</button><button onclick="cmd('DISARM')">DISARM</button><br>
   <button onclick="cmd('FAN_ON')">FAN ON</button><button onclick="cmd('FAN_OFF')">FAN OFF</button>
   <button onclick="cmd('VENT')">VENT</button><br>
   <button class="red" onclick="fetch('/attack',{method:'POST',headers:H})">REPLAY ATTACK</button>
   <button class="red" onclick="cmd('UNLOCK')">UNLOCK</button>
  </div>
  <div class="dim" style="margin-top:12px">ENERGY</div>
  <div id="energy">—</div><div class="dim">saved vs always-on</div>
 </div>
</div>

<div class="row">
 <div class="card"><div class="dim" style="margin-bottom:6px">FLOOR PLAN</div>
  <div class="zones">
   <div class="zone" id="z-hall"><h3>POULTRY HALL</h3><div class="v" id="v-hall">—</div></div>
   <div class="zone" id="z-pit"><h3>MANURE PIT</h3><div class="v" id="v-pit">—</div></div>
   <div class="zone" id="z-store"><h3>FEED & WATER STORE</h3><div class="v" id="v-store">—</div></div>
   <div class="zone" id="z-ctrl"><h3>CONTROL ROOM</h3><div class="v" id="v-ctrl">—</div></div>
  </div></div>
 <div class="card"><div class="dim">SIMULATED SENSORS <span class="simtag">SIM</span> — organizer-sanctioned stand-ins</div>
  <div class="sl"><label>NH3 ammonia (hall) — limit 25 ppm</label><input type="range" min="0" max="80" value="8" oninput="sim('nh3',this.value)"></div>
  <div class="sl"><label>Gas CH4 (pit)</label><input type="range" min="0" max="1023" value="120" oninput="sim('gas',this.value)"></div>
  <div class="sl"><label>Flame (store)</label><button onclick="sim('flame',1)">FLAME</button><button onclick="sim('flame',0)">clear</button>
   <label style="margin-left:14px">Motion</label><button onclick="sim('mot',1)">INTRUDER</button><button onclick="sim('mot',0)">clear</button></div>
 </div>
</div>

<div class="row">
 <div class="card" style="flex:2">
  <div class="dim">AI ANALYST <span class="aitag">TIER 2</span> — predictive layer.
   <b>Advisory only: it never actuates.</b> Every command still goes through CMD|ctr|mac|ACTION.</div>
  <div id="aibase" class="dim" style="margin:6px 0">waiting for telemetry…</div>
  <table id="aitab"></table>
 </div>
 <div class="card">
  <div class="dim">AI FINDINGS</div>
  <div id="aifind" style="height:150px;overflow-y:auto;font-size:12px;line-height:1.5;margin-top:6px">
   <span class="dim">nothing anomalous</span></div>
  <button class="acc" onclick="fetch('/ai/relearn',{method:'POST',headers:H})">RELEARN BASELINE</button>
 </div>
</div>
<div class="row">
 <div class="card"><div class="dim">EVENT LOG</div><div id="log"></div></div>
 <div class="card"><div class="dim">CHAINED AUDIT LOG (EEPROM)</div>
  <table id="audit"><tr><th>#</th><th>event</th><th>val</th><th>min</th><th>chain</th></tr></table></div>
</div>
<script>
const H={'Content-Type':'application/json'};
const el=id=>document.getElementById(id);
const cmd=a=>fetch('/cmd',{method:'POST',headers:H,
 body:JSON.stringify({action:a,role:el('role').value,pin:el('pin').value})});
const sim=(n,v)=>fetch('/sim',{method:'POST',headers:H,body:JSON.stringify({name:n,value:v})});
const script=n=>fetch('/script',{method:'POST',headers:H,body:JSON.stringify({name:n,role:el('role').value})});
function sendRawLine(){const i=el('rawline');if(!i.value.trim())return;
 fetch('/raw',{method:'POST',headers:H,body:JSON.stringify({line:i.value})});i.value='';}
async function loadPorts(){const r=await(await fetch('/ports')).json();
 el('ports').innerHTML=r.ports.map(p=>`<option value="${p.device}">${p.device} ${p.desc?'— '+p.desc:''}</option>`).join('')
   ||'<option value="">no ports found — is the UNO plugged in?</option>';}
function connectSer(){const p=el('ports').value;if(p)fetch('/connect',{method:'POST',headers:H,body:JSON.stringify({port:p})});}
function onSerial(s){const p=el('serialpill');
 p.className='pill '+(s.connected?'on':'off');
 p.textContent='serial: '+(s.connected?(s.port||'?'):(s.detail||'none'));}
function onRaw(r){const c=el('console');const d=document.createElement('div');
 d.className=r.ok?r.dir:'bad';
 d.textContent=`${r.t} ${r.dir==='rx'?'←':'→'} ${r.line}${r.ok?'':'   ⟵ UNPARSED'}`;
 c.appendChild(d);while(c.childNodes.length>400)c.removeChild(c.firstChild);
 c.scrollTop=c.scrollHeight;}
function onCounters(k){el('stats').textContent=` rx ${k.rx} · tx ${k.tx} · unparsed ${k.unparsed}`;
 el('stats').style.color=k.unparsed>0?'var(--alert)':'var(--dim)';}
function fmt(t,k,unit){if(!t[k])return '—';return t[k].v+unit+(t[k].sim?' <span class=simtag>SIM</span>':'')}
function onTel(t){
 el('v-hall').innerHTML=`NH3 ${fmt(t,'nh3',' ppm')}<br>T ${fmt(t,'t1','°')} / ${fmt(t,'t2','°')} · H ${fmt(t,'hum','%')}<br>snd ${fmt(t,'snd','')}`;
 el('v-pit').innerHTML=`CH4 ${fmt(t,'gas','')} <br>valve ${t.relay&&t.relay.v?'OPEN':'<b class=ALERT>CUT</b>'} · fan ${t.fan&&t.fan.v?'ON':'off'}`+
   (t.gas&&t.gas.v>=700?`<br><span class=noenter>DO NOT ENTER — rescuers are >1/4 of manure-gas victims</span>`:'');
 el('v-store').innerHTML=`water ${fmt(t,'water','')}<br>flame ${fmt(t,'flame','')}`;
 el('v-ctrl').innerHTML=`cabinet ${t.tamp&&t.tamp.v?'<b class=ALERT>OPEN</b>':'closed'} · vent ${t.vent&&t.vent.v?'open':'shut'}`;
 if(t.saved_pct)el('energy').textContent=t.saved_pct.v+'%';
 el('z-pit').className='zone'+(t.gas&&t.gas.v>=700?' alert':t.gas&&t.gas.v>=450?' warn':'');
 el('z-hall').className='zone'+(t.nh3&&t.nh3.v>=25?' warn':'');
 el('z-store').className='zone'+(t.flame&&t.flame.v>0?' alert':(t.water&&t.water.v<20?' warn':''));
 el('z-ctrl').className='zone'+(t.tamp&&t.tamp.v?' alert':'');
}
function onAi(a){
 const b=el('aibase');
 if(a.learning){const p=Math.round(a.progress*100);
  b.innerHTML=`<b>learning what "normal" looks like in this room</b> — ${p}% of ${a.baseline_secs}s`;
  b.style.color='var(--acc)';}
 else{b.innerHTML=`baseline learned at <b>${a.learned_at||'—'}</b> from ${a.baseline_secs}s of normal operation`;
  b.style.color='var(--dim)';}
 el('aitab').innerHTML='<tr><th>channel</th><th>value</th><th>trend</th><th>time to critical</th><th>vs baseline</th></tr>'+
  a.channels.map(c=>{
   const flat=Math.abs(c.per_min)<0.5;
   const arrow=c.per_min>0?'▲':'▼';
   const trend=flat?'<span class=dim>steady</span>':`${arrow} ${c.per_min>0?'+':''}${c.per_min}${c.unit}/min`;
   const eta=c.eta?`<b class="${c.state=='alert'?'ALERT':'WARN'}">${c.eta}</b>`:'<span class=dim>—</span>';
   const z=(c.z===null||c.z===undefined)?'<span class=dim>learning</span>'
     :`<span class="${Math.abs(c.z)>=4?'WARN':'dim'}">${c.z>0?'+':''}${c.z}σ</span>`;
   return `<tr class="ai-${c.state}"><td>${c.label} <span class=dim>${c.zone}</span></td>`+
     `<td>${c.v}${c.unit}</td><td>${trend}</td><td>${eta}</td><td>${z}</td></tr>`;
  }).join('');
 el('aifind').innerHTML=a.findings.slice().reverse().map(f=>
   `<div class="${f.sev}">${f.t} <b>${f.kind}</b> ${f.msg}</div>`).join('')
   ||'<span class=dim>nothing anomalous</span>';
}
function banner(cls,msg){const b=el('banner');b.className=cls;b.textContent=msg+'  (tap to dismiss)';}
function onEvent(e,old){const d=document.createElement('div');d.className=e.sev;
 d.textContent=`${e.t}  ${e.raw}`;el('log').prepend(d);
 if(old)return;
 const p=e.raw.split('|');
 if(p[0]==='AI'){if(el('banner').className!=='EMERG'&&el('banner').className!=='ALERT'&&(e.sev==='ALERT'||e.sev==='WARN'))
   banner('AIB','AI ANALYST: '+(p[4]||''));return;}
 if(e.sev==='EMERG')banner('EMERG','EMERGENCY: '+(p[3]||'')+' — zone '+(p[2]||'?'));
 else if(e.sev==='ALERT')banner('ALERT','ALERT: '+(p[3]||'')+' — '+(p[2]||''));
 else if(e.sev==='SEC')banner('SEC','CYBER: '+p.slice(1).join(' · '));
 else if((p[3]||'').startsWith('GAS_CLEARED')||(p[3]||'')==='PIN_OK_DISARMED')el('banner').className='';}
function onLog(rows){const tb=el('audit');tb.innerHTML='<tr><th>#</th><th>event</th><th>val</th><th>min</th><th>chain</th></tr>';
 rows.filter(r=>r.chain!='EMPTY').forEach(r=>{tb.innerHTML+=`<tr><td>${r.slot}</td><td>${r.what}</td><td>${r.val}</td><td>${r.min}</td><td class=${r.chain}>${r.chain}</td></tr>`})}
function onMode(m){const e=el('mode');e.textContent=m;e.className=m;}
const es=new EventSource('/stream');
es.onmessage=ev=>{const m=JSON.parse(ev.data);
 if(m.type=='tel')onTel(m.tel);
 else if(m.type=='raw'){onRaw(m.raw);onCounters(m.counters);}
 else if(m.type=='state')onMode(m.mode);
 else if(m.type=='event')onEvent(m.event);
 else if(m.type=='log')onLog(m.log);
 else if(m.type=='ai')onAi(m.ai);
 else if(m.type=='serial')onSerial(m);
 else if(m.type=='hello'){el('log').innerHTML='';el('console').innerHTML='';
   onMode(m.state.mode);onTel(m.state.tel||{});
   (m.events||[]).forEach(e=>onEvent(e,true));(m.raws||[]).forEach(onRaw);
   onCounters(m.counters||{rx:0,tx:0,unparsed:0});onSerial(m.serial||{});
   if(m.ai)onAi(m.ai);}};
loadPorts();
</script></body></html>"""

# ── /fire — fire-station dispatch screen (PITCH DEMO ONLY) ───────────────
# Read-only consumer of the same SSE stream. No bridge/firmware logic here:
# if this page is closed nothing changes. Stylized Romania map, 40 BioGuard
# nodes; the live node is Ferma Strajer (Nea Ion, jud. Timis), responding
# station is Lugoj — the jury's own Honeywell town.
FIRE_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISU Banat — Dispecerat 112</title>
<style>
 /* 112 dispatch console — same industrial family as the bridge, night-shift
    register: red is reserved for live incidents, the clock is always king. */
 :root{--bg:#080B10;--card:#12171F;--inset:#0A0E14;--line:#26303C;--edge:#33404F;
       --tx:#F2F6FA;--dim:#8E9AA8;--ok:#35C46F;--warn:#F0A72E;--alert:#FF5449;
       --acc:#41A8FF;--red:#C6362C;
       --sans:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
       --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--tx);padding:14px 16px;overflow-x:hidden;
   font-family:var(--sans);font-size:13.5px}
 #topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
   padding:2px 2px 12px;border-bottom:1px solid var(--line)}
 .brand{display:flex;align-items:center;gap:11px}
 .brand-tick{width:4px;height:38px;background:var(--red);border-radius:2px}
 .brand-name{font-weight:800;font-size:18px;line-height:1;letter-spacing:.1em}
 .brand-sub{font-size:11.5px;color:var(--dim);margin-top:4px;letter-spacing:.03em}
 .topbar-right{display:flex;align-items:center;gap:14px}
 .dim{color:var(--dim);font-size:12px}
 .card>.dim:first-child{font-weight:700;font-size:10.5px;letter-spacing:.1em;
   text-transform:uppercase;color:var(--dim)}
 .row{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px}
 .pill{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:3px 10px;
   font-family:var(--mono);font-size:11px}
 .pill.on{border-color:#1E5C38;color:#5FD68F;background:#0D2417}
 .pill.off{border-color:#6B4E12;color:#F0C36A;background:#241A05}
 .pill.sim{border-color:#4A3357;color:#C9A6DE;background:#1C1224;letter-spacing:.4px}
 #clock{font-family:var(--mono);font-size:30px;font-weight:700;color:var(--tx);
   font-variant-numeric:tabular-nums;letter-spacing:.04em}
 @keyframes bl{50%{opacity:.35}}
 .farm{fill:#2EA04366} .farm-core{fill:var(--ok)}
 svg text{font-family:var(--sans);font-weight:600}
 #status{font-size:14px;font-weight:600;padding:11px 14px;border-radius:6px;background:#0D2417;
   border:1px solid #1E5C38;border-left:4px solid var(--ok);color:#7EE787;margin-top:12px}
 #status.pre{background:#241A05;border-color:#6B4E12;border-left-color:var(--warn);
   color:#F0C36A;animation:bl 1.4s infinite}
 #status.inc{background:#2E0D0B;border-color:#7A2B27;border-left-color:var(--alert);
   color:#FF8A82;animation:bl 1s infinite;
   background-image:repeating-linear-gradient(-45deg,transparent 0 12px,#FF544912 12px 24px)}
 #feed{height:190px;overflow-y:auto;font-family:var(--mono);font-size:11.5px;line-height:1.65;margin-top:8px}
 #feed .WARN{color:var(--warn)} #feed .EMERG{color:var(--alert);font-weight:bold}
 #feed .OK{color:var(--ok)} #feed .INFO{color:var(--dim)}
 #incident{display:none}
 #incident.show{display:block;border-color:#7A2B27;border-top:3px solid var(--alert)}
 #incident h2{margin:0 0 10px;color:var(--alert);font-size:14px;font-weight:800;
   letter-spacing:.08em;animation:bl 1.2s infinite}
 #incident table{width:100%;font-size:12.5px;border-collapse:collapse}
 #incident td{border-bottom:1px solid var(--line);padding:6px}
 #incident td:first-child{color:var(--dim);width:150px;font-size:11px;font-weight:700;
   letter-spacing:.05em;text-transform:uppercase}
 .tel{font-family:var(--mono);font-size:19px;font-weight:700;font-variant-numeric:tabular-nums}
 .tel.bad{color:var(--alert)}
 #overlay{display:none;position:fixed;inset:0;z-index:50;background:#180507F2;
   text-align:center;padding-top:9vh}
 #overlay.show{display:block}
 #overlay .ringbox{display:inline-block;position:relative;width:150px;height:150px}
 #overlay .ringbox div{position:absolute;inset:0;border:3px solid var(--alert);
   border-radius:50%;animation:opulse 1.6s infinite ease-out}
 #overlay .ringbox div:nth-child(2){animation-delay:.5s}
 #overlay .ringbox div:nth-child(3){animation-delay:1s}
 @keyframes opulse{0%{transform:scale(.55);opacity:1}100%{transform:scale(1.5);opacity:0}}
 #overlay .phone{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
   font-family:var(--sans);font-size:44px;font-weight:800;letter-spacing:.06em;color:#fff;
   animation:callpulse 1.1s infinite}
 @keyframes callpulse{0%,100%{transform:scale(1)}50%{transform:scale(1.09)}}
 #overlay h2{font-size:28px;font-weight:800;letter-spacing:.04em;color:#fff;
   margin:26px 0 6px;animation:bl 1s infinite}
 #overlay h3{font-size:18px;font-weight:600;color:#FFB3AD;margin:6px 0}
 #overlay .why{font-size:15.5px;color:#FFDFDC;margin:14px auto;max-width:640px;line-height:1.55}
 #answer{background:var(--ok);color:#04120A;border:none;border-radius:8px;
   font-family:var(--sans);font-size:19px;font-weight:800;letter-spacing:.08em;
   padding:16px 54px;cursor:pointer;margin-top:18px;box-shadow:0 0 40px #35C46F66}
 #answer:hover{transform:scale(1.04)}
 #duty{position:fixed;inset:0;z-index:60;background:#080B10F5;display:flex;
   align-items:center;justify-content:center;flex-direction:column;gap:16px}
 #duty h1{font-size:19px;font-weight:800;letter-spacing:.09em;margin:0}
 .roundel{width:88px;height:88px;border:3px solid var(--red);border-radius:50%;
   display:flex;align-items:center;justify-content:center;
   font-size:30px;font-weight:800;letter-spacing:.04em;color:#FF8A82}
 #duty button{background:var(--card);color:var(--tx);border:1px solid var(--edge);
   border-radius:8px;font-family:var(--sans);font-size:16px;font-weight:700;
   letter-spacing:.04em;padding:16px 40px;cursor:pointer}
 #duty button:hover{background:#1C2530;border-color:var(--acc)}
 .ok{color:var(--ok)}
</style></head><body>

<div id="duty">
 <div class="roundel">112</div>
 <h1>ISU BANAT — DISPECERAT 112 · STAȚIA LUGOJ</h1>
 <div class="dim">demo screen — receives BioGuard auto-dispatch calls</div>
 <button onclick="goOnDuty()">GO ON DUTY — enable audio alerts</button>
</div>

<header id="topbar">
 <div class="brand"><span class="brand-tick"></span>
  <div>
   <div class="brand-name">ISU BANAT — DISPECERAT 112</div>
   <div class="brand-sub">Stația de Pompieri Lugoj · BioGuard auto-dispatch uplink</div>
  </div>
 </div>
 <div class="topbar-right">
  <span class="pill sim">CONCEPT · SIMULATED CONSOLE — not an ISU system</span>
  <span id="uplink" class="pill off">BioGuard uplink: …</span>
  <span id="clock">--:--:--</span>
 </div>
</header>

<div class="row">
 <div class="card" style="flex:3;min-width:420px">
  <div class="dim">BIOGUARD FLEET — 40 nodes · illustrative scale-out <span style="float:right">● <span class="ok">nominal</span> · ● <span style="color:var(--warn)">pre-alert</span> · ● <span style="color:var(--alert)">incident</span></span></div>
  <svg id="map" viewBox="0 0 672 480" style="width:100%;margin-top:8px">
   <polygon points="189,40 210,30 266,43 329,68 392,45 427,18 451,13 476,40 493,80 553,150 563,200 553,250 598,305 661,305 665,325 623,360 591,405 588,465 539,440 469,435 385,470 301,465 217,455 185,435 175,380 136,392 98,365 80,320 42,265 3,230 63,180 91,140 126,90 168,60"
     fill="#131c26" stroke="#2c3a4d" stroke-width="2"/>
   <g id="fleet"></g>
   <g id="incgroup" style="display:none">
    <circle id="ring1" cx="95" cy="255" fill="none" stroke="#f85149" stroke-width="2">
      <animate attributeName="r" values="8;36" dur="1.4s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values=".9;0" dur="1.4s" repeatCount="indefinite"/></circle>
    <line x1="95" y1="255" x2="119" y2="271" stroke="#58a6ff" stroke-width="1.6" stroke-dasharray="5 4"/>
    <circle cx="119" cy="271" r="5" fill="#58a6ff"/>
    <text x="126" y="272" fill="#58a6ff" font-size="9">Stația Lugoj</text>
    <text x="126" y="284" fill="#58a6ff" font-size="9">~14 km · ETA ~18 min</text>
    <text x="95" y="242" fill="#ff7b72" font-size="12" font-weight="bold" text-anchor="middle">FERMA STRĂJER</text>
   </g>
   <circle id="incdot" cx="95" cy="255" r="6" class="farm-core"/>
  </svg>
  <div id="status">NO ACTIVE INCIDENTS — 40 farms reporting normal</div>
 </div>

 <div style="flex:2;min-width:340px;display:flex;flex-direction:column;gap:14px">
  <div class="card" id="incident">
   <h2 id="inc-title">⬤ ACTIVE INCIDENT</h2>
   <table>
    <tr><td>Farm</td><td><b>Ferma Străjer</b> — BioGuard node FS-017</td></tr>
    <tr><td>Location</td><td>sat Știuca, jud. Timiș · 45.57°N 21.98°E</td></tr>
    <tr><td>Contact</td><td>Ion Popescu („Nea Ion") · +40 7xx xxx xxx</td></tr>
    <tr><td>Nature</td><td id="inc-nature">—</td></tr>
    <tr><td>Dispatched</td><td id="inc-crew">1× autospecială stingere + SMURD — Stația Lugoj</td></tr>
    <tr><td>Live CH4 (pit)</td><td class="tel" id="tel-gas">—</td></tr>
    <tr><td>Live flame</td><td class="tel" id="tel-flame">—</td></tr>
    <tr><td>Hall temp</td><td class="tel" id="tel-t1">—</td></tr>
   </table>
   <div class="dim" style="margin-top:8px">⚠ manure-pit gas: instruct crew SCBA before entry — rescuers are >¼ of victims</div>
  </div>
  <div class="card" style="flex:1">
   <div class="dim">DISPATCH LOG</div>
   <div id="feed"><span class="dim">quiet shift…</span></div>
  </div>
 </div>
</div>

<div id="overlay">
 <div class="ringbox"><div></div><div></div><div></div><div class="phone">112</div></div>
 <h2>INCOMING AUTOMATED EMERGENCY CALL</h2>
 <h3>BioGuard Auto-Dispatch · node FS-017 — Ferma Străjer, jud. Timiș</h3>
 <div class="why" id="ov-why">—</div>
 <div class="dim">machine-generated call · two independent channels agree · GPS attached</div><br>
 <button id="answer" onclick="answerCall()">ANSWER</button>
</div>

<script>
const el=id=>document.getElementById(id);
// 39 background fleet nodes (stylized positions; live node drawn separately)
const FARMS=[[238,163],[70,265],[515,124],[252,408],[378,275],[580,420],[121,135],
 [277,260],[469,183],[407,346],[77,222],[548,296],[464,325],[188,61],[424,75],
 [432,147],[305,186],[237,233],[189,252],[119,310],[291,397],[327,354],[368,347],
 [413,390],[499,420],[501,384],[590,320],[489,270],[527,176],[452,65],[200,121],
 [236,74],[301,127],[392,204],[391,253],[292,330],[172,377],[404,445],[359,440]];
el('fleet').innerHTML=FARMS.map(([x,y],i)=>
 `<circle cx="${x}" cy="${y}" r="4" class="farm"><title>BioGuard node #${i+1} — nominal</title></circle>`+
 `<circle cx="${x}" cy="${y}" r="2" class="farm-core"></circle>`).join('');

setInterval(()=>{el('clock').textContent=new Date().toLocaleTimeString('ro-RO')},500);

// ── audio (armed by the GO ON DUTY click) ────────────────────────────────
let AC=null, ringTimer=null;
function tone(f,dur,when,vol){const o=AC.createOscillator(),g=AC.createGain();
 o.frequency.value=f;o.connect(g);g.connect(AC.destination);
 g.gain.setValueAtTime(0,when);g.gain.linearRampToValueAtTime(vol,when+.02);
 g.gain.setValueAtTime(vol,when+dur-.05);g.gain.linearRampToValueAtTime(0,when+dur);
 o.start(when);o.stop(when+dur);}
function chime(){if(!AC)return;const t=AC.currentTime;tone(880,.15,t,.25);tone(660,.3,t+.18,.25);}
function ringBurst(){if(!AC)return;const t=AC.currentTime;   // EU 425 Hz ringtone
 tone(425,.45,t,.4);tone(425,.45,t+.6,.4);}
function startRing(){stopRing();ringBurst();ringTimer=setInterval(ringBurst,2200);}
function stopRing(){if(ringTimer){clearInterval(ringTimer);ringTimer=null;}}
function goOnDuty(){try{AC=new (window.AudioContext||window.webkitAudioContext)();}catch(e){}
 el('duty').style.display='none';log('INFO','on duty — BioGuard uplink monitoring 40 nodes');}

// ── incident state machine ───────────────────────────────────────────────
let phase='idle';          // idle | prealert | held | ringing | active | contained
function log(sev,msg){const d=document.createElement('div');d.className=sev;
 d.textContent=`${new Date().toLocaleTimeString('ro-RO')}  ${msg}`;
 const f=el('feed');if(f.firstChild&&f.firstChild.className==='dim')f.innerHTML='';
 f.prepend(d);}
function setDot(color,r){const d=el('incdot');d.style.fill=color;d.setAttribute('r',r);}
function zoomTo(x,y,w,h,ms){const s=el('map').viewBox.baseVal,
 f={x:s.x,y:s.y,w:s.width,h:s.height},t0=performance.now();
 (function step(t){const p=Math.min(1,(t-t0)/ms),e=p<.5?2*p*p:1-Math.pow(-2*p+2,2)/2;
  el('map').setAttribute('viewBox',`${f.x+(x-f.x)*e} ${f.y+(y-f.y)*e} ${f.w+(w-f.w)*e} ${f.h+(h-f.h)*e}`);
  if(p<1)requestAnimationFrame(step);})(t0);}

function preAlert(msg){if(phase!=='idle')return;phase='prealert';
 setDot('var(--warn)',8);chime();
 el('status').className='pre';
 el('status').innerHTML='⚠ PRE-ALERT — Ferma Străjer (jud. Timiș): '+msg+'<br><span class="dim">advance notice from BioGuard predictive layer — crew placed on standby, no dispatch yet</span>';
 log('WARN','PRE-ALERT from BioGuard FS-017: '+msg);
 log('WARN','→ crew Lugoj placed on standby');}

function dispatch(nature,why){if(phase==='ringing'||phase==='active')return;
 phase='ringing';setDot('var(--alert)',8);
 el('inc-nature').textContent=nature;
 el('ov-why').innerHTML=why;
 el('status').className='inc';
 el('status').textContent='⬤ INCOMING EMERGENCY CALL — Ferma Străjer, jud. Timiș';
 el('overlay').className='show';startRing();
 log('EMERG','AUTOMATED 112 CALL — BioGuard FS-017: '+nature);}

function answerCall(){stopRing();el('overlay').className='';phase='active';
 el('incident').className='card show';
 el('incgroup').style.display='';
 el('status').className='inc';
 el('status').textContent='⬤ ACTIVE INCIDENT — Ferma Străjer · crew Lugoj dispatched · ETA ~18 min';
 zoomTo(0,155,280,200,900);
 log('EMERG','call answered — dispatching 1× autospecială + SMURD from Stația Lugoj');
 log('INFO','GPS + live telemetry link opened to responding crew');}

function contain(){pendingFlame=null;
 if(phase!=='active'&&phase!=='prealert'&&phase!=='ringing'&&phase!=='held')return;
 stopRing();el('overlay').className='';
 phase='contained';setDot('var(--ok)',6);
 el('incgroup').style.display='none';
 el('status').className='';
 el('status').innerHTML='<span class="ok">SITUATION CONTAINED</span> — Ferma Străjer back to normal · 40 farms reporting';
 el('inc-title').textContent='✓ INCIDENT CLOSED';el('inc-title').style.animation='none';
 zoomTo(0,0,672,480,900);
 log('OK','BioGuard FS-017 reports values back in the safe band — incident closed');
 setTimeout(()=>{if(phase==='contained'){phase='idle';
   el('incident').className='card';el('inc-title').textContent='⬤ ACTIVE INCIDENT';
   el('inc-title').style.animation='';el('status').textContent='NO ACTIVE INCIDENTS — 40 farms reporting normal';}},12000);}

// ── SSE: same stream the main dashboard reads ────────────────────────────
// ── corroboration gate ───────────────────────────────────────────────────
// We never roll a crew on a single binary pin. Our own tier-2 analyst flags a
// flame asserted with no thermal signature as "sensor fault or spoofed input";
// dispatching on that anyway would have our two screens contradicting each
// other live. So a FLAME_DETECTED is HELD until a second, physically
// independent channel agrees -- hall temperature rising over the session
// baseline, or CH4 critical in the same building. A false truck roll is a real
// cost to a real station, and it is how a farm gets switched off.
let ambT1=null,lastT1=null,flameOn=false,gasCrit=false,pendingFlame=null;
const CORRO_RISE=5;   // °C over pre-event ambient before we believe the flame pin
function corroboration(){
 if(gasCrit)return 'CH4 critical in the same building';
 if(ambT1!==null&&lastT1!==null&&lastT1-ambT1>=CORRO_RISE)
   return 'hall temperature +'+Math.round(lastT1-ambT1)+'° over ambient';
 return null;}
function tryDispatch(){if(!pendingFlame)return;
 const why=corroboration();if(!why)return;
 const p=pendingFlame;pendingFlame=null;
 log('OK','corroborated — '+why);
 dispatch(p.n,p.w+'<br><span class="dim">corroboration: '+why+'</span>');}
function holdFlame(n,w){if(phase==='ringing'||phase==='active'||pendingFlame)return;
 pendingFlame={n:n,w:w};phase='held';setDot('var(--warn)',8);
 el('status').className='pre';
 el('status').innerHTML='◐ FLAME ASSERTED — HELD FOR CORROBORATION<br><span class="dim">single-sensor assertion from FS-017 · no crew dispatched until a second independent channel agrees</span>';
 log('WARN','flame asserted by FS-017 — HELD: single sensor, awaiting corroboration');
 tryDispatch();}

function onTel(t){const g=t.gas?t.gas.v:null,fl=t.flame?t.flame.v:null,t1=t.t1?t.t1.v:null;
 if(g!==null){el('tel-gas').textContent=Math.round(g)+(g>=700?'  — EXPLOSIVE':'');
   el('tel-gas').className='tel'+(g>=700?' bad':'');
   if(g>=700)gasCrit=true;else if(g<400)gasCrit=false;}
 if(fl!==null){el('tel-flame').textContent=fl>0?'DETECTED':'clear';
   el('tel-flame').className='tel'+(fl>0?' bad':'');flameOn=fl>0;}
 if(t1!==null){el('tel-t1').textContent=Math.round(t1)+'°C';lastT1=t1;
   // ambient only tracks while nothing is burning, so a fire can never drag
   // its own baseline up behind it
   if(!flameOn)ambT1=(ambT1===null)?t1:ambT1*0.9+t1*0.1;}
 tryDispatch();}
function onEvent(e){const p=e.raw.split('|');
 if(p[0]==='AI'&&p[1]==='PREDICT'&&(e.sev==='WARN'||e.sev==='ALERT'))preAlert(p[4]||'');
 if(p[0]==='AI'&&p[1]==='PLAUS'&&(p[3]||'').indexOf('FLAME')>=0&&pendingFlame)
   log('WARN','tier-2 analyst agrees: '+(p[4]||'flame implausible')+' — dispatch stays held');
 if(p[0]==='EVT'&&e.sev==='EMERG'){
  if(p[3]==='FLAME_DETECTED')holdFlame('FIRE — flame confirmed (feed & water store)',
    'Flame detected in the feed store.<br>CH4 + hay environment — <b>high fire spread risk</b>.<br>Sprinkler + ventilation already actuated by the on-site reflex layer.');
  else if(p[3]==='GAS_CRITICAL')dispatch('EXPLOSIVE ATMOSPHERE — CH4 critical (manure pit)',
    'Methane above the critical threshold in the manure pit.<br><b>Explosion risk — livestock and one family on site.</b><br>Power to the pit cut and extraction running (automatic).');}
 if(p[0]==='EVT'&&(p[3]==='GAS_CLEARED'))contain();}
const es=new EventSource('/stream');
es.onmessage=ev=>{const m=JSON.parse(ev.data);
 if(m.type==='tel')onTel(m.tel);
 else if(m.type==='event')onEvent(m.event);
 else if(m.type==='state'&&(m.mode==='DAY'||m.mode==='NIGHT')&&phase==='active')contain();
 else if(m.type==='hello'){el('uplink').className='pill on';
   el('uplink').textContent='BioGuard uplink: LIVE';
   onTel(m.state.tel||{});}};
es.onerror=()=>{el('uplink').className='pill off';el('uplink').textContent='BioGuard uplink: lost';};
</script></body></html>"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="serial port to auto-connect at startup (optional; UI can pick)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--fake", action="store_true", help="generated data, no hardware")
    ap.add_argument("--pi", help="Raspberry Pi node host/IP — adds socket://<pi>:7777 to the port picker")
    ap.add_argument("--baseline", type=float, default=45.0,
                    help="seconds of normal operation the analyst learns from (venue: 600)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--http-port", type=int, default=5001,
                    help="dashboard port (use another one to run a second bench alongside)")
    args = ap.parse_args()
    analyst.baseline_secs = args.baseline
    if args.pi:
        pi_host = args.pi
    if args.fake:
        fake_on = True
        threading.Thread(target=fake_loop, daemon=True).start()
    if args.port:
        threading.Thread(target=reader_loop, args=(args.port, args.baud), daemon=True).start()
    app.run(host=args.host, port=args.http_port, threaded=True)
