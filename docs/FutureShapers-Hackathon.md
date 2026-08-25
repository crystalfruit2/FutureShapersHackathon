---
tags:
  - project
  - hackathon
status: active
started: 2026-08-24
deadline: 2026-08-27
location: POLITEHNICA Bucharest, Romania
---

# FutureShapers Hackathon 2026 🏆

Honeywell hackathon inside [[Resources/futureshapers-camp-2026|FutureShapers Camp 2026]] (Bucharest, 24–28 Aug). **Goal: win it.**

## The task
Build an **innovating automation system** with an Arduino UNO R3 CH340 + Bitmi 10171 kit, plus 5 extra sensors (MQ4 gas, air quality, PIR motion, flame, tilt KY-020). Four objectives: centralized control · security · energy efficiency · **cyber security** (listed twice in the brief — our differentiator).

Brief slide photo: ![[hackathon-brief-slide.png]]

## Key documents
- **Code repo (Mac):** `/Users/alpeldam/Documents/Projects/FutureShapers-Hackathon/` — firmware in root, `docs/` mirrors this vault folder (vault = writing source of truth; re-copy after edits)
- **[[Projects/FutureShapers-Hackathon/proposal-master|MASTER PROPOSAL]]** — ⭐ single source of truth (Tue midday): official brief intel, reconciled verdict (A Straja vs C Ferma Străjer), agri deep-dive, cyber checklist, facts bank
- **[[Projects/FutureShapers-Hackathon/official-brief.docx|Official brief]]** — full doc received Tue: scoring = Innovation/Creativity/Functionality/Practicality; dashboard+energy monitoring = official bonus; full kit list (water level, sound, stepper, thermistor, 74HC595)
- **[[Projects/FutureShapers-Hackathon/pitch-scenario|Pitch options]]** — A: Straja (wooden church) · B: Cutia Neagră (flight recorder for buildings, non-religious flagship) · C: Gospodar (barn) · D: dorm fallback — pick with the team Tue
- **[[Projects/FutureShapers-Hackathon/option-cutia-neagra|Cutia Neagră concept]]** — full black-box concept + implementation delta
- **[[Projects/FutureShapers-Hackathon/implementation-guide|Implementation guide]]** — materials, pin map (Plan A/B/C), firmware architecture, hour-by-hour build, demo skeleton
- **[[Projects/FutureShapers-Hackathon/research-2026-08-25|Research]]** — 7 agents: stress-test, 19 verticals, tech feasibility, jury model, winning patterns, barn/bloc head-to-head, 9 framings
- **[[Projects/FutureShapers-Hackathon/battle-plan|Battle plan]]** — concept ("miniature Honeywell building"), 4 demo scenarios, cyber feature list, hour-by-hour execution plan, presentation rubric mapping, team roles

## Timeline
| When | What |
| --- | --- |
| Mon 24.08 | Brief received at opening · battle plan drafted ✅ |
| Tue 25.08, 10–12 | **Skeleton milestone:** state machine + LCD + keypad + 1 sensor + 1 output, end-to-end |
| Tue 25.08, 13–16 | Add sensors one at a time (non-blocking code only) |
| Wed 26.08, 10–12 | Cyber features + cardboard building model |
| Wed 26.08, 13–16 | **Feature freeze 14:00** → 3 rehearsals + backup video |
| Thu 27.08, 10–13 | Final presentation (10–15 min) & prizes |

## Team
- Alp — _(fill roles once agreed: firmware / hardware / cyber+test / story-scribe)_
-
-
-

## Day log
### Mon 24.08
- Opening + Honeywell visit; hackathon brief captured (one slide)
- Battle plan drafted with Claude

### Tue 25.08 (morning, pre-block)
- 7-agent research sprint: dorm idea stress-tested (verdict: story upgradeable, machine right), 19 verticals + 9 framings scored, jury modeled (hiring funnel; TeChallenge proxy), 15 winning projects mined
- Four pitch options on the table (Straja / Cutia Neagră / Gospodar / dorm) — team decision pending
- Implementation guide written; pin-famine solved on paper (Plan A: 4-button ladder)

### Tue 25.08
- Competition officially started; full brief doc received → scoring revealed (Innovation/Creativity/Functionality/Practicality — novelty IS scored), dashboard + energy monitoring = official bonus points, kit richer than the slide (water level, sound, stepper, thermistor, 74HC595)
- Alp's agri idea → 5-agent deep-dive: poultry/livestock facility scored 24/25 (ties Straja); Suceava Jan-2025 biogas explosion (5,000 pigs) = the missing Romanian anchor; Honeywell agri alignment confirmed ("largest unprotected building class" framing); agri×cyber = unoccupied lane
- **[[Projects/FutureShapers-Hackathon/proposal-master|Master proposal]] written; team DECIDED: 🐔 FERMA STRĂJER locked (see [[Areas/Decision-Log]])** — code repo at `~/Documents/Projects/FutureShapers-Hackathon/`

### Wed 26.08
-

### Thu 27.08 — result
-

## Challenge log (feeds rubric items 4 & 7 — keep it live!)
-
