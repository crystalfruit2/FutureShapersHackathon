---
tags:
  - resource
  - event
  - hackathon
date: 2026-08-24
status: active
event: "[[Resources/futureshapers-camp-2026|FutureShapers Camp 2026]]"
---

# FutureShapers Hackathon — Battle Plan (24–27 Aug 2026)

Brief photo: `hackathon-brief-slide.png`

## The brief (from the only slide we have)
- **Kit:** Arduino UNO R3 CH340 + Bitmi 10171 starter kit, **plus 5 extra sensors:** MQ4 gas, air quality, motion (PIR), fire/flame, tilt KY-020
- **Objectives:** (1) centralized control of appliances/devices, (2) security via motion detection + alerts, (3) energy efficiency via automated lighting/HVAC, (4) **cyber security elements + cyber-secure design**
- **Mandatory:** microcontroller + sensors + relay integration · strategic sensor placement · stable power supply · ≥3 input sources · ≥3 output types · **cyber enhancements**
- **Presentation (10–15 min, Thu 10:00):** live demo · optional-feature highlights · steps to success · challenges · development · experience highlights · lessons learned
- **Working time:** Tue + Wed, 10–12 and 13–16 (10 hours total)

## Concept: "a miniature Honeywell building"
Pitch it as **one node of a scalable Building Management System**, not a toy smart home. Honeywell's actual businesses are building automation, fire & life safety, and OT cybersecurity — the judges ARE these people. A cardboard model building with labeled zones (kitchen / hallway / entrance / control panel) makes "strategic sensor placement" visible and scorable.

**Core architecture: a mode state machine** — HOME / AWAY (armed) / NIGHT / EMERGENCY — driven from a central panel (LCD + keypad + IR remote). Life-safety events override everything (real fire-code priority logic — say this out loud in the demo).

## Four demo scenarios (= the four objectives, in order)
1. **Central control:** keypad + IR remote switch modes; LCD is the dashboard. Relay switches a "mains" appliance.
2. **Energy:** ultrasonic at the door = occupancy counter → occupancy 0 ⇒ lights (LEDs) off; temp sensor → fan = HVAC with hysteresis; photoresistor = daylight harvesting. Show a "power saved" tally on the display.
3. **Security:** AWAY + PIR motion → entry-delay countdown → PIN or alarm. **Tilt sensor on the control panel = tamper detection** (rip the panel off the wall → instant alarm). Clever, visible, uses the weird sensor.
4. **Safety (the emotional peak):** unlit-lighter butane puff on MQ4 / flame sensor → EMERGENCY: buzzer, red flash, servo opens vent/door, fan exhausts, LCD "EVACUATE".

## Cyber = the differentiator (listed twice in the brief; most teams will skip it)
- Two-tier PINs (user disarms, admin configures) = least privilege
- 3 wrong PINs → lockout + escalating delay + alarm = brute-force defense
- Tilt tamper detection = physical security layer
- IR replay protection: require rolling sequence, not single button
- Sensor plausibility cross-checks (flame without temp rise ⇒ "sensor fault?" not blind alarm) = spoofing defense
- Fail-secure: reboot into ARMED, never disarmed
- EEPROM audit log with an "event log" screen
- **One threat-model slide** (spoofing / tampering / replay / DoS → countermeasure each). Honeywell sells OT cybersecurity; this slide wins the room.

## Execution plan (10 hours)
- **Tue 10–12:** end-to-end skeleton FIRST — state machine + LCD + keypad + 1 sensor + 1 output working together. Pin map on paper before any wiring.
- **Tue 13–16:** add sensors one at a time (test standalone → integrate). Non-blocking code only (`millis()`, no `delay()`) — delay-based code makes features fight each other.
- **Wed 10–12:** cyber features + cardboard model + polish.
- **Wed 13–16:** **feature freeze 14:00.** Rehearse full demo 3×. Record a backup video of a perfect run. Photograph the working wiring.
- Traps: servo/fan on the kit's external power module rail (common GND!), never Arduino 5V — brownout resets are the #1 demo killer and "stable power" is literally rubric item 3. Keypad+LCD eat ~14 pins — use I2C LCD if the kit has one; analog pins work as digital.

## Presentation (map slides 1:1 to their 7 rubric items)
Open with a story ("3am, gas leak in a student dorm…"), run the demo as that narrative — one person narrates, one drives hardware. A "mandatory requirements" slide with six literal checkmarks. Close with scalability: this node → cloud BMS (Honeywell Forge shape). Keep a **challenge log from hour 1** — items 4 and 7 of their rubric come from it for free.

## Team roles (4 people)
1. Firmware lead — state machine, owns the single codebase
2. Hardware lead — wiring, pin map, power, physical model
3. Cyber + test lead — cyber features, tries to break the demo
4. Story lead / scribe — slides, challenge log, demo script, rehearsal timing

## Status
- [x] Brief captured + plan drafted (Mon evening)
- [ ] Team aligned on concept + roles
- [ ] Tue skeleton milestone
- [ ] Wed 14:00 freeze + rehearsals + backup video
- [ ] Thu presentation
