---
tags:
  - project
  - hackathon
date: 2026-08-25
---

# Pitch Options — pick one with the team, build starts either way

The machine (state machine + dashboard + cyber suite + fault tolerance, per [[Projects/FutureShapers-Hackathon/implementation-guide|implementation guide]]) is identical under every option. Only the cardboard model, zone labels, and narration change. Full research behind these: [[Projects/FutureShapers-Hackathon/research-2026-08-25]].

## Option A — "Straja": guardian for Romania's wooden churches
On 3 July 2026 — seven weeks ago — the 1675 oak church of St Elijah at Poșta, Maramureș (Category A monument) burned almost entirely; the alarm came at 4 a.m. when 200 m² were already ablaze, and nobody was watching (VERIFIED: Radio Cluj, Europa FM). In 1930, one candle at Costești killed 118 people. Maramureș has 8 UNESCO wooden churches and ~200 more, sitting unmanned in depopulating villages, holding irreplaceable icons, where water sprinklers would destroy what they save.
**Demo:** zones nave/altar/tower; flame = the candle left burning; relay cuts heating; DHT11 = conservation microclimate (= energy story); PIR = off-hours intrusion; **tilt sensor on the icon frame — a juror lifts the icon, instant alarm (THE moment)**; cyber = the diocese's remote dashboard for an unattended site, authenticated commands, tamper log. Close: the diocese announced protection measures after the Poșta fire — the customer already exists; Honeywell Lugoj (908 people) manufactures exactly these fire-alarm systems.
*Strengths:* once-in-a-hackathon originality, maximal national emotion, perfect Lugoj fit. *Watch-outs:* MQ4 slightly forced (stove gas), "religion" framing must stay heritage-framing.

## Option B — "Cutia Neagră": the flight recorder for buildings ⭐ non-religious flagship
Full concept + implementation delta: [[Projects/FutureShapers-Hackathon/option-cutia-neagra]].
Airplanes have flight recorders; buildings don't. Rahova's cause is *still* unestablished by prosecutors; Colectiv's investigation took 4 years; and NIS2 (now Romanian law) makes tamper-evident incident logging a legal duty. The node is a working smart building whose hash-chained, tamper-proof log replays any incident second by second — **and when the "landlord" edits one line to hide the gas warning, the chain breaks in red at exactly that record.** "You can burn the building — you can't burn the truth."
*Strengths:* category escape (evidence infrastructure vs everyone's reactive controller), lowest demo risk (pure software delta), three verified Romanian hooks + a legal hook. *Watch-outs:* must show all 4 objectives in scene 1 or the recorder identity swallows them; Rahova handled respectfully.

## Option C — "Gospodar": the digital shepherd (barn node)
Persona Nea Ion, Timiș county — 40 km from the jury's own Lugoj plant. Manure gas kills whole families (288 verified US deaths; odorless at lethal levels) → MQ4 + relay-slammed ventilation is a life-safety loop, not a gadget. Tilt on the gate = Europe-wide livestock-theft gangs; flame = hay/electrical fires (~70% of barn fires); ultrasonic = feed-silo gauge; DHT ventilation = animal welfare AND the energy objective. Business: Romania = 2.9M farms = 31.8% of the whole EU's farms; Honeywell already sells agri gas detection (BW line — say it back to them); biogas upsell (17M MWh untapped). Safety actuations hardware-interlocked — no remote command can cancel them.
*Strengths:* every sensor natural, empty category, verified Honeywell-agri hook. *Watch-outs:* US death data not Romanian; medium emotional heat.

## Option D — fallback: the Regie dorm retrofit
Ana, room 314; the building we slept in last night. Kept from the original pitch — solid, authentic, but 4–6 rival teams will build some smart-home variant and another may even pick the dorm. Use only if the team rejects A–C.

## How to decide with the team (Tue, 15 minutes max)
1. Gut check: which story does each teammate WANT to tell on Thursday? Enthusiasm on stage is worth a point.
2. If split: **B (Cutia Neagră)** — it has the best originality-to-risk ratio and the strongest cyber story, and A/C survive as one-line scale-out mentions ("the same node bolts into a wooden church or a barn tomorrow").
3. Whatever wins: build order in the guide is unchanged; the model-builder starts the chosen skin Wed morning.
