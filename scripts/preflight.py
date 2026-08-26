#!/usr/bin/env python3
"""
BioGuard stage pre-flight — read-only, ~10 seconds, changes nothing.

    python3 scripts/preflight.py

Answers the only question that matters right before a demo with one attempt:
"if I run the show now, what will actually happen?" Every check that can go
wrong prints the exact command that fixes it, because the failure modes here
are all silent — a railed gas sensor, a channel a test sequence still holds, a
water probe reading zero. None of them announce themselves; they just make the
demo behave differently than rehearsal.
"""
import json, sys, urllib.request

BRIDGE = "http://localhost:5001"
GAS_LIMIT = 700          # a.u. — GAS_CRITICAL -> EMERGENCY -> the 112 dispatch call
GAS_CLEAR = 400          # a.u. — GAS_CLEARED -> "situation contained"
RAW_PER_AU = 4095 / 1023 # the board's raw ADC counts per a.u.
OK, WARN, BAD = "\033[32m✓\033[0m", "\033[33m!\033[0m", "\033[31m✗\033[0m"
problems = []   # blocking: the show misbehaves if you start now
notes = []      # deliberate choices worth restating out loud

def get(path, timeout=4):
    with urllib.request.urlopen(BRIDGE + path, timeout=timeout) as r:
        return json.loads(r.read().decode())

def head(path, timeout=4):
    req = urllib.request.Request(BRIDGE + path)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")

def fail(msg, fix):
    print(f"{BAD} {msg}")
    print(f"     → {fix}")
    problems.append(msg)

def warn(msg, fix):
    print(f"{WARN} {msg}")
    print(f"     → {fix}")
    problems.append(msg)

def note(msg, detail=""):
    print(f"{WARN} {msg}")
    if detail:
        print(f"     {detail}")
    notes.append(msg)

print("\n── BioGuard pre-flight ─────────────────────────────────────────\n")

# 1. bridge
try:
    get("/api/board")
    print(f"{OK} bridge answering on {BRIDGE}")
except Exception as e:
    print(f"{BAD} bridge not answering on {BRIDGE} ({e})")
    print("     → python3 dashboard/app.py --esp")
    sys.exit(1)

# 2. the web app is served with the base href it needs, or it opens blank
try:
    _, html = head("/app/")
    if 'base href="/app/"' in html:
        print(f"{OK} web app served with the right base href")
    else:
        fail("web app will open as a BLANK page (wrong base href)",
             "cd flutter_app && flutter build web --release --base-href /app/")
except Exception as e:
    fail(f"web app not served at {BRIDGE}/app/ ({e})",
         "cd flutter_app && flutter build web --release --base-href /app/")

# 3. the board
b = get("/api/board")
if not b["connected"]:
    fail(f"sensor board NOT connected ({b['url']})",
         "sudo scripts/bioguard-net.sh on   (then wait ~3 s, the poller retries every second)")
    print("\n   Everything below is about the board — rerun once it is linked.\n")
    sys.exit(1)

print(f"{OK} board live at {b['url']}")
print(f"     raw       {json.dumps(b['raw'])}")
print(f"     converted {' · '.join(f'{k}={v}' for k, v in sorted(b['converted'].items()))}")

conv, raw = b["converted"], b["raw"]

# 4. pins — a test sequence silently keeps the channels it drove
pinned = set(b["pinned"])
if "gas" in pinned:
    warn("gas is held by a simulator pin — the REAL sensor cannot trigger the alarm",
         "release it: click RELEASE SIM PINS → BOARD on the bench, or "
         "curl -X POST -H 'Content-Type: application/json' -d '{\"line\":\"SIM|gas=\"}' " + BRIDGE + "/raw")
elif pinned:
    note(f"pinned to simulated values: {', '.join(sorted(pinned))} — board ignored there",
         "intentional if you pinned them yourself; RELEASE SIM PINS → BOARD hands them back")

# 5. the gas alarm — the one beat that runs off real hardware
gas = conv.get("gas")
if gas is None:
    warn("board is not reporting gas — the alarm will run off the simulator",
         "check the MQ sensor's wiring; the demo still works, just not off real gas")
elif gas >= GAS_LIMIT:
    fail(f"gas RESTING at {gas} a.u. — already over the {GAS_LIMIT} limit (raw {raw.get('gas')})",
         "the show would open in EMERGENCY. MQ sensors rail while warming up: power the board "
         "and wait 3-5 min, then rerun. If it stays railed, pin it safe for the demo: "
         "curl -X POST -H 'Content-Type: application/json' -d '{\"line\":\"SIM|gas=120\"}' " + BRIDGE + "/raw")
elif gas >= GAS_LIMIT * 0.8:
    warn(f"gas resting at {gas} a.u. — only {GAS_LIMIT - gas} below the limit, a hair trigger",
         "fine if you want it to fire easily; risky if you need calm airtime first. Let it warm up longer.")
elif gas >= 200:
    print(f"{OK} gas resting {gas} a.u. — {GAS_LIMIT - gas} of headroom "
          f"(needs raw {int(GAS_LIMIT * RAW_PER_AU)}+ to alarm)")
else:
    warn(f"gas resting low at {gas} a.u. — needs {GAS_LIMIT - gas} of rise to alarm",
         "hold the source closer / longer, or rehearse with the bench GAS RAMP button")

# 5b. the CLOSING beat. EMERGENCY lifts only under 400 a.u. — if the sensor
#     RESTS above that, the farm can enter EMERGENCY and never leave, and
#     "situation contained" never plays. Rehearsal hides this: the simulator
#     rests at 120.
if gas is not None and GAS_CLEAR <= gas < GAS_LIMIT:
    warn(f"gas rests at {gas} a.u., ABOVE the {GAS_CLEAR} clear threshold — once it alarms it "
         f"will NOT clear itself, so 'situation contained' never fires",
         f"either ventilate until it drops under raw {int(GAS_CLEAR * RAW_PER_AU)}, or close the "
         "beat deliberately: curl -X POST -H 'Content-Type: application/json' "
         "-d '{\"line\":\"SIM|gas=120\"}' " + BRIDGE + "/raw")
elif gas is not None and gas < GAS_CLEAR:
    print(f"{OK} gas rests under the {GAS_CLEAR} clear threshold — the contained beat will fire")

# 6. channels the board is not covering — they stay simulated, which is sanctioned
missing = [k for k in ("temperature", "humidity", "water_level", "sound_level") if raw.get(k) is None]
if missing:
    print(f"{WARN} board sends null for: {', '.join(missing)} — those stay simulated (sanctioned)")

# 7. water reading zero makes the analyst shout, every 20 s, on stage
water = conv.get("water")
if water is not None and water <= 1 and "water" not in pinned:
    warn(f"water reads {water}% (raw {raw.get('water_level')}) — the analyst will keep firing "
         "'STUCK water frozen at 0 — disconnected probe' into AI FINDINGS",
         "put the probe in water, or pin it before the show: curl -X POST -H 'Content-Type: application/json' "
         "-d '{\"line\":\"SIM|water=72\"}' " + BRIDGE + "/raw")

# 8. don't walk on stage already in EMERGENCY
try:
    import urllib.request as u
    with u.urlopen(BRIDGE + "/stream", timeout=6) as r:
        for _ in range(40):
            line = r.readline().decode("utf-8", "replace")
            if line.startswith("data:"):
                d = json.loads(line[5:])
                if d.get("type") == "hello":
                    mode = d["state"]["mode"]
                    if mode == "EMERGENCY":
                        fail("the farm is ALREADY in EMERGENCY",
                             "clear it before the show: bench CLEAR buttons, or drop gas below 400")
                    else:
                        print(f"{OK} farm mode is {mode} — a clean start")
                    break
except Exception:
    pass

print()
if problems:
    print(f"\033[31m{len(problems)} thing(s) to fix before you start.\033[0m\n")
    sys.exit(1)
tail = f" ({len(notes)} deliberate choice(s) noted above.)" if notes else ""
print(f"\033[32mReady. Bench :5001 · app :5001/app/ · dispatch :5001/fire\033[0m{tail}\n")
