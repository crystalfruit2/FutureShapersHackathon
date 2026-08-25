---
tags:
  - project
  - hackathon
date: 2026-08-25
status: active
supersedes: "[[Projects/FutureShapers-Hackathon/research-2026-08-25|morning research]] + agri deep-dive (5 agents, Tue midday)"
---

# FutureShapers — Master Proposal (all ideas, revamped)

> **✅ DECIDED Tue 25.08 midday: Option C — Ferma Străjer locked by team vote.** Sections 3, 5, 6, 7 are now the active plan; A/B material survives via the platform close + audit-log feature.

Single source of truth as of Tue 25.08 midday. Consolidates: morning 7-agent research, the agri deep-dive (5 agents), and the **full official brief** ([[Projects/FutureShapers-Hackathon/official-brief.docx|official-brief.docx]], received Tue).

---

## 1. What the official brief changed (new intel — read first)

1. **Scoring is now known: Innovation · Creativity · Functionality · Practicality.** The morning jury model assumed novelty wasn't scored — **wrong**. Innovation + Creativity = half the score. A distinctive vertical is worth real points, not just vibes.
2. **"Additional points" are explicit:** (A) remote monitoring/control via a user-friendly app, (B) energy monitoring in real time, (C) centralized web dashboard. → The planned **serial-tethered laptop dashboard is now officially bonus-scoring. Build it.** Add a "power saved" tally = energy monitoring points.
3. **Cyber recommended topics are enumerated** (map features 1:1, say the words): authentication & access layers (admin/power user/user) · data encryption · secure firmware updates · data privacy · device hardening · physical tamper resilience · **OWASP IoT compliance**. Nobody else will read OWASP IoT Top 10 tonight — quoting it = free Innovation points.
4. **Full kit list is richer than the slide** — new usable parts: **water level sensor** (trough/drinker supply!), **sound sensor** (flock distress / glass-break), **stepper + ULN2003** (feed auger / vent crank), **thermistor** (2nd temp channel → cross-check vs DHT11 = spoof detection), **4-digit 7-seg** (live ppm/°C readout), **74HC595** (pin-famine relief), joystick, RGB LED, L293D.
5. Typo in brief: motion-sensor row links the MQ135 page; actual part is a PIR. Flame sensor = KY-026.

---

## 2. The verdict (reconciled across all 5 research agents)

**Alp's instinct survived adversarial review — with one big correction: the winning agri idea is not a farm gadget, it's a *building*.**

- The adversarial agent initially said "don't pivot" (85%) — but two of its three decisive reasons **fell** with new evidence:
  - *"Novelty isn't scored"* → refuted by the official scoring (Innovation + Creativity = 2/4).
  - *"Agri has no Romanian emotional anchor"* → refuted by **F1: Suceava, Jan 2025 — manure biogas + electrical short = explosion, 5,000 pigs dead, €5–6M** — the exact failure chain our node prevents — plus **F4: another Romanian farm burned *yesterday* (Sulița, Botoșani, 24.08.2026)**.
  - What still stands: **switching costs ~4h of story assets** (model, script, slides — firmware is ~100% reused). So the decision is **today, before the afternoon block — never a Wednesday pivot.**
- "Agriculture wins hackathons" is half-true: agri wins where impact is scored (it IS here — Practicality) but **the sensor-plumbing build loses everywhere** (8,151 GitHub repos for "smart irrigation"; smart-greenhouse = the agri tutorial-project). The winning shape: named pain + number, unusual mechanism, economics slide, demo the *decision* not the plumbing.
- Honeywell jury alignment: **ALIGNS — conditionally.** Honeywell's own agriculture page names CH₄/H₂S/CO₂/NH₃ in manure storage & silos (Manning EC-FX-NH3, BW Solo). **NFPA 150** (fire & life safety code for animal housing) exists because — their words — *"current building, fire and life safety codes do not address the life safety of the animal occupants."* Calibration line: **"We're extending building automation to Europe's largest unprotected building class"** — never "we're doing smart farming." (Honest gap: Honeywell has no barn BMS product — that's the opportunity slide; don't imply they sell one.)

### The three live options

| | Option | Score | Wins on | Loses on |
|---|---|---|---|---|
| A | **Straja** — wooden-church guardian | 24/25 | Strongest single emotional anchor (1675 Poșta church burned 7 weeks ago; Lugoj makes fire alarms); script & scenes pre-written | Weakest energy story; religious framing to manage |
| B | **Cutia Neagră** — flight recorder for buildings | 24/25* | Cyber-native identity (chained-CRC log hero); non-religious; Rahova/NIS2 | Least visceral demo props |
| C | **Ferma Străjer** (Gospodar 2.0) — smart livestock facility | **24/25** | All 5 special sensors honest (MQ4 = datasheet purpose); **best cyber story of any option** (spoofed 'fans-off' kills a flock in ~3h); best energy story; biggest scale slide (⅓ of EU farms); F1 anchor; nobody else will do it | ~4h story-asset rebuild; church still edges it on pure heartbreak |

**Recommendation:** team vote between A and C **today**. Whatever wins, close with the **platform slide** — "the same node protects a 1675 church, a Suceava barn, an ATEX Zone 20 silo: Romania's unmanned buildings" — so the losing option's best material still gets used. B's chained-CRC audit log ships as a feature in every variant.

---

## 3. Option C revamped: **Ferma Străjer** — the livestock facility as a building

One cardboard building, four zones: **poultry hall · manure/waste pit · feed & water store · control room.** (Poultry hall chosen over pure pig barn: every demo trick is legible in 10 seconds; the manure-pit zone imports the pig-farm methane story.)

### Sensor → zone → documented hazard (all cited in facts bank)
| Sensor | Zone | Real hazard |
|---|---|---|
| MQ4 | manure pit | methane accumulation → **Suceava explosion (F1)**; pit CH₄ hits 5–15% = explosive range |
| Air quality (MQ135) | poultry hall | ammonia ≥50 ppm = irreversible damage to birds; 20–25 ppm = industry limit |
| DHT11 + **thermistor** | hall + brooder | heat-death: closed house kills a flock in ~3h (14,000 birds, Pennsylvania, Jul 2026). Two independent temp channels → **sensor-spoof cross-check** (cyber feature!) |
| Flame (KY-026) | feed store | 70% of barn fires with known cause = heating/electrical (F6); 2.53M US animals dead 2022–24 |
| PIR | perimeter, night mode | intrusion/predator; + pit-entry interlock ("person entered while gas high" — rescuers are >¼ of manure-gas victims, F8) |
| Tilt (KY-020) | control cabinet door | physical tamper → alarm (brief: "resilience against physical tampering") |
| **Water level** | drinker line | supply failure = silent flock killer; kit part nobody else will use |
| **Sound sensor** | hall | flock-distress anomaly (real research area) — Innovation points |
| Ultrasonic | feed silo | fill-level gauge on dashboard |
| Photoresistor | hall | broiler lighting programs (real management lever) |
| Relay / fan / servo / **stepper** | — | "gas valve" cut · exhaust fan · inlet vent flap · feed auger |

### The four demo scenes (= 4 objectives, in order)
1. **Central control:** keypad+LCD control room, modes DAY/NIGHT/EMERGENCY; dashboard mirrors zones. (Bonus points: web dashboard is official extra credit.)
2. **Energy:** hysteresis ventilation + lighting program + live "power saved" tally on 7-seg (official extra credit: energy monitoring).
3. **Security:** night mode → PIR intruder → alarm; cabinet tilt-tamper; PIN lockout.
4. **Life safety + cyber (the peak):** butane puff at pit MQ4 → EMERGENCY: gas-valve relay cut, fan purge, servo vents, "EVACUATE — do not enter pit" (rescuer-protection line). Then the **cyber scene**: laptop sends spoofed unauthenticated "fans off" → **"REJECTED — STALE COUNTER / BAD MAC"**, logged in chained-CRC EEPROM audit log; juror invited to corrupt a byte → chain breaks red at the exact record. Narration: *"In 2021 ransomware stopped a quarter of US beef production. This is what secure-by-design farm OT looks like."*

### Cyber checklist → official recommended topics (say these literally)
- Auth & access layers → user PIN disarms, admin PIN configures (least privilege)
- Data encryption → honest framing: *"UNO can't do TLS — we do MAC'd commands + rolling counter, and here's what production hardening needs"* (points for honesty in front of OT people)
- Secure firmware updates → physical-presence flag (jumper) required to flash; narrated
- Data privacy → no PII on device; log stores events, not people
- Device hardening → watchdog + fail-secure boot (reboots into ARMED) + EEPROM state restore
- Physical tampering → tilt sensor on cabinet + lockout survives power-cycle
- OWASP IoT → name-check "no default passwords, secure update, audit logging" mapped to features

### The economics/platform close (45 s — use in ANY option)
- ⅓ of all EU farms are in Romania; agri = 20.7% of employment; **44% of farmers are over 65** → "who watches the barn at 3 AM?"
- **EU pays for this:** CAP RO plan = €14.9B; AFIR opening **€665.7M** (Dec 2025–Feb 2026), incl. DR-12 young farmers €200k w/ digitalization + DR-21 pig biosecurity €50k — name the measure codes.
- Insurance already mandates monitoring in large livestock buildings.
- Loop-closer: the same manure gas that burned Suceava = **14+ TWh/yr untapped biogas** (Romania has ~10 plants; Germany thousands) — *"measure the hazard today, harvest it tomorrow."*

---

## 4. Agri annex — what NOT to build (from 19+10 scored verticals)
- **Greenhouse/sera (20/25):** the agri cliché — judges have seen ten; MQ4 weak. Only steal the Tomata line: *"€200M of subsidies, imports still grew — cash doesn't fix climate control, technology does"* (F15).
- **Silo & cold storage (16/13):** their famous disasters (dust, phosphine, low O₂) are **invisible to this sensor kit** — a gas-sensor-literate judge will catch it. Silo appears only as the ATEX Zone 20 *line* in the platform close.
- **Wine cellar (17):** best story, wrong chemistry (killer is CO₂; MQ4 can't see it).
- **Stână (16):** best 30-second anecdote (27 shepherds killed by bears in 20 yrs), worst project. One pitch line max.
- **Irrigation (13):** 8,151 GitHub repos. Never.

## 5. Verified facts bank — agri (F-numbers; ✅ = safe on stage)
- **F1 ✅ Suceava 13.01.2025:** Agrosuin farm, Vornicenii Mici — biogas from animal waste + faulty conductor → explosion, fire, 4,000 m² hall, **5,000 pigs dead, €5–6M**, 2 silos hit. [newsweek.ro](https://newsweek.ro/actualitate/incendiu-devastator-la-o-ferma-din-suceava-unde-se-aflau-5000-de-porci-toate-animalele-au-pierit) · [revista-ferma.ro](https://revista-ferma.ro/incendiu-la-o-ferma-din-suceava-5-000-de-animale-arse-de-vii-de-la-ce-a-pornit-focul/) — **the opening fact.**
- **F4 ✅ Sulița, Botoșani 24.08.2026 (yesterday):** animals dead + 5 t feed burned. [radioromania.ro](https://www.radioromania.ro/stiri-locale/botosani-animale-moarte-si-furaje-arse-in-urma-unui-incendiu-id211751.html) — *"while we prepared this pitch, another farm burned."*
- **F2 ✅ Brăila 2023:** ~200 animals, electrical fault, man burned trying to save them. **F3 ✅ Botoșani 2024:** 70 cows, volunteer firefighters. **F6 ✅** 2.53M US animals in barn fires 2022–24; ~70% of known causes = heating/electrical; AWI recommends detection.
- **F7 ✅ Colorado 20.08.2025:** 6 dead of H₂S at a dairy, 4 from one family, one a student. **F8 ✅** 459 people in US manure-gas incidents since 1975, ~59% fatal; **>¼ of victims are rescuers**. (⚠️ do NOT say "288 deaths" — use "nearly 6 in 10 died".)
- **F11–F14 ✅** agri = 20.7% of RO employment (EU outlier) · 23% of the entire EU ag workforce · ⅓ of EU farms, 3.4% of output, 92% under 5 ha · 44.3% of farmers >65 · biggest EU decline in ag employment (−8.9 pp).
- **F15 ✅ Tomata:** minister: "4 years, ~€200M, impact zero" (Factual.ro: truncated but directionally real). **F16 ✅ OLAF:** €850k tomato-subsidy fraud — *"sensor data makes subsidies auditable."*
- **F19 ✅** Romania = EU's #1 grain exporter 2024–25 (wheat 5.4M t). **F21 ✅** Purdue: 2023 = 55 US confined-space cases, 29 fatal.
- **F22–F23 ✅** CAP €14.9B · AFIR €665.7M opening Dec 2025–Feb 2026 (DR-12/DR-14/DR-21).
- **F24 ✅** 14.1M MWh/yr biogas potential from RO manure; ~10 plants nationwide. (⚠️ don't say "17M MWh" or "zero plants".)
- **⚠️ Do-not-say list:** 288 deaths · €2B/5× import ratio · Constanța 36M t · 17M MWh · zero on-farm biogas · the two unverified 2026 Suceava fires.

## 6. Agri × cyber incident deck (for the cyber slide, any option)
JBS May 2021 — $11M ransom, ~25% of US beef offline · AGCO May 2022 — tractor plants shut during planting · 6 grain co-ops hit at harvest 2021 → **FBI warning: attacks timed to seasons** · DEF CON 30 John Deere jailbreak · Food & Ag ISAC founded 2023 · academic literature names "tampered climate control decimating bird populations" as an attack outcome. **No notable hackathon winner has ever occupied farm OT security (2018–2026 search) — open lane.**

## 7. Honeywell vocabulary bridges (any option)
1. *"Fire & life safety for the buildings nobody protects"* — NFPA 150's own rationale; Lugoj builds fire alarms.
2. *"A silo is an ATEX Zone 20 building"* — EU law, their home turf.
3. *"The four gases Honeywell already names: CH₄, H₂S, CO₂, NH₃"* — from their own agriculture page (Manning EC-FX-NH3, BW Solo). We add the fixed, networked supervisory layer above their portable detectors.
4. *"A supervisory layer for unmanned OT sites"* — Forge/OT-SOC language, applied where no SOC has looked.
5. *"Insurance is already mandating what we're building."*

---

*Full agent outputs: [[Projects/FutureShapers-Hackathon/research-2026-08-25|morning research]] · this doc supersedes the pitch-options list in [[Projects/FutureShapers-Hackathon/pitch-scenario|pitch-scenario]] for option C. Build details unchanged: [[Projects/FutureShapers-Hackathon/implementation-guide|implementation-guide]] (74HC595 + new sensors need a pin-map pass).* 
