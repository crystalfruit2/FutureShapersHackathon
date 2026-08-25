# Bio Guard (scenario: Ferma Străjer) — FutureShapers Hackathon 2026 (Honeywell, Bucharest)

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
down: SIM|<name>=<value>                        (demo injection for missing sensors)
      CMD|<ctr>|<mac>|<ACTION>                  mac = CRC8("<ctr>|<ACTION>" then secret "STRAJER26")
```

## Dashboard (`dashboard/`, laptop)
```
pip3 install flask pyserial
python3 dashboard/app.py --fake                    # no Arduino needed — build UI now
python3 dashboard/app.py --port /dev/cu.usbmodem*  # against real hardware
```
→ http://localhost:5000 — floor plan (4 zones), live telemetry with SIM badges,
event log, energy-saved tally, sim sliders (NH₃/flame/motion = the "keyboard
simulation"), **⚔ REPLAY ATTACK button** (the live cyber demo), chained-log verify.
Verified working in fake mode incl. replay rejection.

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
