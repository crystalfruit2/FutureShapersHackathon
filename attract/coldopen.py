"""BioGuard — pitch cold open.  "The same night, twice."

A second, separate film from the 40 s attract loop in render.py, which is
untouched and still plays on the table. This one opens the pitch.

Ignition is an ELECTRICAL FAULT that smoulders, not lightning. Three reasons,
all of them ours: lightning takes the power and the router with it, no sensor in
the kit can see a strike on an open field, and a bolt is instantaneous -- it
gives the predictive layer nothing to predict, which is the one feature the whole
pitch is built on. A frayed cable also reads as preventable, i.e. as a market;
an act of God reads as futile.

Shared asset set, two cuts:
    python3 coldopen.py seq     -> sequential  (bad night, then the same night again)
    python3 coldopen.py split   -> split screen (both nights at once, shared clock)
    python3 coldopen.py still 8.0 seq
"""
from PIL import Image, ImageDraw
import math, random, os, sys

import render as R
from render import (C, W, H, WW, WH, FPS, BARN, HOUSE, blit, glow, ease,
                    text, tw, camera, _base, COW, CHICKEN, farmer)

# ── framing ──────────────────────────────────────────────────────────────
# Locked camera. It never moves in either cut -- in a room where every other
# reel is cuts and pushes, a frame that refuses to move is the loudest thing on
# the projector. zoom stays at 1.0: anything below it downsamples pixel art.
CAM = (400, 110, 1.0)
BX, BY = BARN
FIRE_X, FIRE_Y = BX + 50, BY + 72        # feed & water store, right of the doors

C2 = dict(C)
C2.update({
 'ember':(150,38,18),'ember2':(206,66,22),'smoke':(58,60,68),'smoke2':(78,80,88),
 'char':(28,22,20),'ash':(96,92,90),
})

# ── fire ─────────────────────────────────────────────────────────────────
def draw_fire(img, amt, t, ox=FIRE_X, oy=FIRE_Y):
    """amt 0..1.  <=0.30 smoulder (embers + smoke, no flame). ->1.0 open fire."""
    if amt <= 0.002: return
    px = img.load(); d = ImageDraw.Draw(img)
    rnd = random.Random(int(t * FPS))
    sm = min(1.0, amt / 0.30)                    # smoulder ramp
    fl = max(0.0, (amt - 0.28) / 0.72)           # flame ramp

    # embers at the base -- the first thing that exists, and the thing a
    # rising-temperature channel sees long before any flame sensor does
    ew = int(4 + 16 * sm + 12 * fl)
    for i in range(int(6 + 26 * sm + 40 * fl)):
        x = ox - ew // 2 + rnd.randrange(0, max(1, ew))
        y = oy - rnd.randrange(0, 2 + int(3 * sm))
        if 0 <= x < WW and 0 <= y < WH:
            px[x, y] = C2['ember2'] if rnd.random() < 0.4 + 0.4 * fl else C2['ember']

    # flame tongues
    if fl > 0.01:
        fw = int(6 + 26 * fl)
        for col in range(-fw // 2, fw // 2):
            edge = 1.0 - abs(col) / (fw / 2.0 + 0.001)
            hgt = (2 + 30 * fl) * (0.35 + 0.65 * edge)
            hgt *= 0.75 + 0.25 * math.sin(t * 13.0 + col * 0.9)
            hgt *= 0.85 + 0.3 * rnd.random()
            for k in range(int(hgt)):
                x, y = ox + col, oy - k
                if not (0 <= x < WW and 0 <= y < WH): continue
                u = k / max(1.0, hgt)
                px[x, y] = (C2['lit2'] if u < 0.22 else
                            C2['lit']  if u < 0.48 else
                            C2['gl']   if u < 0.76 else C2['gl2'])

    # smoke, rising and drifting -- present from the first ember
    for i in range(int(40 + 90 * sm + 260 * fl)):
        rise = rnd.random() ** 0.5
        y = oy - int(4 + rise * (34 + 84 * amt))
        spread = 3 + rise * (16 + 26 * amt)
        x = ox + int((rise ** 1.4) * 30 * math.sin(t * 0.6 + rise * 4.0)) \
              + rnd.randrange(-int(spread), int(spread) + 1)
        if 0 <= x < WW and 0 <= y < WH and rnd.random() < 0.92 - 0.42 * rise:
            r = rnd.random()
            px[x, y] = (C2['smoke2'] if r < 0.30 else
                        C2['ash']    if r < 0.36 and amt > 0.5 else C2['smoke'])

    # the fire is its own light source
    glow(px, ox, oy - int(3 + 9 * fl), int(13 + 30 * amt), C2['gl'], 0.26 + 0.40 * amt)
    if fl > 0.2:
        glow(px, ox, oy - 5, int(16 + 18 * fl), C2['lit'], 0.16 * fl)


BARN_COLS = frozenset([C['bn'], C['bn2'], C['bn3'], C['bnr'], C['bnr2'],
                       C['roof'], C['roof2'], C['lit'], C['lit2'], C['gl2'], C['K']])

def burn_barn(img, prog, base_px):
    """prog 0..1 -- char the shell and nibble the ridge away.

    Only pixels that are actually part of the barn are touched: darkening the
    whole bounding box painted a visible rectangle over the sky and the grass.
    Deliberately NOT a clean geometric collapse either -- a rectangular bite out
    of the roof reads as a black box, not as a fire. Ragged char plus the smoke
    from draw_fire does the work. Call this BEFORE draw_fire, so the barn is
    still pristine palette colours and can be matched."""
    if prog <= 0.002: return
    px = img.load()
    k = 1.0 - 0.62 * prog
    for y in range(BY - 8, BY + 75):
        for x in range(BX - 10, BX + 102):
            if not (0 <= x < WW and 0 <= y < WH): continue
            c = px[x, y]
            if c in BARN_COLS:
                px[x, y] = (int(c[0] * k), int(c[1] * k * 0.86), int(c[2] * k * 0.80))
    # ragged nibble down from the ridge, restoring the sky band behind it
    rnd = random.Random(7)
    jag = [rnd.random() for _ in range(BX - 10, BX + 102)]
    for j, x in enumerate(range(BX - 10, BX + 102)):
        n = 0.30 + 0.70 * jag[j] * (0.55 + 0.45 * math.sin(x * 0.55))
        eaten = 0
        for y in range(BY - 8, BY + 30):
            if eaten >= int(30 * prog * n): break
            if 0 <= x < WW and 0 <= y < WH:
                c = px[x, y]
                if c == base_px[6, y]: continue          # still sky, nothing to eat
                px[x, y] = base_px[6, y]; eaten += 1
    if prog > 0.35:                                        # embers + ash in the wreck
        rnd2 = random.Random(int(prog * 977))
        for i in range(int(160 * (prog - 0.35))):
            x = BX + rnd2.randrange(0, 93); y = BY + 26 + rnd2.randrange(0, 48)
            r = rnd2.random()
            px[x, y] = C2['ember2'] if r < 0.22 else (C2['ember'] if r < 0.55 else C2['char'])


# ── the world, with the state this film needs ────────────────────────────
_CLEAN = {}
def clean_px():
    if 'p' not in _CLEAN: _CLEAN['p'] = _base().load()
    return _CLEAN['p']

def draw_spark(img, t, ox=FIRE_X, oy=FIRE_Y - 16):
    """The overloaded junction box letting go. An electrical fault, not a bolt:
    it is preventable, it develops over time, and it is what actually burns
    Romanian barns."""
    px = img.load(); rnd = random.Random(int(t * FPS * 3))
    for i in range(14):
        x = ox + rnd.randrange(-3, 4); y = oy + rnd.randrange(-3, 4)
        if 0 <= x < WW and 0 <= y < WH:
            px[x, y] = (208, 226, 255) if rnd.random() < 0.5 else C['lit2']
    glow(px, ox, oy, 14, (190, 214, 255), 0.55)


def scene(t, *, house_lit=False, fire=0.0, burn=0.0, barn_open=0.0,
          farmer_x=None, alert=0.0, animals_out=0.0, spark=False,
          loft_lit=False):
    """One 640x200 world frame. Modelled on render.draw_world but with the
    states the cold open needs: a dark house, a fire, a burning barn, and the
    node's red reflex."""
    img = _base(); d = ImageDraw.Draw(img)
    Rr = lambda x0, y0, x1, y1, c: d.rectangle([x0, y0, x1, y1], fill=c)
    for (sx, sy, ph) in R.STARS:
        if sy < 100:
            tw2 = 0.55 + 0.45 * math.sin(t * 1.7 + ph * 9.0)
            d.point((sx, sy), fill=C['starb'] if tw2 > 0.86 else C['star'])
    if not loft_lit:                        # _base lights the hayloft; at 02:40 nobody is up there
        Rr(BX + 42, BY + 11, BX + 50, BY + 21, C['bnr'])
    hx, hy = HOUSE
    if not house_lit:                       # nobody is awake. that is the argument.
        Rr(hx + 9, hy + 26, hx + 20, hy + 36, C['wd'])
        Rr(hx + 14, hy + 26, hx + 15, hy + 36, C['wd2'])
    # barn interior + sliding doors
    Rr(BX + 26, BY + 40, BX + 66, BY + 74, C['K'])
    if barn_open > 0.02:
        # a dark barn with a warm floor and stall posts -- filling the whole
        # doorway with C['lit'] made a flat orange slab once the animals left
        Rr(BX + 26, BY + 40, BX + 66, BY + 74, C['roof'])
        Rr(BX + 29, BY + 60, BX + 63, BY + 74, C['gl2'])
        Rr(BX + 32, BY + 66, BX + 60, BY + 74, C['gl'])
        for sx in (BX + 36, BX + 46, BX + 56):
            Rr(sx, BY + 43, sx + 1, BY + 73, C['wd'])
        if animals_out < 0.5:                          # a lamp on, not a light box
            Rr(BX + 42, BY + 45, BX + 50, BY + 51, C['lit'])
    px = img.load()
    if barn_open > 0.30 and animals_out < 0.5:
        blit(px, COW, BX + 30, BY + 52); blit(px, COW, BX + 47, BY + 54, flip=True, w=17)
        blit(px, CHICKEN, BX + 42, BY + 64); blit(px, CHICKEN, BX + 55, BY + 65, flip=True, w=9)
    dx = int(19 * barn_open)
    Rr(BX + 26, BY + 40, BX + 46 - dx, BY + 74, C['roof'])
    Rr(BX + 46 + dx, BY + 40, BX + 66, BY + 74, C['roof'])
    Rr(BX + 45 - dx, BY + 40, BX + 46 - dx, BY + 74, C['bn3'])
    Rr(BX + 46 + dx, BY + 40, BX + 47 + dx, BY + 74, C['bn3'])
    px = img.load()
    if animals_out > 0.01:                  # they walk out, and they are fine
        u = ease(min(1.0, animals_out))
        blit(px, COW, int(BX + 30 - 44 * u), BY + 66 + int(6 * u))
        blit(px, COW, int(BX + 52 + 30 * u), BY + 68 + int(4 * u), flip=True, w=17)
        blit(px, CHICKEN, int(BX + 40 - 60 * u), BY + 74 + int(4 * u))
        blit(px, CHICKEN, int(BX + 58 + 46 * u), BY + 73, flip=True, w=9)
    if farmer_x is not None:
        Rr(int(farmer_x) + 3, 158, int(farmer_x) + 11, 158, C['dirt'])
        blit(px, farmer(int((farmer_x // 5) % 2)), int(farmer_x), 138)
    # beetle + lantern on the post: amber asleep, red when the node acts
    bxx, byy = R.POST_X - 8, 107
    blit(px, R.BEETLE, bxx, byy)
    lx, ly = bxx + 18, byy + 4
    Rr(bxx + 16, byy + 4, bxx + 17, byy + 9, C['b']); Rr(bxx + 17, byy + 3, bxx + 19, byy + 4, C['B'])
    Rr(lx, ly, lx + 7, ly + 1, C['K']); Rr(lx, ly + 1, lx + 7, ly + 9, C['K'])
    lamp = C['dng'] if alert > 0.5 else C['gl']
    lamp2 = C['dng'] if alert > 0.5 else C['lit2']
    Rr(lx + 1, ly + 2, lx + 6, ly + 8, lamp); Rr(lx + 2, ly + 3, lx + 5, ly + 7, lamp2)
    Rr(lx + 3, ly - 2, lx + 5, ly - 1, C['K'])
    px = img.load()
    if burn > 0.0: burn_barn(img, burn, clean_px())   # before the fire: needs clean palette
    if fire > 0.0: draw_fire(img, fire, t)
    if spark: draw_spark(img, t)
    px = img.load()
    flick = 0.44 + 0.06 * math.sin(t * 11.0) + 0.03 * math.sin(t * 23.0)
    glow(px, lx + 3, ly + 5, 26 if alert > 0.5 else 22, lamp, flick + 0.25 * alert)
    if house_lit:
        glow(px, hx + 14, hy + 31, 15, C['lit'], 0.30)
    if barn_open > 0.05:
        glow(px, BX + 46, BY + 56, 30, C['gl'],
             0.40 * barn_open * (1.0 - 0.45 * min(1.0, animals_out)))
    return img


# ── HUD: the clock is the argument, the tag says which night ─────────────
def hud(fr, clock, *, sub=None, tag=None, tagcol='dim'):
    """A silent film cannot express a time DELTA without a clock on screen.
    And with the same shot playing twice, the viewer needs to know at a glance
    which of the two nights they are looking at -- hence the persistent tag."""
    d = ImageDraw.Draw(fr)
    if tag:
        w = tw(tag, 1)
        d.rectangle([0, 0, w + 11, 12], fill=C[tagcol])
        text(d, tag, 6, 3, (8, 8, 10), 1)
    w = tw(clock, 2)
    d.rectangle([W - w - 12, 6, W - 4, 6 + 16], fill=(0, 0, 0))
    text(d, clock, W - w - 8, 8, C['txt'], 2)
    if sub:
        w2 = tw(sub, 1)
        d.rectangle([W - w2 - 10, 26, W - 4, 26 + 8], fill=(0, 0, 0))
        text(d, sub, W - w2 - 7, 27, C['dim'], 1)
    return fr

def card(lines, a=1.0):
    """Black title card. A static line held in silence is the most
    room-quieting device available."""
    fr = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(fr)
    total = sum(s * 9 + 6 for _, s, _ in lines)
    y = (H - total) // 2
    for txt, s, col in lines:
        text(d, txt, (W - tw(txt, s)) // 2, y, tuple(int(c * a) for c in C[col]), s)
        y += s * 9 + 6
    return fr

def tc(sec):
    """02:40:00 style, from seconds after 02:40:00."""
    m = 40 + int(sec) // 60
    return "02:%02d:%02d" % (m, int(sec) % 60)


# ── cut 1: sequential — the same night, twice ────────────────────────────
# English on purpose: not all of the jury is Romanian. Place names keep their
# diacritics because they are proper nouns, and because a Romanian juror
# noticing that we spelled Timis correctly is worth more than it costs.
#
# The first half is built out of absence: the fire grows and nothing in the
# frame responds to it. That empty stretch IS the argument (F45 -- nobody is
# left to watch), so it is held longer than is comfortable. The camera never
# moves in either half.
# Every text hold is 3x what it was: on a projector, at the back of a room, a
# card that reads fine on a laptop is gone before anyone has finished it. The
# fades stay short so the extra time is spent at full opacity, not mid-dissolve.
D_OPEN  = 3.6                      # opening slate
D_STAMP = 2.4                      # each of the two timestamp cards
D_MID   = 3.0                      # "the same night, the same fault"
D_FINAL = 4.8                      # closing number
SKIP_HOLD = 0.75                   # each skipped clock stamp

CARD0  = D_OPEN
P1     = D_OPEN                    # locked shot, bad night
P1_LEN = 9.0 + 6 * SKIP_HOLD       # 9 s real time, then the clock runs away
P1_END = P1 + P1_LEN
CARDS  = P1_END                    # 08:30 / 11:00
MID    = CARDS + 2 * D_STAMP       # the restart, announced
P2     = MID + D_MID               # hard cut back, local2 starts at 3.2
P2_OFF = 3.2
ACT    = P2 + 1.4                  # the node acts. one frame.
END    = ACT + 3.0
TOTAL  = END + D_FINAL

TAG1, TAG1C = "WITHOUT BIOGUARD", 'dng'
TAG2, TAG2C = "WITH BIOGUARD",    'ok'

SKIPS = ["02:45", "03:10", "04:00", "05:30", "07:00", "08:30"]

def env(u, dur, fi=0.28, fo=0.30):
    """alpha envelope: quick in, long hold, quick out"""
    return max(0.0, min(1.0, u / fi, (dur - u) / fo))

def _p1_clock(local):
    if local < 9.0: return tc(local)
    i = min(len(SKIPS) - 1, int((local - 9.0) / SKIP_HOLD))
    return SKIPS[i]

def frame_seq(t):
    # ── opening card ────────────────────────────────────────────────────
    if t < CARD0:
        a = env(t, D_OPEN)
        return card([("02:40", 3, 'txt'),
                     ("A LIVESTOCK FARM — TIMIȘ COUNTY, ROMANIA", 1, 'dim')], a)
    # ── half one: the night nobody saw ──────────────────────────────────
    if t < P1_END:
        L = t - P1
        spark = 3.6 <= L < 3.75
        fire = 0.0
        if L >= 3.9:
            u = (L - 3.9) / 5.1                      # smoulder -> open fire
            fire = min(1.0, 0.04 + ease(min(1.0, u)) * 0.96)
        burn = 0.0 if L < 5.2 else min(0.95, ease(min(1.0, (L - 5.2) / 8.0)) * 0.95)
        fr = camera(scene(L, house_lit=False, fire=fire, burn=burn, spark=spark), *CAM)
        sub = "NOBODY WOKE UP" if L >= 9.0 else None
        return hud(fr, _p1_clock(L), sub=sub, tag=TAG1, tagcol=TAG1C)
    # ── the two timestamps that do all the work ─────────────────────────
    if t < MID:
        u = t - CARDS
        if u < D_STAMP:
            return card([("08:30", 3, 'dng'), ("SOMEONE FOUND THE FIRE", 1, 'txt')],
                        env(u, D_STAMP))
        return card([("11:00", 3, 'dng'), ("THE FIRE BRIGADE ARRIVED", 1, 'txt')],
                    env(u - D_STAMP, D_STAMP))
    # ── the restart, announced ──────────────────────────────────────────
    if t < P2:
        a = env(t - MID, D_MID)
        return card([("THE SAME NIGHT.", 2, 'txt'),
                     ("THE SAME FAULT.", 2, 'txt'),
                     ("€40 ON THE WALL.", 1, 'ok')], a)
    # ── half two: the same night, with the node ─────────────────────────
    L = P2_OFF + (t - P2)
    flash = 1.0 if ACT <= t < ACT + 1.0 / FPS else 0.0
    acted = t >= ACT
    spark = 3.6 <= L < 3.75
    fire = 0.0
    if L >= 3.9:
        fire = min(0.16, 0.04 + (L - 3.9) * 0.17)        # never gets past smoulder
    if acted:                                            # sprinkler + extraction
        fire = max(0.0, fire - (t - ACT) * 0.13)
    barn_open = ease(min(1.0, (t - ACT) / 0.8)) if acted else 0.0
    animals = min(1.0, max(0.0, (t - ACT - 0.6) / 2.0))
    fx = None
    if t >= ACT + 1.0:
        fx = 258 + ease(min(1.0, (t - ACT - 1.0) / 1.9)) * 122
    fr = camera(scene(L, house_lit=acted, loft_lit=acted, fire=fire, burn=0.0,
                      spark=spark, barn_open=barn_open, animals_out=animals,
                      farmer_x=fx, alert=1.0 if acted else 0.0), *CAM)
    if flash:                                            # one frame of red
        fr = Image.blend(fr, Image.new('RGB', (W, H), C['dng']), 0.62)
    sub = "THE NODE ACTED" if acted else None
    fr = hud(fr, tc(L), sub=sub, tag=TAG2, tagcol=TAG2C)
    if t >= END:                                         # the closing number
        a = min(1.0, (t - END) / 0.7)
        cd = card([("6 HOURS", 3, 'dng'), ("→", 3, 'dim'), ("1 SECOND", 3, 'ok')], 1.0)
        fr = Image.blend(fr, cd, min(1.0, a))
    return fr


def build(outdir):
    os.makedirs(outdir, exist_ok=True)
    n = int(TOTAL * FPS)
    for f in range(n):
        frame_seq(f / float(FPS)).resize((W * 4, H * 4), Image.NEAREST) \
            .save("%s/f%05d.png" % (outdir, f))
        if f % 60 == 0: print("frame", f, "/", n, flush=True)
    return n


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "still":
        frame_seq(float(a[1])).resize((W * 4, H * 4), Image.NEAREST) \
            .save("co_still_%s.png" % a[1])
        print("ok")
    else:
        build("co_frames")
