# BioGuard — attract loop

40 s silent pixel loop for the table screen: night farm → farmer walks to the barn →
doors open on the animals → pull back to the beetle watchman + **BIO GUARD** → live
dashboard beat (intruder, bad-MAC reject, replay blocked, log chain intact) → loops.

- `render.py` — the whole thing. No engine, no third-party art, no assets on disk.
  320×180 internal, nearest-upscaled ×4. Sprites are ASCII maps at the top of the file.
- `bioguard_attract.mp4` — 1280×720, 24 fps, h264. **Play this on the day**, fullscreen,
  looped, muted. Nothing to crash in front of the jury.

Rebuild:  `python3 render.py`  then
`ffmpeg -y -framerate 24 -i frames/f%05d.png -c:v libx264 -pix_fmt yuv420p -crf 18 \
  -vf "scale=1280:720:flags=neighbor" bioguard_attract.mp4`

Quick look at one moment: `python3 render.py --still 20`

Not part of the demo system — separate files, touches no firmware and no dashboard state,
so it sits outside the Wed 14:00 feature freeze.

## Godot port (`godot/`)

Same 40 s beat sheet, rebuilt in Godot 4.7 so the loop can be tweaked in an editor
instead of a Python file. **Not interactive — it is the same silent attract loop.**
The mp4 above is still what plays on the day; this is the convenience layer.

`Main.tscn` is the source of truth — edit it in the Godot editor, or as text.
`build_scene.py` is the scaffolding that built it and now refuses to run without
`--force`, because running it would discard editor work. It stays as the readable
record of how every node was derived from `render.py`.

- twelve spot frames: `Godot --path . res://Shots.tscn` → `shots/`
- the whole loop: `Godot --path . res://Record.tscn -- <outdir> 24 40` → 960 PNGs,
  then the same ffmpeg line as above. `Record.gd` seeks frame by frame so it is
  deterministic; Godot's own Movie Maker under-reported frames and stalled here.

What the engine buys over `render.py`, all of it inspector-tweakable:

| | where | knob |
| --- | --- | --- |
| real 2D lighting instead of pasted glow blobs | `World/LampLight` … `BarnTop` | `energy`, `texture_scale`, `Flicker.gd` exports |
| procedural twinkling starfield (`sky.png` never had stars — `render.py` redrew them every frame, so the port lost them) | `World/Sky/SkyArt` material | `density`, `twinkle` |
| parallax depth on sky + both hill layers | `World/Sky`, `Far`, `Near` | `scroll_scale` |
| fireflies, barn dust, chimney smoke | `Fireflies`, `BarnDust`, `Smoke` | `amount`, `color_ramp` |
| vignette | `Grade/Vignette` | `strength` |
| CRT scanlines on the dashboard beat | `Dashboard/Crt` | `scan`, `sweep` |

Camera and door motion is baked to **linear** keys on purpose: Godot's cubic value
interpolation overshoots between equal keyframes and threw the camera off the world.

## Pitch cold open (`coldopen.py`)

A **second, separate film** from the attract loop above, which is untouched and still
plays on the table. This one opens the pitch. **34 s**, silent, English, same pixel
language. Captions are English because not all of the jury is Romanian; only the place
name keeps its diacritics.

`bioguard_coldopen.mp4` — 1280×720, 24 fps. Rebuild:
`python3 coldopen.py` then the same ffmpeg line as above, with `co_frames`.
One moment: `python3 coldopen.py still 16.0`.

**Ignition is an electrical fault that smoulders, not lightning.** Three reasons, all
of them ours: a strike takes the power and the router with it (RO averages 350 min/yr
without power); no sensor in the kit can see a bolt land on an open field; and a bolt
is *instantaneous*, so it gives the predictive layer nothing to predict — the one
feature the whole pitch rests on. A frayed cable also reads as preventable, i.e. as a
market; an act of God reads as futile.

**Which night you are watching is never ambiguous:** a persistent tag sits top-left of
every shot — red `WITHOUT BIOGUARD`, green `WITH BIOGUARD` — a card between the halves
announces the restart, and the beetle's lantern is amber in the first half and red in
the second. Text holds are deliberately long (see `D_OPEN`/`D_STAMP`/`D_MID`/`D_FINAL`
and `SKIP_HOLD`): a card that reads fine on a laptop is gone before anyone at the back
of a room has finished it.

**Structure — the same night, twice, sequentially.**
The camera never moves. The first half is built out of *absence*: the fire grows and
nothing in frame responds to it, and the clock skips 02:45 → 08:30 while the barn
burns. Two black cards carry the two real timestamps from the Giurgiu case (found
08:30, brigade 11:00). Then a hard cut back to a **pixel-identical** frame — verified
at 0.002 mean abs diff, clock digits only — and this time the beetle's lantern goes
red at 02:40:04, the doors open, and the animals walk out.

The film does **not** show a fire truck arriving. We compress *detection*, not
response; the `/fire` console says ETA ~18 min and the video must not contradict it.
The rescue is the live demo, not the video — the film creates the debt, `/fire` pays it.

| | where | knob |
| --- | --- | --- |
| smoulder → open flame | `draw_fire` | `amt` (≤0.30 smoulder, →1.0 fire) |
| charred shell + ragged ridge | `burn_barn` | `prog`; call **before** `draw_fire` (needs clean palette) |
| the ignition itself | `draw_spark` | 2 frames, the only fast thing in the film |
| the clock | `hud` / `_p1_clock` | `SKIPS` table |
| beat timing | module constants | `CARD0 P1 P1_END CARDS P2 ACT END TOTAL` |

Romanian diacritics `Ă Â Î Ș Ț` (plus the legacy cedilla codepoints `Ş Ţ`) and
`€ · , — →` were added to `render.py`'s `FONT`. `text()` force-uppercases, so only the
caps forms exist. Comma-below letters run two rows past the baseline; breve and
circumflex letters compress into rows 2–6 so every baseline still lines up.
