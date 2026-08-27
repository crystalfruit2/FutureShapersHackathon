# BioGuard (scenario: Ferma Străjer) — FutureShapers Hackathon 2026 (Honeywell, Bucharest)

> 📚 **Full project documentation for juries & visitors:** [`documentation/`](documentation/README.md)
> — includes [BioGuard-Documentation.pdf](documentation/BioGuard-Documentation.pdf) and screenshots.


Smart livestock-facility supervisory node. Arduino UNO R3 + Bitmi kit.
**25.08 constraint:** the 5 extra sensors (MQ4/MQ135/PIR/flame/tilt) were NOT provided —
we simulate them (potentiometer + dashboard injection), organizer-sanctioned.
Substitution map + revised pin map (Plan A′): `docs/implementation-guide.md`.

## Firmware (`arduino_firmware/`, PlatformIO)
Owned by the firmware lead. Pin map (Plan A′), substitution table, architecture rules
(millis() scheduler, no delay(), mode state machine, serial protocol) are all in
`docs/implementation-guide.md`. The dashboard speaks the protocol below — firmware
must emit/accept exactly these lines:
```
up:   EVT|<ms>|<zone>|<type>|<value>|<sev>     sev: INFO WARN ALERT EMERG
      TEL|gas=512,nh3=12s,t1=24,...,fan=1,relay=1,vent=0,saved_pct=63   (1 Hz; 's' = simulated)
      STATE|<mode>      SEC|<what>      ACK|<ctr>      LOG|<slot>|<type>|<val>|<min>|<OK/BROKEN/EMPTY>
      AI|<kind>|<zone>|<what>|<message>|<sev>   kind: PREDICT DRIFT PLAUS STUCK BASELINE RISK
                                                (emitted by the laptop, never by the firmware)
down: SIM|<name>=<value>                        (demo injection for missing sensors)
      CMD|<ctr>|<mac>|<ACTION>                  mac = HMAC-SHA256(secret "STRAJER26", "<ctr>|<ACTION>")[:8 hex]
```

## Real sensor board (Oleksandr's ESP32) — 26.08

The physical sensors arrived as a standalone board, not GPIO on the Pi: it is a **WiFi AP
`BioGuard`** (password `claude_plan`, **no DHCP**) serving `GET http://192.168.4.1/` →

```json
{"gas": 1548, "temperature": 24.2, "humidity": 51.0, "water_level": 9}
```

`temperature`/`humidity` are floats (or `null` while unwired); `gas`/`water_level` are **raw
0-4095 ADC counts — conversion is our job, server side** (the board's FPU is too slow).
Conversion (identical in `dashboard/app.py` and `pi_node/bioguard_node.py`):
gas → 0-1023 a.u. (keeps the 700 critical limit everywhere) · water_level → 0-100 % ·
temperature → `t1` · humidity → `hum` · sound_level → `snd`, a flag: the level is auto-baselined
to the room (EMA) and only trips above it, so a loud venue does not read as a restless flock. A `null`/missing channel stays simulated per-key and
takes over automatically the moment it appears.

**Connect (laptop, macOS)** — manual IP because there is no DHCP; this drops internet, which
the cloud sink is built to survive (fail-open → LocalStore):

```
networksetup -setairportnetwork en0 BioGuard claude_plan
networksetup -setmanual Wi-Fi 192.168.4.2 255.255.255.0 192.168.4.1
python3 dashboard/app.py --esp                    # default http://192.168.4.1/
networksetup -setdhcp Wi-Fi                       # restore normal WiFi afterwards
```

**Seeing exactly what the board said** — the same object in all three UIs, so they can never
disagree about the hardware: bench card *SENSOR BOARD — RAW JSON*, the app's Controls →
*Sensor board*, or `curl http://localhost:5001/api/board`. It carries the board's own JSON, the
bridge's conversion of it, the live channels and any channel a SIM pin is holding.

⚠️ **A test sequence steals the channels it drives.** `SIM|gas=…` pins `gas`, and a pin outranks
the board — run GAS RAMP or FLAME once and the real board's gas is ignored until you hand it
back. `SIM|gas=` with **no value** releases one channel; the bench button
**RELEASE SIM PINS → BOARD** releases all five (`gas t1 hum water snd`). The board card names any
pinned channel in red, so "why is gas not live?" is answerable at a glance.

`--esp` implies the local state machine (`--fake`), so the 4 real channels ride alongside the
simulated ones — organizer-sanctioned for the sensors we weren't given. Precedence per
channel: **SIM-pinned (sliders / NIST replay) > board > generated** — a rehearsed demo beat can
never be stomped by the live board, and the header shows `board: LIVE gas+hum+t1+water`
(3 missed polls → `board: lost — sim fallback` + a WARN event, demo keeps running).
Note: while the board is live, `water` is board-owned — the REFILL WATER beat needs a
`SIM|water=…` pin first.

**Pi in the loop instead:** give the Pi the static IP (same commands, `wlan0`/`dhcpcd` on
Raspberry Pi OS); `pi_node/bioguard_node.py` now polls the board itself inside its sensor
hooks, so the reflex layer actuates on real data. The laptop then connects to the Pi as
before — but both must sit on the BioGuard AP for that TCP link.

**Phone / Flutter app:** join the `BioGuard` AP, set a manual IP (e.g. `192.168.4.3`,
mask `255.255.255.0`), and point the app's bridge URL (Controls → bridge) at
`http://192.168.4.2:5001`. The Fleet tab keeps working over mobile data since it reads
Firestore directly.

### Stage day — two commands, in this order

```
sudo scripts/bioguard-net.sh on     # Wi-Fi -> board's AP, internet stays on USB Ethernet / iPhone USB
python3 scripts/preflight.py        # read-only, ~10 s: "if I start now, what happens?"
```

`bioguard-net.sh` refuses to run if no second interface is up, rather than taking the internet
down with it; `off` puts Wi-Fi back on DHCP and restores the service order. `preflight.py` checks
the bridge, the web app's base href, the board link, simulator pins, the **gas resting level
against the 700 limit**, null channels, a water probe reading 0, and whether the farm is already
in EMERGENCY — printing the exact fix command for each. Exit code 0 means safe to start.

🔴 **The gas sensor's resting level decides whether the alarm works.** MQ sensors rail near 4095
while warming up — 4095 converts to 1023 a.u., over the 700 limit, so the show would **open in
EMERGENCY**. Power the board 3-5 minutes before the demo and rerun the pre-flight; a resting
value around 1900 raw (475 a.u.) leaves 225 of headroom, which a puff of gas crosses immediately.
If it will not settle, pin it safe (`SIM|gas=120`) and run the alarm off the bench, which is the
rehearsed path anyway.

**The gas ladder, in the units the board actually reports** (`a.u. = raw × 1023/4095`):

| gas | raw ADC | what fires |
|---|---|---|
| rising, forecast crossing ≤ 300 s | — | `AI|PREDICT` WARN → `/fire` **PRE-ALERT**, crew on standby, chime |
| rising, forecast ≤ 90 s | — | PREDICT escalates to ALERT |
| **≥ 700** | **≥ 2802** | `GAS_CRITICAL` → `STATE|EMERGENCY` → **full-screen 112 call** (425 Hz ring, ANSWER), app takeover, relay cut + fan + vent |
| < 400 | < 1602 | `GAS_CLEARED` → **"situation contained"** |

PREDICT also needs a learned baseline (`--baseline`, default 45 s), ≥ 8 samples, a rise of
≥ 14 a.u./min sustained over ≥ 5 samples, and the channel ≥ 2σ above its own baseline. So a slow
approach earns the pre-alert; shoving the source at the sensor jumps straight to the 112 call.

⚠️ **The clear threshold is below a real sensor's resting value.** Alp's board rests at ~492 a.u.
(raw 1968) but EMERGENCY only lifts under 400 — so on real hardware the farm can enter EMERGENCY
and never leave, and the contained beat never plays. The simulator hides this: it rests at 120.
Either ventilate below raw 1602 or close the beat with `SIM|gas=120`. Pre-flight checks this.

Measured end-to-end on the mock board (26.08): raw 3050 → 762 a.u. →
`EVT|0|pit|GAS_CRITICAL|762|EMERG` → `STATE|EMERGENCY`, with the analyst reaching risk 1.00 and
`CH4 critical in 4s` *before* the crossing. `/fire` consumes the same stream, so the 112 dispatch
call rides on that event.

**Rehearsal without the hardware:** `python3 dashboard/mock_board.py` serves the exact same
JSON (incl. `--nulls` for the temp/hum-unwired state) on `:8181` →
`python3 dashboard/app.py --esp http://127.0.0.1:8181/`. `--gas N` pins the raw count so the
alarm beat can be rehearsed to the second (`--gas 3050` crosses the limit; `--gas 1900` rests).

## BioGuard web app — served BY the bridge at `/app/`

```
flutter build web --release --base-href /app/     # ← the --base-href is NOT optional
```

🔴 **Rebuild it any other way and the page comes up blank parchment and nothing else.** Flutter
writes `<base href="/">` by default; every script URL then resolves against the bridge's ROOT, so
`flutter_bootstrap.js` fetches the *dashboard HTML* with a 200 and the engine never starts. There
is no error on screen and no 404 in the log — it looks like the app is broken. (Cost us a debug
round on 26.08.) The app is then at `http://localhost:5001/app/`, same origin as the bridge, so
on web it points at itself and needs no address typed in.

⚠️ **The bridge address field is the BRIDGE, never the sensor board.** `http://192.168.4.1/` is
the ESP32; it serves sensor JSON, not `/stream`, and the app just says "Failed to fetch". On web
the field is filled from the page's own origin and *Use the laptop serving this page* puts it
back one tap. From a phone on the BioGuard AP it is `http://192.168.4.2:5001`.

## Dashboard (`dashboard/`, laptop)
```
pip3 install flask pyserial
python3 dashboard/app.py --fake                    # no Arduino needed — build UI now
python3 dashboard/app.py --port /dev/cu.usbmodem*  # against real hardware
```
→ http://localhost:5001 — floor plan (4 zones), live telemetry with SIM badges,
event log, energy-saved tally, sim sliders (NH₃/flame/motion = the "keyboard
simulation"), **⚔ REPLAY ATTACK button** (the live cyber demo), chained-log verify.
Verified working in fake mode incl. replay rejection.

## AI analyst — Tier 2 (`dashboard/app.py`, no extra deps)
Three layers, and the pitch line that goes with them: **reflex** (firmware, ms, cuts the
valve, needs no network) · **perception** (this analyst, 1 Hz, sees it coming) ·
**language** (Claude, later). The analyst is **advisory only — it never actuates.** No `CMD|`
is ever produced by it; commands still carry the truncated HMAC-SHA256 MAC and the monotonic counter.
Say that out loud in the demo: *a language model cannot open a valve on this farm.*

It reads the same `TEL|` stream everything else reads and emits `AI|` lines back into the
event bus, so the web dashboard **and** the Flutter app both get it for free. Four detectors:

| kind | what it catches | why a fixed threshold can't |
| --- | --- | --- |
| `PREDICT` | EWMA rate-of-rise → time-to-threshold (*"CH₄ +240/min → critical in 1m29s"*) | fires ~60 s **before** the 700 limit — the Suceava anchor |
| `DRIFT` | z-score vs. a baseline learned on site | NH₃ creeping 8→22 ppm never crosses the 25 limit, but it's a failing fan belt |
| `PLAUS` | cross-sensor: flame with no thermal rise · probes disagreeing · extraction running but the gas still climbing | spoofed/faulty input, and a *cyber* finding as much as a safety one |
| `STUCK` | a normally-lively probe frozen while the farm moves | dead probe or **replayed telemetry** |

Guards that keep it honest: a forecast needs a sustained climb **and** a departure from the
channel's own learned noise band, so probe jitter can't invent a crossing; `STUCK` only fires
on probes the baseline saw moving; nothing is learned while the node is in `EMERGENCY`.

```
python3 dashboard/app.py --fake                       # baseline learns in 45 s
python3 dashboard/app.py --fake --baseline 600        # at the venue: 10 min of real "normal"
python3 dashboard/app.py --fake --http-port 5055      # second bench beside a live one
```
AI ANALYST panel = live per-channel trend, ETA and σ, plus RELEARN BASELINE (re-profile
"normal" in *this* room — good demo beat). Two demo sequences in the bench panel:
**AI · SLOW GAS CREEP** (predicted ~60 s before the reflex layer fires) and
**AI · NH₃ DRIFT** (caught while staying under the fixed limit).

## Cloud — Tier 3 (`dashboard/cloud/`, no extra deps)
One node proves the product works; a fleet proves it's a business. The bridge is the farm
**gateway**: it mirrors what the Pi node reports into Firestore under a farm id, so many farms land in
one project and the model gets to learn from all of them at once. Same three-layer line as
above, one layer longer: **reflex** (ms, on the Pi node) · **perception** (1 Hz, on the laptop) ·
**fleet** (hours, in the cloud).

Zero new pip installs — `cryptography` + `requests` were already there, so `store.py` signs
the service-account JWT itself and speaks the Firestore REST API directly. A
`pip install firebase-admin` that has to succeed on venue Wi-Fi is not a dependency we accept.

**With no credentials at all it still runs.** `LocalStore` is a JSON file with the same
interface, the same data, the same model and the same console — it just isn't shared between
machines. Losing the internet costs telemetry *resolution*, never the node and never the demo.

| layer | what the cloud earns that one node can't |
| --- | --- |
| history | 30 days per farm instead of the 45 s baseline the on-site analyst learns |
| fleet model | a new customer inherits the fleet's learned weights on **day one**, before contributing a row of their own |
| regional signal | correlated distress across neighbouring farms — one farm reads its own feed drop as a feeder fault; three farms in one county on one day is a notifiable disease pattern |

The risk model is a hand-rolled logistic regression over an 11-feature, 3-hour window,
predicting an alert-grade incident **6 h ahead**. Honesty guards, because a model demoed on
data invented to flatter it is a lie:
- `seed.py` is a crude barn *simulator*, not a random-number source with the answer baked in —
  ammonia is a stock (`dNH₃/dt = prod − NH₃/τ`) that accumulates and is removed by ventilation,
  so every incident is the END of a physical build-up. That is *why* 6-hour warning is possible.
- training reweights the rare positives to 50/50 to learn them at all, then **shifts the
  log-odds back by the true base rate** at inference — without that correction an obvious
  build-up printed a flat `100%`.
- z-scores are clamped at ±4σ, so a 15-second stage ramp can't extrapolate to a confident
  number with no evidence behind it.
- a forecast is suppressed unless its projected rise clears the channel's own noise, and no
  ETA past 12 h is shown at all.
- **quote the held-out number, not the training AUC.** `validate.py` trains on three farms and
  scores the fourth, which is exactly the claim being made.

```
python3 -m cloud.seed --days 30 --wipe   # 4 farms x 30 d, ~3 300 docs, then trains
python3 -m cloud.validate                # leave-one-farm-out -> mean held-out AUC 0.915
python3 app.py --fake                    # /cloud is now live alongside / and /app/
```

`/cloud` = fleet console: KPI strip, regional banner, a card per farm with its risk, the
model's own per-feature reasons for that risk, the time-to-threshold forecast and a
30-day sparkline; tap a farm for its stored daily history and event log. Buttons retrain on
whatever is actually in the cloud and re-run the held-out validation live.

To point it at a real project (all optional — unset means LocalStore):
```
export BIOGUARD_FIREBASE_KEY=~/.bioguard/service-account.json   # THIS project's key
export BIOGUARD_FARM_ID=strajer-01          # which farm this gateway is
export BIOGUARD_CLOUD=auto                  # on | off | auto
```
Live project is **`bioguard-c75cc`**. The service-account key lives at
`~/.bioguard/service-account.json` (mode 600, deliberately **outside the repo** so it can
never be committed) — never paste its contents anywhere; it holds a private key.
Firestore rules are still Google's test-mode default: **world read+write until 2026-09-25**.
Fine for the hackathon, but if a judge asks about the cloud's security posture, the honest
answer is that device→cloud writes are service-account authenticated while client reads are
currently open, and the fix is a one-line rule change to `allow read: if true; allow write: if false;`.
The Flutter **Fleet** tab reads Firestore *directly* (config already wired in
`lib/firebase_options.dart`), so on a phone over mobile data it needs no laptop in the loop;
if Firebase can't initialise it transparently falls back to the bridge's `/cloud/api/fleet`,
which serves the identical shape. The header always states which one it used — *"via
Firestore"* vs *"via Bridge"* plus the reason — so a silent fallback can never be mistaken
for the real thing on stage.

⚠️ **Two build traps, both cost us time once:**
1. Always `--base-href /app/`. A plain `flutter build web` resets it to `/` and the app
   serves blank at `/app/`.
2. After adding any plugin, `flutter clean` before building. The cached
   `web_plugin_registrant.dart` does **not** regenerate on its own, so `firebase_core`
   silently never registers and every `Firebase.initializeApp()` dies with
   `channel-error … FirebaseCoreHostApi.initializeCore` — which looks like bad config but
   is a stale build.

## Firmware test bench — how we test Oleksandr's firmware (Tue/Wed)
`dashboard/app.py` doubles as the test bench. With the UNO plugged into the laptop:
```
pip3 install flask pyserial
python3 dashboard/app.py            # then open http://localhost:5001
```
1. Top-left ENGINEER panel → pick `/dev/cu.usbmodem*` (mac) / `COM*` (win) → CONNECT.
2. Watch the raw console: every line the firmware prints appears live. Lines that
   don't match the protocol get flagged red `UNPARSED` and counted in the header —
   if `unparsed` ever climbs, the firmware's output format drifted from the contract.
3. Run the canned sequences in order — each one exercises one demo scene:
   GAS RAMP (emergency chain + auto-recover) · CMD+REPLAY+BAD MAC (both rejections
   must appear as SEC| lines) · ARM+INTRUDER · FLAME · AUDIT DUMP (chain must be OK).
4. Type arbitrary/garbage lines in the input box to test firmware input tolerance.
5. `--fake` flag = no hardware needed; same UI, generated data (UI dev + rehearsal).

Note on Vercel: this bench can never run on Vercel — a cloud server has no access to
the USB port on the desk. What can go to Vercel later is the Flutter **web** build in
demo mode (`flutter build web`). The serial side always runs on the laptop.

## Farmer app (`flutter_app/`, Flutter — iOS first, web later)
```
cd flutter_app
flutter run                       # iOS simulator; open ios/Runner.xcworkspace in Xcode for device signing
flutter test && flutter analyze   # protocol contract tests
```
Native farm app: zone cards, human-language activity feed, emergency takeover screen
("3AM alert"), replay-attack + audit-chain verify UI, simulation bench for the missing
sensors. Boots in Demo mode (built-in generator, zero hardware); switch to "Live farm
node" in Controls and point it at the laptop bridge (`dashboard/app.py`) address.
Same codebase builds for web later: `flutter build web`.

## Rules that don't move
- Serial protocol lives in the header comment of `src/main.cpp`. Change it there first.
- D0/D1 belong to the dashboard link. Nobody touches them.
- Actuators + heaters on the MB102 external rail, never Arduino 5V. Common GND.
- Feature freeze Wed 14:00 → 3 rehearsals + backup video (`docs/battle-plan.md`).

Docs mirrored from Alp's vault — edit there, re-copy here. Strategy: `docs/proposal-master.md`.
