"""Generate a plausible fleet history and push it to the cloud store.

A prediction model demoed on data invented to flatter it is a lie, so the
generator here is written as a crude barn simulator rather than as a
random-number source with the answer baked in:

  * ammonia ACCUMULATES and is removed by ventilation, so it climbs at night
    and after a fan fault — it never teleports to 50 ppm
  * temperature is a diurnal curve the farm fights, not a coin flip
  * every incident is the END of a physical build-up, which is exactly why a
    6-hour-ahead prediction is possible at all

The model is then fitted on this history and scored by AUC on it. If the
generator were noise, the AUC would come out at 0.5 and we would know.

    python3 -m cloud.seed              # seed + train
    python3 -m cloud.seed --days 45    # longer history
    python3 -m cloud.seed --wipe       # rebuild the local store from scratch
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
import zlib
from datetime import datetime, timedelta, timezone

if __package__ in (None, ""):                       # allow `python3 seed.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "cloud"

from . import CFG, open_store            # noqa: E402
from .fleet import (RiskModel, build_dataset, featurize, forecast,  # noqa: E402
                    label_incident, regional_signal, WINDOW_H, _hour_of)

# Four Romanian farms. Two share a county on purpose — that is what makes the
# regional correlation layer demonstrable at all.
FARMS = [
    dict(id="strajer-01", name="Ferma Străjer", owner="Ferma Străjer SRL",
         region="Ilfov", town="Afumați", lat=44.51, lon=26.25,
         species="Broiler poultry", herd=18000, house_m2=1450,
         plan="Pro", installed="2026-06-14", live=True, health=0.94),
    dict(id="ilfov-03", name="Ferma Petrești", owner="Agrozoo Petrești SA",
         region="Ilfov", town="Petrăchioaia", lat=44.62, lon=26.32,
         species="Layer poultry", herd=24000, house_m2=1900,
         plan="Pro", installed="2026-07-02", live=False, health=0.82),
    dict(id="constanta-02", name="Ferma Vadu Oii", owner="Dobrogea Agro SRL",
         region="Constanța", town="Hârșova", lat=44.68, lon=27.95,
         species="Fattening pigs", herd=3200, house_m2=2400,
         plan="Standard", installed="2026-05-28", live=False, health=0.88),
    dict(id="arges-04", name="Ferma Bascov", owner="Bascov Ferme SRL",
         region="Argeș", town="Bascov", lat=44.88, lon=24.83,
         species="Dairy cattle", herd=420, house_m2=3100,
         plan="Standard", installed="2026-07-19", live=False, health=0.91),
]

FAULTS = ("VENT_FAULT", "HEAT", "PIT_GAS", "FEED_OUT")


def farm_seed(farm_id: str) -> int:
    """Stable per-farm RNG seed.

    NOT hash(): Python salts str hashing per process (PYTHONHASHSEED), so
    hash(farm_id) produced a different fleet on every run — which made the
    validation AUC wander between invocations and quietly turned the one
    number we intended to quote into a number we could not reproduce.
    """
    return zlib.crc32(farm_id.encode()) & 0xFFFFFFFF


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _doc_id(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H")          # hourly, lexicographically sorted


def simulate(farm: dict, days: int, end: datetime, rng: random.Random):
    """Hourly telemetry + the events those readings would have raised.

    Ammonia is modelled as a stock with a production rate and a ventilation
    time constant: dNH3/dt = prod - NH3/tau. That single line is what makes
    the whole prediction story honest — under a healthy programme tau is ~2 h
    and the house settles around 12-19 ppm; when ventilation fails tau jumps
    to ~22 h and the stock climbs several ppm per hour, crossing 25 long
    before it crosses 50. The model gets hours of warning because the physics
    gives hours of warning, not because the generator leaked the label.
    """
    hours = days * 24
    start = end - timedelta(hours=hours - 1)

    base_t = {"Ilfov": 21.0, "Constanța": 23.0, "Argeș": 19.5}[farm["region"]]
    density = farm["herd"] / max(farm["house_m2"], 1)      # animals per m²
    nh3_prod = 5.4 + 1.9 * min(density / 14.0, 1.6)        # ppm produced / h

    # Schedule faults up front so every incident has a build-up to be
    # predicted from. HEAT is pinned to daylight — a heat event at 04:00 is
    # not a thing, and letting one happen would teach the model nonsense.
    faults: dict[int, tuple[str, int]] = {}
    n_faults = max(6, int(days / 30.0 * (1.0 - farm["health"]) * 110))
    for _ in range(n_faults):
        kind = rng.choice(FAULTS)
        for _try in range(12):
            at = rng.randint(WINDOW_H + 6, hours - 12)
            if kind != "HEAT" or 9 <= (start + timedelta(hours=at)).hour <= 15:
                break
        dur = {"VENT_FAULT": (7, 16), "HEAT": (5, 9),
               "PIT_GAS": (4, 8), "FEED_OUT": (13, 20)}[kind]
        faults[at] = (kind, rng.randint(*dur))

    # The correlated regional episode: both Ilfov farms degrade together in
    # the final day. This is the only scripted part, and it is scripted
    # because the regional layer is the thing being demonstrated.
    #
    # Petrești is left mid-build-up at "now" on purpose. A console where every
    # farm reads 3% risk demonstrates storage, not prediction — the whole
    # claim is that the fleet model calls an incident while the house is still
    # inside normal limits and nothing has alarmed yet. Străjer's episode is
    # scheduled to RESOLVE before now, because Străjer is the farm the live
    # Pi node drives and it should look healthy on stage.
    scripted_feed = -1
    if farm["id"] == "ilfov-03":
        faults[hours - 20] = ("FEED_OUT", 19)
        faults[hours - 3] = ("VENT_FAULT", 26)     # still climbing at "now"
        scripted_feed = hours - 20
    elif farm["id"] == "strajer-01":
        faults[hours - 22] = ("VENT_FAULT", 9)     # resolved well before "now"
        faults[hours - 20] = ("FEED_OUT", 12)
        scripted_feed = hours - 20

    nh3 = 11.0 + rng.uniform(-2, 2)
    gas = 170.0 + rng.uniform(-25, 25)
    water, food = 88.0, 84.0
    active: dict[str, dict] = {}
    hist, events = [], []

    for i in range(hours):
        t = start + timedelta(hours=i)
        h = t.hour
        if i in faults:
            kind, dur = faults[i]
            active[kind] = {"left": dur, "total": dur}
            if i == scripted_feed:
                # depletion is ~1.35 %/h, so a scripted feed-out that begins
                # just after a top-up would end 19 h later still at ~69 % and
                # the regional episode silently would not happen
                food = 34.0

        def age(kind: str) -> float:
            """Hours since this fault began; 0 when it isn't running."""
            a = active.get(kind)
            return 0.0 if not a else float(a["total"] - a["left"])

        vent_fault = "VENT_FAULT" in active
        heat = "HEAT" in active
        pit = "PIT_GAS" in active
        feed_out = "FEED_OUT" in active

        # ── temperature: the diurnal curve plus what the farm can't shed ──
        diurnal = 5.4 * math.sin(2 * math.pi * (h - 15) / 24.0)
        temp = base_t + diurnal + rng.gauss(0, 0.55)
        if heat:
            temp += 12.0 * min(1.0, (age("HEAT") + 0.5) / 3.5)   # ramps over ~3.5 h
        if vent_fault:
            temp += 2.2

        hum = 68.0 - 1.15 * (temp - base_t) + rng.gauss(0, 3.0)
        hum = max(35.0, min(96.0, hum))

        # ── ammonia: a stock, not a reading ───────────────────────────────
        tau = 2.0 if 7 <= h <= 20 else 3.2       # day programme ventilates harder
        if temp > 30:
            tau *= 0.8                            # fans ramp on heat
        if vent_fault:
            tau = 22.0
        prod = nh3_prod * (1.0 + 0.011 * max(0.0, hum - 62))
        nh3 += prod - nh3 / tau
        nh3 = max(2.0, nh3 + rng.gauss(0, 0.35))

        # ── methane from the manure pit ───────────────────────────────────
        target = 175.0 + 55.0 * (1 if 6 <= h <= 9 else 0)   # morning scraping
        if pit:
            target = 430.0 + 95.0 * min(1.0, (age("PIT_GAS") + 0.5) / 3.0)
        gas += (target - gas) * 0.22 + rng.gauss(0, 9)
        gas = max(90.0, gas)

        # ── consumables ───────────────────────────────────────────────────
        water -= rng.uniform(1.6, 2.6)
        food -= rng.uniform(0.9, 1.8)
        # a feed-out IS the refill not happening — it must block the top-up,
        # not slow the animals down
        if not feed_out and food < 22 and rng.random() < 0.75:
            food = rng.uniform(88, 97)
            events.append((t, "EVT|0|hall|FOOD_REFILLED|0|INFO"))
        if water < 18 and rng.random() < 0.85:
            water = rng.uniform(90, 98)
            events.append((t, "EVT|0|hall|WATER_REFILLED|0|INFO"))
        water, food = max(0.0, water), max(0.0, food)

        s = {"ts": _iso(t), "nh3": round(nh3, 1), "temp": round(temp, 1),
             "hum": round(hum, 1), "gas": round(gas), "water": round(water),
             "food": round(food),
             "mode": "NIGHT" if (h >= 21 or h < 6) else "DAY",
             "fault": next((k for k in FAULTS if k in active), "")}
        if s["gas"] >= 700 or s["nh3"] >= 50 or s["temp"] >= 38:
            s["mode"] = "EMERGENCY"
        hist.append(s)

        for k in list(active):
            active[k]["left"] -= 1
            if active[k]["left"] <= 0:
                del active[k]

        # ── the events those readings would have raised on the node ───────
        prev = hist[-2] if len(hist) > 1 else s
        for metric, key, warn, crit in (("nh3", "NH3", 25, 50),
                                        ("temp", "TEMP", 32, 38),
                                        ("gas", "GAS", 450, 700)):
            if prev[metric] < crit <= s[metric]:
                events.append((t, f"EVT|0|hall|{key}_CRITICAL|{s[metric]}|EMERG"))
            elif prev[metric] < warn <= s[metric]:
                events.append((t, f"EVT|0|hall|{key}_HIGH|{s[metric]}|ALERT"))
            elif s[metric] < warn <= prev[metric]:
                events.append((t, f"EVT|0|hall|{key}_CLEARED|{s[metric]}|INFO"))
        if prev["food"] >= 20 > s["food"]:
            events.append((t, f"EVT|0|hall|FOOD_LOW|{s['food']}|ALERT"))
        if prev["water"] >= 20 > s["water"]:
            events.append((t, f"EVT|0|hall|WATER_LOW|{s['water']}|ALERT"))
        # Birds vocalise when they cannot reach feed, or when the house is
        # hot and unventilated. The previous condition (vent_fault AND
        # hum > 82) was unsatisfiable by construction, since a vent fault
        # raises temp and hum falls with temp — so this event never fired and
        # the cross-farm disease pattern had nothing to correlate on.
        distress = (feed_out and food < 24) or (vent_fault and temp > 30)
        if distress and rng.random() < 0.22:
            events.append((t, "EVT|0|hall|DISTRESS_SOUND|1|ALERT"))
        if rng.random() < 0.004:
            events.append((t, "SEC|REPLAY_REJECTED|COUNTER_REUSE"))
        if rng.random() < 0.002:
            events.append((t, "EVT|0|field|INTRUDER|1|ALERT"))

    return hist, events


def daily_rollup(hist: list[dict]) -> dict[str, dict]:
    days: dict[str, dict] = {}
    for s in hist:
        d = s["ts"][:10]
        r = days.setdefault(d, {"date": d, "n": 0, "nh3_sum": 0.0, "nh3_max": 0.0,
                                "temp_sum": 0.0, "temp_max": -99.0, "gas_max": 0.0,
                                "alerts": 0, "vent_hours": 0})
        r["n"] += 1
        r["nh3_sum"] += s["nh3"]
        r["nh3_max"] = max(r["nh3_max"], s["nh3"])
        r["temp_sum"] += s["temp"]
        r["temp_max"] = max(r["temp_max"], s["temp"])
        r["gas_max"] = max(r["gas_max"], s["gas"])
        if label_incident(s):
            r["alerts"] += 1
        if s["nh3"] > 18 or s["temp"] > 28:
            r["vent_hours"] += 1
    for r in days.values():
        n = max(r.pop("n"), 1)
        r["nh3_avg"] = round(r.pop("nh3_sum") / n, 1)
        r["temp_avg"] = round(r.pop("temp_sum") / n, 1)
        r["nh3_max"] = round(r["nh3_max"], 1)
        r["temp_max"] = round(r["temp_max"], 1)
        # ventilating on a forecast instead of on an alarm is the saving
        r["kwh_saved"] = round(r["vent_hours"] * 0.42, 1)
    return days


def seed(days: int = 30, wipe: bool = False, verbose: bool = True):
    store = open_store()
    if wipe and getattr(store, "kind", "") == "local":
        store.db.clear()
        store._dirty = True
        store._flush(force=True)

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    series, index = [], []

    for farm in FARMS:
        rng = random.Random(farm_seed(farm["id"]))
        hist, events = simulate(farm, days, end, rng)
        series.append(hist)
        last = hist[-1]

        writes = [(f"farms/{farm['id']}/telemetry/{_doc_id(datetime.strptime(s['ts'], '%Y-%m-%dT%H:%M:%SZ'))}",
                   s) for s in hist]
        for d, r in daily_rollup(hist).items():
            writes.append((f"farms/{farm['id']}/daily/{d}", r))
        for n, (t, raw) in enumerate(events):
            sev = raw.split("|")[5] if raw.startswith("EVT|") and len(raw.split("|")) > 5 \
                else ("SEC" if raw.startswith("SEC|") else "INFO")
            writes.append((f"farms/{farm['id']}/events/{_doc_id(t)}-{n:04d}",
                           {"ts": _iso(t), "raw": raw, "sev": sev,
                            "zone": raw.split("|")[2] if raw.startswith("EVT|") else "ctrl",
                            "type": raw.split("|")[3] if raw.startswith("EVT|")
                                    else raw.split("|")[1]}))

        alerts24 = sum(1 for s in hist[-24:] if label_incident(s))
        doc = {k: v for k, v in farm.items() if k not in ("live", "health")}
        doc.update(
            farm_id=farm["id"], gateway="BioGuard GW-1 (Raspberry Pi)",
            firmware="1.4.2-signed", is_live_node=farm["live"],
            last_seen=last["ts"], mode=last["mode"], online=True,
            live={k: last[k] for k in ("nh3", "temp", "hum", "gas", "water", "food")},
            alerts_24h=alerts24, samples=len(hist), history_days=days,
            updated_at=_iso(end))
        writes.append((f"farms/{farm['id']}", doc))
        index.append({"id": farm["id"], "name": farm["name"],
                      "region": farm["region"], "species": farm["species"],
                      "herd": farm["herd"]})

        store.commit(writes)
        if verbose:
            print(f"  {farm['id']:<14} {len(hist):>4} samples  "
                  f"{len(events):>3} events  {alerts24} alerts/24h  "
                  f"-> {len(writes)} docs")

    # ── fit the fleet model on everything above ───────────────────────────
    X, y = build_dataset(series)
    model = RiskModel.train(X, y)
    store.set_doc("fleet/model", model.to_doc(), merge=False)

    # ── derive risk ON WRITE, not on read ─────────────────────────────────
    # Any client — this console, the Flutter app talking to Firestore
    # directly, a vet's browser — should be able to read a farm's risk with
    # one document get. Recomputing an 11-feature model per reader means the
    # phone needs the weights, the history and the feature code; storing the
    # derived state next to the raw state means it needs none of them.
    scored, patches = [], []
    for farm, hist in zip(FARMS, series):
        win = hist[-WINDOW_H:]
        x = featurize(win, _hour_of(win[-1]["ts"]))
        cut = hist[-24:]
        markers = sorted({m for s_ in cut for m in (
            (["NH3_CRITICAL"] if s_["nh3"] >= 50 else
             ["NH3_HIGH"] if s_["nh3"] >= 25 else []) +
            (["FOOD_LOW"] if s_["food"] < 20 else []) +
            (["WATER_LOW"] if s_["water"] < 20 else []) +
            (["DISTRESS_SOUND"] if s_.get("fault") == "VENT_FAULT"
             and s_["nh3"] >= 25 else []))})
        risk = round(100 * model.predict(x), 1)
        patches.append((f"farms/{farm['id']}", {
            "risk_pct": risk, "risk_drivers": model.explain(x),
            "forecast": forecast(hist), "markers": markers,
            "scored_at": _iso(end)}))
        scored.append({"_id": farm["id"], "name": farm["name"],
                       "region": farm["region"], "risk": risk,
                       "markers": markers})
    store.commit(patches)

    regions = regional_signal(scored)
    store.set_doc("fleet/regions", {"signals": regions,
                                    "updated_at": _iso(end)}, merge=False)

    store.set_doc("fleet/summary", {
        "farms": len(FARMS), "regions": len({f["region"] for f in FARMS}),
        "animals": sum(f["herd"] for f in FARMS),
        "samples": sum(len(h) for h in series),
        "history_days": days, "index": index,
        "at_risk": len([f for f in scored if f["risk"] >= 35]),
        "regions_flagged": len(regions),
        "updated_at": _iso(end)}, merge=False)

    store.flush()          # fleet/model must survive the throttle window

    if verbose:
        print(f"\n  fleet model: {model.meta['samples']} windows, "
              f"{model.meta['incidents']} positive, AUC {model.meta['auc']}")
        print(f"  backend: {getattr(store, 'kind', '?')} "
              f"({getattr(store, 'project_id', '')})")
    return model, series


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--wipe", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    print(f"seeding {len(FARMS)} farms x {args.days} days …")
    seed(args.days, args.wipe)
    print(f"done in {time.time()-t0:.1f}s")
