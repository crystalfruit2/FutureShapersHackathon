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
