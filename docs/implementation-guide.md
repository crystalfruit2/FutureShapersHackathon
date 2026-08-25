---
tags:
  - project
  - hackathon
  - guide
date: 2026-08-25
---

# Implementation Guide — step by step

## ⚠️ 25.08 UPDATE — the 5 extra sensors are NOT provided
Organizers confirmed on-site: no MQ4, no MQ135, no PIR, no KY-026 flame, no KY-020 tilt. Sanctioned workaround: simulate via potentiometer or keyboard input. Substitution map (firmware already implements it — every channel can be HARDWARE or SIM, same code path):

| Missing | Replacement | Notes |
|---|---|---|
| MQ4 (pit methane) | potentiometer on A0 | knob = gas level; perfectly controllable demo; say honestly "production = MQ4/Manning EC-FX" |
| MQ135 (hall ammonia) | `SIM|nh3=<val>` from dashboard slider | keyboard injection, organizer-sanctioned |
| PIR (motion) | HC-SR04 ultrasonic as presence detector | matches the pen-plan (night robbery watch); silo-level role dropped |
| KY-026 flame | `SIM|flame=1` (optional: photoresistor as light-spike detector) | A2 defaults to thermistor instead — dual-temp spoof check is worth more (cyber points) |
| KY-020 tilt | push button wired as cabinet door-contact switch on D2 | real BMS cabinets use door contacts — pitch it as MORE realistic |

Pitch line: "Our sensor abstraction treats hardware and injected channels identically — which is also our spoofing test harness." Turns the handicap into a cyber feature.

### Pin map — Plan A′ (revised for no-extra-sensors)
| Pin | Function | | Pin | Function |
|---|---|---|---|---|
| D0/D1 | ⛔ RESERVED — serial dashboard | | D9 | buzzer (bit-banged, no tone() if IR in use) |
| D2 | cabinet door-contact button (tamper) | | D10 | red alarm LED |
| D3 | IR receiver (attacker's channel, optional) | | D11/D12 | HC-SR04 trig/echo (night motion) |
| D4 | DHT11 | | D13 | green/status (onboard) |
| D5 | relay (gas valve / heater cut) | | A0 | potentiometer = "MQ4" gas |
| D6 | servo (vent flap) | | A1 | water level sensor |
| D7 | fan via transistor | | A2 | thermistor (2nd temp channel → spoof check) |
| D8 | sound sensor (digital out) | | A3 | 4-button PIN ladder |
| | | | A4/A5 | I2C LCD (if backpack; else 74HC595) |
| SIM-only channels | NH3 (`nh3`), flame (`flame`) — injected from dashboard | | | |

The same machine powers every pitch option (church / non-religious option / dorm fallback) — only zone labels, the cardboard model, and the narration change. Build once, skin at the end.

## 0. What you need (gather Tuesday morning)
- [ ] The kit: Arduino UNO R3, breadboards, jumper M-M/M-F, LCD1602 (**check: does it have an I2C backpack? changes everything below**), 4x4 keypad, IR remote + receiver, HC-SR04, SG90 servo, DC fan/motor (+ driver transistor or L293D?), relay module (**check: 1-channel or 2?**), buzzer, DHT11, photoresistor, LEDs + resistors, 7-seg, **power supply module for breadboard** (the MB102-style one — critical)
- [ ] The 5 extra sensors: MQ4, air quality, PIR, flame, tilt KY-020
- [ ] A laptop with Arduino IDE + Python 3 (`pip install pyserial flask`)
- [ ] USB cable + a spare if possible
- [ ] Cardboard, scissors/cutter, tape, markers (ask organizers), phone for the backup video
- [ ] Ask mentors casually: spare I2C LCD backpack? second UNO? (either one relieves the pin famine)

## 1. FIRST HOUR — three things before anyone wires anything
1. **Power the MQ4 immediately** and leave it warming the entire session (needs 24–48h burn-in ideally, ≥10 min minimum; report "ratio over clean-air baseline", never absolute ppm — say that honestly in the pitch, Honeywell engineers respect calibration honesty).
2. **Inventory the kit** against the list above — the I2C-LCD and relay-channel questions decide the pin map.
3. **Write the pin map on paper and tape it to the table.** Nobody wires outside the map. Teams lose entire hours to pin conflicts discovered live.

### Pin map — Plan A (SUPERSEDED by Plan A′ above — kept for reference)
The full 4x4 keypad eats 8 pins and the UNO simply cannot fit keypad + all sensors + all actuators (we counted). A resistor-ladder button pad (4 push buttons + kit resistors on ONE analog pin) keeps real PIN auth and frees 7 pins:

| Pin | Function | | Pin | Function |
|---|---|---|---|---|
| D0/D1 | ⛔ RESERVED — serial dashboard | | D9 | red alarm LEDs |
| D2 | PIR (interrupt) | | D10 | green/status LEDs |
| D3 | IR receiver (attacker's channel!) | | D11/D12 | HC-SR04 trig/echo (`pulseIn` WITH timeout) |
| D4 | DHT11 | | D13 | onboard status |
| D5 | relay (heater/gas valve/"mains") | | A0 | MQ4 (analog) |
| D6 | servo (vent/door) | | A1 | air quality (analog) |
| D7 | fan via transistor | | A2 | photoresistor |
| D8 | tilt KY-020 (debounced!) | | A3 | 4-button PIN ladder |
| — | buzzer → share D13 or swap with 7-seg plans | | A4/A5 | I2C LCD |

Plan B (no I2C backpack): demote the LCD — the laptop dashboard becomes the main display, LCD dropped or status-only on 6 pins, sacrifice ultrasonic. Plan C (mentor lends I2C backpack + 2-ch relay): fan moves to relay ch2, D7 freed for buzzer.

⚠️ Timer traps: `tone()` and the IRremote library both want Timer2 — use a recent IRremote with timer override, or bit-bang the buzzer. Servo (Timer1) + IRremote coexist fine.
⚠️ Power: MQ4 heater (~150 mA) + servo spikes + relay coil from USB = brownout resets mid-demo. **All actuators + gas-sensor heaters on the breadboard supply module; UNO powers logic only; grounds tied together.**

## 2. Firmware architecture (write it this way from line 1)
- **One non-blocking loop** — `millis()`-based cooperative scheduler, zero `delay()` calls. Every feature is a small task polled with its own interval (DHT max once/2 s; MQ4/air every 500 ms; buttons/tilt every 20 ms with N-consistent-reads debounce).
- **One mode state machine**: `NORMAL → ARMED → ALERT → EMERGENCY` (+ `LOCKDOWN` after brute-force). All rules route through it; **life-safety events override everything** — say this in the pitch, it's fire-code thinking.
- **Serial protocol** (115200, newline-delimited, `F()` macros to keep strings in flash — no ArduinoJson on the UNO):
  - Up: `EVT|<ms>|<zone>|<sensor>|<value>|<severity>` and `STATE|<mode>|<flags>`
  - Down: `CMD|<counter>|<mac>|<action>` — counter must increase; `mac = XOR/CRC8(secret, counter, action)`. Wrong/stale → `SEC|REPLAY_REJECTED` event. This 20-line check IS the live cyber demo.
- **EEPROM**: (a) config + mode survives power-cycle (fail-secure: reboots into ARMED), (b) failed-PIN counter survives reboot ("you can't reset the lockout by power-cycling — we log it instead"), (c) **chained audit log**: ring of 8-byte records, each CRC8 chained over the previous record's CRC — dashboard "Verify log" walks the chain; corrupt one byte → chain visibly breaks at that record.
- **Graceful degradation**: DHT checksum-fail / ultrasonic timeout ⇒ mark sensor OFFLINE, keep running in degraded mode, auto-recover. Plus AVR watchdog + a hidden "freeze" test button → 2 s recovery from EEPROM. This is the most Honeywell 30 seconds you can perform.

## 3. Laptop dashboard (the "supervisory layer" — build in parallel, ~2–3 h)
Python: `pyserial` reader thread → Flask + server-sent events → one HTML page: floor-plan div per zone (color by state), scrolling event log with severity colors, live sensor tiles, buttons that send `CMD` lines (Arm/Disarm/Setpoint/Verify-log/Ack). Keep it one file, no framework. Fallback if time collapses: Serial Studio or even a formatted terminal tail — but the floor plan is worth fighting for; it turns "student demo" into "miniature BMS". Vocabulary on screen: "Supervisory Dashboard", zones, severity levels.

## 4. Build order (hour by hour)
**Tue 10–12:** kit inventory + pin map + MQ4 warming (0:00–0:30) → scaffold skeleton: scheduler + state machine + serial EVT stream + one sensor (PIR) + one output (LED) end-to-end to dashboard (0:30–2:00). *Milestone: an event travels sensor → UNO → laptop screen.*
**Tue 13–16:** add sensors one at a time, each: standalone test (2 min) → integrate → see it on dashboard. Order: DHT → relay → flame → MQ4(baseline code) → tilt → buzzer → servo → fan → photoresistor → air quality → ultrasonic → PIN ladder. Then PIN auth + lockout. *Milestone: all four objectives demonstrable crudely.*
**Wed 10–12:** cyber layer (command MAC + replay rejection + audit log + verify/corrupt demo) + graceful-degradation + watchdog. Cardboard model built in parallel by story-lead (zones labeled to match dashboard).
**Wed 13–16:** **FEATURE FREEZE 14:00 — hard.** 14:00–15:00 script the demo scene by scene, assign narrator vs operator. 15:00–16:00 rehearse the EXACT run ≥3× (target 5 incl. evening), **record the backup video twice**, photograph the wiring, rehearse from cold boot (unplug → replug → still armed, log intact).

## 5. The demo script skeleton (12 min — map slides 1:1 to their 7 rubric items)
Hook (0:30) → live scenario demo, 4 continuous scenes = the 4 objectives (4:00) → optional-feature highlights incl. one attack replayed by a teammate-as-attacker and visibly rejected (1:30) → steps-to-success as a picture (1:30) → challenges as problem→tried→fixed ×3 (1:30) → architecture, one slide (1:00) → experience: ONE specific named moment, no adjectives (1:00) → lessons ×3 (one technical, one teamwork) + callback close (1:00). Print a **one-page spec sheet** (block diagram, pin map, threat model) and hand it to the jury.
Cyber language rule: never say "encrypted"/"secure" loosely — say "authenticated with a rolling counter; real hardening would need a crypto-capable MCU — here's what we'd do with two more weeks." Jury sells OT cybersecurity; honesty scores, overclaiming kills.

## 6. Per-pitch demo mapping
*(the only part that changes per story — see [[Projects/FutureShapers-Hackathon/pitch-scenario|pitch-scenario]] for narratives)*
- **Straja (wooden church):** zones = nave/altar/tower; relay = heating cut; servo = vestry door; tilt ON the icon frame (juror lifts icon → alarm — THE moment); flame = candle left burning; MQ4 = stove gas; DHT = conservation microclimate = energy story; PIR = off-hours intrusion; cyber = unattended remote site, diocese dashboard.
- **Non-religious flagship:** filled in from today's second brainstorm round — see [[Projects/FutureShapers-Hackathon/pitch-scenario|pitch-scenario]].
- **Dorm (fallback):** as originally scripted — Ana, room 314.
