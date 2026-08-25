---
tags:
  - project
  - hackathon
date: 2026-08-25
---

# Option B — "Cutia Neagră" (Black Box: a flight recorder for buildings)

**The one-sentence pitch:** *Every airplane has a flight recorder; no building does. Cutia Neagră is a smart-building node whose tamper-proof, hash-chained event log means that after a fire, a gas blast, or a break-in, investigators replay exactly what happened — second by second — and nobody can rewrite the truth.*

## Why this can win (all three anchors VERIFIED)
1. **Rahova, Oct 2025** — 3 dead; residents reported the gas smell **11 days before** the blast; **prosecutors STILL cannot establish the cause**. A tamper-proof sensor log would literally have answered the open question.
2. **Colectiv, 2015** — 64 dead, no fire permit, the investigation took 4+ years, the government fell. Root cause: no evidence trail.
3. **NIS2 is now Romanian law** (GEO 155/2024 + Law 124/2025): incidents legally require 24h warning / 72h notification / final report with timestamped, retrievable logs. **Tamper-evident logging is a legal obligation — we make it a €40 hardware primitive.** Bonus: Bucharest's ~349 red-dot seismic buildings give the tilt sensor a second national story (structural displacement monitoring).
4. Category escape: ~6 rival teams will present reactive smart controllers that differ only in paint. This is **evidence infrastructure** — a different product category. And it's honest flattery: Honeywell's real fire panels already keep event histories investigators pull; "you already ship the log — we made it the hero, and made it cryptographically honest."

## Demo arc (staged as an ordinary Bucharest bloc — where all three anchors converge)
- **Scene 1 — A normal day (discipline: show ALL four objectives here, fast):** keypad arms, IR toggles the relay lamp, photoresistor kills lights at "sunrise" (phone flashlight), DHT11 drives the fan, dashboard mirrors everything. **The 7-seg ticks the log sequence number — the odometer of truth.** Every event appends a hash-chained record.
- **Scene 2 — The night of the incident:** PIR → deadbolt + buzzer; MQ4 (unlit-lighter puff) → relay cuts the gas valve + fan vents + servo damper; flame → full alarm; a knock on the model → tilt logs "structural displacement." A **stopwatch on the 7-seg** freezes each response time (gas cut in 3.2 s — vs Rahova's 11 days).
- **Scene 3 — The investigation (the money scene):** kill power to the whole model — "the building is gone." Reboot only the node. Dashboard **replay mode** re-verifies the chain and scrolls the incident second by second. Then the theatrical peak: a teammate plays the corrupt landlord and edits one log line on the laptop to hide the gas warning → re-verify → **the chain breaks in red at exactly that line.** Line: *"In Rahova, prosecutors still can't say what happened. You can burn the building — you can't burn the truth."*
- **Close:** the node prints/displays a structured **incident packet for responders** (readings timeline, last-known occupancy from PIR, hazards, safest entry) — Crevedia hook: 39 firefighters injured entering blind (verified). Then NIS2 slide: "this log format is what the law now demands."

## Cyber story (strongest of any option)
The tamper-evident chain IS the cyber objective, plus: authenticated dashboard commands (rolling counter + MAC, live replay-attack rejected), PIN lockout surviving power cycles, fail-secure boot. Vocabulary: "Honeywell Forge Cybersecurity+ | Cyber Insights" is their real product line — mention once, lightly. Never say "encrypted"; say "hash-chained, append-only; production would use a secure element."

## Implementation delta on top of [[Projects/FutureShapers-Hackathon/implementation-guide|the core guide]]
Nearly pure software over the standard build — lowest risk per unit of originality:
1. Core build exactly as the guide (scaffold → sensors → cyber). The chained EEPROM audit log is already in the plan — here it's promoted to product centerpiece.
2. `LOG` record: `seq | ms | zone | sensor | value | prevCRC | CRC8(record+prevCRC)` — ring buffer in EEPROM (~120 records), mirrored over serial to the laptop which archives the full history.
3. Replay mode = Python script over the archived serial log: re-verify chain, scroll timeline, render the incident packet. ~1h.
4. 7-seg wired as log-seq counter / stopwatch (or LCD line 2 if pins are tight — Plan A pin map note: 7-seg optional).
5. The tamper-reveal: "Verify log" button in dashboard; corrupting one byte in the laptop archive (or EEPROM via hidden serial cmd) breaks the chain visibly. Rehearse THIS scene most — it's the pitch.
6. Cardboard model: grey bloc cutaway ("Str. Vicina" vibe, avizier notice board, tiny windows) — deliberately ugly-authentic.

## Weaknesses + counters
- "A recorder is passive — does it DO anything?" → the stopwatch scene: it also *acted* in 3.2 s. Active controller + honest witness.
- Hash chain must be explainable in 30 s → the tamper-reveal demo IS the explanation; never say blockchain (say "append-only chained checksums, like a flight recorder").
- Rahova sensitivity → no victim names/photos, one respectful sentence, focus on the 11 silent days and the unanswered question.

## Verdict vs the other options
| Option | Originality | Jury fit | Demo risk | Emotional force |
|---|---|---|---|---|
| **B: Cutia Neagră (bloc skin)** | 9/10 — category escape | Excellent (Lugoj + OT-cyber + NIS2) | LOW (software) | High (Rahova/Colectiv, verified) |
| A: Straja (wooden church) | 9/10 — once-in-a-hackathon | Excellent (Lugoj fire alarms) | Low-med | Maximal (national heritage) |
| C: Gospodar (barn) | 8/10 | Very good (Honeywell sells agri gas detection) | Low-med | Medium |
| D: Dorm | 5/10 | Good | Low | Medium |
Compromise line if the team also loves A or C: *"the same node bolts into a wooden church or a barn tomorrow"* — one sentence, not a re-staging.
