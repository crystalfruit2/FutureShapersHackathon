# Bio Guard — attract loop

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
