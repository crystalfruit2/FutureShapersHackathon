"""Fleet analytics — the part that only works BECAUSE the data is pooled.

Three layers, in increasing order of "you could not do this on the node":

  1. per-farm forecast    linear extrapolation to a threshold crossing.
                          The node already does this locally; the cloud does
                          it over 30 days instead of 45 seconds.
  2. fleet risk model     logistic regression trained on every farm's history,
                          predicting an ALERT-grade incident in the next 6 h.
                          A new farm inherits the fleet's learned weights on
                          day one instead of collecting its own month of data.
  3. regional signal      correlated distress across neighbouring farms.
                          One farm with a feed drop is a feeder fault; three
                          farms in the same county on the same day is a
                          notifiable disease pattern (ASF). No single farm can
                          see this about itself.

Deliberately dependency-free: hand-rolled logistic regression in pure Python.
`pip install scikit-learn` is not a thing we want between us and a demo.
"""
from __future__ import annotations

import math
import time

# feature order is the model's contract — appended to, never reordered
FEATURES = [
    ("nh3_mean",   "ammonia level"),
    ("nh3_slope",  "ammonia trend"),
    ("temp_mean",  "temperature level"),
    ("temp_slope", "temperature trend"),
    ("hum_mean",   "humidity"),
    ("gas_max",    "methane peak"),
    ("gas_slope",  "methane trend"),
    ("water",      "water reserve"),
    ("food",       "feed reserve"),
    ("hour_sin",   "time of day"),
    ("hour_cos",   "time of day"),
]
FEATURE_KEYS = [k for k, _ in FEATURES]

WINDOW_H = 3      # hours of history each prediction looks back over
HORIZON_H = 6     # hours ahead the model predicts

# what "bad" means per metric — shared by the forecast and the labeller
THRESHOLDS = {
    "nh3": (25.0, 50.0),      # (warn, critical) ppm
    "temp": (32.0, 38.0),     # °C
    "gas": (450.0, 700.0),    # raw MQ-4 units
}


# ── feature extraction ───────────────────────────────────────────────────
def _slope(vals: list[float]) -> float:
    """Least-squares slope per sample-step. Flat when there's nothing to fit."""
    n = len(vals)
    if n < 2:
        return 0.0
    mx = (n - 1) / 2.0
    my = sum(vals) / n
    num = sum((i - mx) * (v - my) for i, v in enumerate(vals))
    den = sum((i - mx) ** 2 for i in range(n))
    return num / den if den else 0.0


def featurize(window: list[dict], hour: int) -> list[float]:
    """A window of consecutive samples (oldest first) -> the model's vector."""
    g = lambda k: [float(s.get(k) or 0.0) for s in window]
    nh3, temp, hum, gas = g("nh3"), g("temp"), g("hum"), g("gas")
    last = window[-1] if window else {}
    return [
        sum(nh3) / len(nh3) if nh3 else 0.0,
        _slope(nh3),
        sum(temp) / len(temp) if temp else 0.0,
        _slope(temp),
        sum(hum) / len(hum) if hum else 0.0,
        max(gas) if gas else 0.0,
        _slope(gas),
        float(last.get("water") or 100.0),
        float(last.get("food") or 100.0),
        math.sin(2 * math.pi * hour / 24.0),
        math.cos(2 * math.pi * hour / 24.0),
    ]


# ── logistic regression, by hand ─────────────────────────────────────────
class RiskModel:
    def __init__(self, w=None, b=0.0, mu=None, sd=None, meta=None,
                 prior_shift=0.0):
        self.w = w or [0.0] * len(FEATURE_KEYS)
        self.b = b
        self.mu = mu or [0.0] * len(FEATURE_KEYS)
        self.sd = sd or [1.0] * len(FEATURE_KEYS)
        self.meta = meta or {}
        self.prior_shift = prior_shift

    # -- training ---------------------------------------------------------
    @classmethod
    def train(cls, X: list[list[float]], y: list[int], epochs: int = 400,
              lr: float = 0.35, l2: float = 1e-2):
        n, d = len(X), len(FEATURE_KEYS)
        if n < 30:
            raise ValueError(f"need >=30 labelled windows to train, got {n}")

        mu = [sum(r[j] for r in X) / n for j in range(d)]
        sd = []
        for j in range(d):
            var = sum((r[j] - mu[j]) ** 2 for r in X) / n
            sd.append(math.sqrt(var) or 1.0)
        Z = [[(r[j] - mu[j]) / sd[j] for j in range(d)] for r in X]

        pos = sum(y) or 1
        neg = n - pos or 1
        # incidents are rare; without rebalancing the model just predicts "fine"
        wpos, wneg = n / (2.0 * pos), n / (2.0 * neg)

        w, b = [0.0] * d, 0.0
        for ep in range(epochs):
            gw, gb, tot = [0.0] * d, 0.0, 0.0
            for i in range(n):
                z = b + sum(w[j] * Z[i][j] for j in range(d))
                p = 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))
                cw = wpos if y[i] else wneg
                err = (p - y[i]) * cw
                for j in range(d):
                    gw[j] += err * Z[i][j]
                gb += err
                tot += cw
            step = lr / max(tot, 1.0)
            for j in range(d):
                w[j] -= step * gw[j] + lr * l2 * w[j]
            b -= step * gb

        m = cls(w, b, mu, sd)
        # Training reweighted the classes to 50/50 so the rare positives were
        # learnable at all. That means the fitted model outputs probabilities
        # calibrated to a BALANCED world, not to a barn — which is why an
        # obvious build-up came out as a flat 100%. Shifting the log-odds by
        # the true base rate maps them back to reality. Standard prior
        # correction; without it every number on the console is inflated.
        m.prior_shift = math.log((pos / n) / (1.0 - pos / n))
        m.meta = {"samples": n, "incidents": pos,
                  "base_rate": round(100.0 * pos / n, 2),
                  "auc": round(m.auc(X, y), 3),
                  "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "horizon_h": HORIZON_H, "window_h": WINDOW_H,
                  "version": 1}
        return m

    # -- inference --------------------------------------------------------
    Z_CLIP = 4.0   # live inference sees slopes far outside the training range

    def _z(self, x):
        """Standardize, then clamp. The model was fitted on hourly steps; the
        sink feeds it 20-second buckets rescaled to per-hour, so a scripted
        gas ramp can produce a slope 50 sigma off anything in training.
        Un-clamped that is a log-odds of several hundred — a confident number
        with no evidence behind it. Clamping keeps out-of-range inputs pegged
        at 'as extreme as anything I was trained on' and no further."""
        out = []
        for j in range(len(x)):
            z = (x[j] - self.mu[j]) / self.sd[j]
            out.append(max(-self.Z_CLIP, min(self.Z_CLIP, z)))
        return out

    def logit(self, x: list[float]) -> float:
        z = self._z(x)
        return self.b + sum(self.w[j] * z[j] for j in range(len(z))) \
            + self.prior_shift

    def predict(self, x: list[float]) -> float:
        """Calibrated probability of an ALERT-grade incident within the
        horizon. Capped just below 1: the model is a logistic fit over eleven
        smoothed channels, and nothing that cheap has earned the right to
        print certainty."""
        s = self.logit(x)
        p = 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, s))))
        return min(p, 0.995)

    def explain(self, x: list[float], top: int = 3):
        """Per-feature contribution to the log-odds — why this score, in words."""
        z = self._z(x)
        contrib = [(FEATURES[j][1], self.w[j] * z[j], x[j])
                   for j in range(len(z))]
        pushing = [c for c in contrib if c[1] > 0.02]
        pushing.sort(key=lambda c: -c[1])
        total = sum(c[1] for c in pushing) or 1.0
        seen, out = set(), []
        for label, v, raw in pushing:
            if label in seen:       # hour_sin/hour_cos share one label
                continue
            seen.add(label)
            out.append({"factor": label, "share": round(100 * v / total),
                        "value": round(raw, 1)})
            if len(out) >= top:
                break
        return out

    def auc(self, X, y) -> float:
        """Rank-based AUC. 0.5 = coin flip, 1.0 = perfect separation."""
        scored = sorted(((self.predict(x), yy) for x, yy in zip(X, y)),
                        key=lambda t: t[0])
        pos = sum(y)
        neg = len(y) - pos
        if not pos or not neg:
            return 0.5
        rank_sum = sum(i + 1 for i, (_, yy) in enumerate(scored) if yy)
        return (rank_sum - pos * (pos + 1) / 2.0) / (pos * neg)

    # -- persistence ------------------------------------------------------
    def to_doc(self) -> dict:
        return {"w": [float(x) for x in self.w], "b": float(self.b),
                "mu": [float(x) for x in self.mu],
                "sd": [float(x) for x in self.sd],
                "features": FEATURE_KEYS,
                "prior_shift": float(self.prior_shift), **self.meta}

    @classmethod
    def from_doc(cls, d: dict):
        if not d or "w" not in d:
            return None
        meta = {k: v for k, v in d.items()
                if k not in ("w", "b", "mu", "sd", "features", "prior_shift")}
        return cls([float(x) for x in d["w"]], float(d["b"]),
                   [float(x) for x in d["mu"]], [float(x) for x in d["sd"]], meta,
                   float(d.get("prior_shift", 0.0)))


# ── labelling the training set ───────────────────────────────────────────
def label_incident(sample: dict) -> bool:
    """Did this sample sit in an ALERT-grade state?"""
    for k, (_, crit) in THRESHOLDS.items():
        if float(sample.get(k) or 0) >= crit:
            return True
    if float(sample.get("water") or 100) < 8:
        return True
    if float(sample.get("food") or 100) < 8:
        return True
    return False


def build_dataset(series: list[list[dict]]):
    """[farm_history, ...] -> (X, y). Each farm is its own timeline; windows
    never straddle two farms."""
    X, y = [], []
    for hist in series:
        hist = sorted(hist, key=lambda s: s.get("ts", ""))
        n = len(hist)
        for i in range(WINDOW_H - 1, n - HORIZON_H):
            window = hist[i - WINDOW_H + 1: i + 1]
            # a window that is ALREADY in the incident is not a prediction,
            # it's an observation — those teach the model to read a thermometer
            if any(label_incident(s) for s in window):
                continue
            future = hist[i + 1: i + 1 + HORIZON_H]
            hour = _hour_of(hist[i].get("ts", ""))
            X.append(featurize(window, hour))
            y.append(1 if any(label_incident(s) for s in future) else 0)
    return X, y


def _hour_of(ts: str) -> int:
    try:
        return int(str(ts)[11:13])
    except (ValueError, IndexError):
        return 12


# ── per-farm forecast (threshold ETA) ────────────────────────────────────
MAX_ETA_H = 12.0     # 2x the model horizon; beyond that it is not a forecast


def forecast(hist: list[dict], hours_per_step: float = 1.0):
    """When does each metric cross its next line, at the current trend?

    Two guards keep this from manufacturing predictions out of noise. A trend
    is only reported if the rise it projects over the model's own horizon
    clears one standard deviation of the window it was fitted on, and no ETA
    beyond MAX_ETA_H is shown at all. Without those, a flat channel wobbling
    +-8 units produces a confident 'crosses 450 in 41 h' on every healthy
    farm on the page, and the whole console stops meaning anything.
    """
    out = []
    tail = hist[-6:]
    if len(tail) < 3:
        return out
    for metric, (warn, crit) in THRESHOLDS.items():
        vals = [float(s.get(metric) or 0) for s in tail]
        cur = vals[-1]
        sl = _slope(vals) / hours_per_step        # units per hour
        # Once the warn line is behind us, "already over 25" is a fact the
        # farmer can read off the gauge. The useful sentence is how long until
        # the CRITICAL line, so the target escalates with the reading.
        target, level = (crit, "critical") if cur >= warn else (warn, "warning")
        if cur >= crit:
            out.append({"metric": metric, "state": "critical",
                        "current": round(cur, 1), "threshold": crit, "eta_h": 0.0,
                        "text": f"is past the {crit:g} critical line — act now"})
            continue
        mean = sum(vals) / len(vals)
        noise = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        # Compare the trend to the noise in the SAME units. `sl` has already
        # been rescaled to per-hour, and the sink's rescale factor is 180x
        # (20 s buckets), so testing `sl * HORIZON_H > noise` let 2 units of
        # bucket-to-bucket jitter pass as a 270/h climb — every healthy farm
        # sprouted a confident methane forecast. The rise across the window
        # that was actually measured is the scale-free version of the test.
        rise = abs(_slope(vals)) * len(vals)
        if sl <= 0.05 or rise < noise:
            if cur >= warn:
                out.append({"metric": metric, "state": "over",
                            "current": round(cur, 1), "threshold": warn,
                            "eta_h": 0.0,
                            "text": f"over the {warn:g} line but no longer rising"})
            continue
        eta = (target - cur) / sl
        if 0 < eta <= MAX_ETA_H:
            out.append({"metric": metric,
                        "state": "rising" if level == "warning" else "escalating",
                        "current": round(cur, 1), "threshold": target,
                        "level": level, "rate": round(sl, 2), "eta_h": round(eta, 3),
                        "text": f"crosses the {target:g} {level} line in "
                                f"{_hh(eta)} at {_rate(sl)}"})
    out.sort(key=lambda f: f["eta_h"])
    return out


def _rate(per_hour: float) -> str:
    """A fast event stated per hour reads as noise: the live path rescales
    20-second buckets, so a real gas ramp printed "+14695.7/h". Same number,
    per minute, is something a farmer can picture."""
    if abs(per_hour) >= 600:
        return f"{per_hour / 60:+.0f}/min"
    return f"{per_hour:+.1f}/h"


def _hh(h: float) -> str:
    if h * 3600 < 90:
        return f"{int(round(h * 3600))} s"     # else a 40 s ETA prints "0 min"
    if h < 1:
        return f"{int(round(h * 60))} min"
    if h < 10:
        return f"{h:.1f} h"
    return f"{int(round(h))} h"


# ── regional signal — the cross-farm layer ───────────────────────────────
DISEASE_MARKERS = ("DISTRESS_SOUND", "FOOD_LOW", "WATER_LOW", "MORTALITY")


def regional_signal(farms: list[dict]):
    """Correlated distress inside one county. This is the whole argument for
    pooling data: a single farm reads its own feed drop as a feeder fault."""
    by_region: dict[str, list[dict]] = {}
    for f in farms:
        by_region.setdefault(f.get("region") or "—", []).append(f)

    out = []
    for region, group in by_region.items():
        if len(group) < 2:
            continue
        flagged = [f for f in group
                   if (f.get("risk") or 0) >= 35
                   or any(m in (f.get("markers") or []) for m in DISEASE_MARKERS)]
        if len(flagged) < 2:
            continue
        share = len(flagged) / len(group)
        markers = sorted({m for f in flagged for m in (f.get("markers") or [])})
        sev = "ALERT" if share >= 0.66 else "WARN"
        out.append({
            "region": region, "severity": sev,
            "farms_flagged": len(flagged), "farms_total": len(group),
            "markers": markers[:4],
            "names": [f.get("name", f.get("_id", "?")) for f in flagged],
            "text": f"{len(flagged)} of {len(group)} farms in {region} show the "
                    f"same distress pattern within 24 h"
                    + (f" ({', '.join(m.lower().replace('_', ' ') for m in markers[:3])})"
                       if markers else "")
                    + ". Single-farm monitoring cannot see this — "
                      "notify the county veterinary authority.",
        })
    out.sort(key=lambda r: (r["severity"] != "ALERT", -r["farms_flagged"]))
    return out
