"""SCAFFOLDING - ITS JOB IS DONE.  Main.tscn is the source of truth now.

This built the scene from nothing.  Running it again REGENERATES Main.tscn and
destroys anything edited in the Godot editor, so it refuses to run without
`--force`.  Reach for it only to rebuild the whole loop from scratch.

Kept for reference: it is the readable record of how every node, light, particle
system, shader and animation track in Main.tscn was derived from render.py.
"""
import sys
if "--force" not in sys.argv:
    raise SystemExit(
        "refusing to run: this OVERWRITES Main.tscn and any editor work in it.\n"
        "Main.tscn is the source of truth - edit it in Godot, or as text.\n"
        "Pass --force only to rebuild the entire scene from scratch."
    )

import os
S = "sprites"
ext = []; scripts = []; subres = []; nodes = []; tracks = []

def E(name):
    if name not in ext: ext.append(name)
    return f'ExtResource("{ext.index(name)+1}_{name}")'

def SC(path):
    if path not in scripts: scripts.append(path)
    return f'ExtResource("s{scripts.index(path)}")'

def SUB(text):
    subres.append(text)

def node(name, type_, parent=".", body=""):
    nodes.append(f'[node name="{name}" type="{type_}" parent="{parent}"]\n{body}')

def sprite(n, png, x, y, z=0, parent=".", extra=""):
    node(n, "Sprite2D", parent,
         f'position = Vector2({x}, {y})\ncentered = false\n'
         f'texture = {E(png)}\nz_index = {z}\n{extra}')

def track(path, keys, interp=1, update=0):
    times = ", ".join(str(t) for t, _ in keys)
    vals  = ", ".join(v for _, v in keys)
    trans = ", ".join("1" for _ in keys)
    i = len(tracks)
    tracks.append(f'tracks/{i}/type = "value"\ntracks/{i}/imported = false\n'
        f'tracks/{i}/enabled = true\ntracks/{i}/path = NodePath("{path}")\n'
        f'tracks/{i}/interp = {interp}\ntracks/{i}/loop_wrap = true\n'
        f'tracks/{i}/keys = {{\n"times": PackedFloat32Array({times}),\n'
        f'"transitions": PackedFloat32Array({trans}),\n"update": {update},\n'
        f'"values": [{vals}]\n}}\n')

def ease(u): return u*u*(3-2*u)

def bake(a, b, va, vb, step=0.4, fmt=None):
    """Sample a smoothstep move into linear keys.  Godot's cubic interp (interp=2)
    overshoots between equal keyframes; linear + baked keys reproduces render.py's
    ease() exactly and never leaves the world."""
    out = []; n = max(1, int(round((b-a)/step)))
    for i in range(n+1):
        t = a + (b-a)*i/n; u = ease(i/n)
        v = [va[k] + (vb[k]-va[k])*u for k in range(len(va))]
        out.append((round(t, 3), fmt(*v)))
    return out

# ── palette (mirrors render.py) ──────────────────────────────────────────
GL  = "Color(1, 0.659, 0.212, 1)"      # 255,168,54  lantern / barn fire
LIT = "Color(1, 0.769, 0.345, 1)"      # 255,196,88  window light
MOON= "Color(0.784, 0.843, 1, 1)"

# ── sub-resources: light cookie, particle ramps, shaders ─────────────────
# banded on purpose - render.py quantises its glow into 5 steps, keep the look
SUB('[sub_resource type="Gradient" id="Gradient_glow"]\n'
    'interpolation_mode = 1\n'
    'offsets = PackedFloat32Array(0, 0.2, 0.4, 0.6, 0.8, 1)\n'
    'colors = PackedColorArray(1, 1, 1, 1, 1, 1, 1, 0.64, 1, 1, 1, 0.36, '
    '1, 1, 1, 0.16, 1, 1, 1, 0.04, 1, 1, 1, 0)\n')
SUB('[sub_resource type="GradientTexture2D" id="Cookie"]\n'
    'gradient = SubResource("Gradient_glow")\nwidth = 128\nheight = 128\n'
    'fill = 1\nfill_from = Vector2(0.5, 0.5)\nfill_to = Vector2(1, 0.5)\n')
SUB('[sub_resource type="Gradient" id="Gradient_fade"]\n'
    'offsets = PackedFloat32Array(0, 0.22, 0.7, 1)\n'
    'colors = PackedColorArray(1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0)\n')
SUB('[sub_resource type="Gradient" id="Gradient_smoke"]\n'
    'offsets = PackedFloat32Array(0, 0.3, 1)\n'
    'colors = PackedColorArray(1, 1, 1, 0, 1, 1, 1, 0.5, 1, 1, 1, 0)\n')

SUB('[sub_resource type="Shader" id="Shader_stars"]\ncode = "shader_type canvas_item;\n'
    '// render.py redraws its starfield every frame, so sky.png has no stars at all -\n'
    '// the port lost them.  Generated here instead: procedural, per-star twinkle,\n'
    '// and it rides the parallax layer for free.\n'
    'uniform float density : hint_range(0.0, 0.05) = 0.008;\n'
    'uniform float twinkle : hint_range(0.0, 1.0) = 1.0;\n'
    'uniform vec3 star_dim : source_color = vec3(0.776, 0.824, 0.941);\n'
    'uniform vec3 star_hot : source_color = vec3(1.0, 0.988, 0.91);\n'
    'float h(vec2 p) { return fract(sin(dot(p, vec2(41.7, 289.3))) * 43758.5453); }\n'
    'void fragment() {\n'
    '\tvec4 c = texture(TEXTURE, UV);\n'
    '\tvec2 cell = floor(UV * vec2(640.0, 102.0));\n'
    '\t// thin out towards the horizon, where the sky washes out anyway\n'
    '\tfloat fade = 1.0 - smoothstep(0.45, 1.0, UV.y);\n'
    '\tif (h(cell) > 1.0 - density * fade) {\n'
    '\t\tfloat ph = h(cell + vec2(7.3, 1.9));\n'
    '\t\tfloat tw = 0.55 + 0.45 * sin(TIME * 1.7 + ph * 56.5);\n'
    '\t\tvec3 sc = tw > 0.86 ? star_hot : star_dim;\n'
    '\t\tc.rgb = mix(c.rgb, sc, mix(1.0, tw, twinkle) * c.a);\n'
    '\t}\n'
    '\tCOLOR = c;\n}\n"\n')
SUB('[sub_resource type="ShaderMaterial" id="Mat_stars"]\n'
    'shader = SubResource("Shader_stars")\nshader_parameter/density = 0.008\n'
    'shader_parameter/twinkle = 1.0\n'
    'shader_parameter/star_dim = Color(0.776, 0.824, 0.941, 1)\n'
    'shader_parameter/star_hot = Color(1, 0.988, 0.91, 1)\n')

SUB('[sub_resource type="Shader" id="Shader_vignette"]\ncode = "shader_type canvas_item;\n'
    '// quantised so it bands like the rest of the art instead of smearing.\n'
    'uniform float strength : hint_range(0.0, 1.0) = 0.34;\n'
    ''
    'void fragment() {\n'
    '\tfloat d = length(UV - vec2(0.5));\n'
    '\tfloat v = smoothstep(0.34, 0.9, d);\n'
    '\tCOLOR = vec4(0.02, 0.01, 0.05, v * strength);\n}\n"\n')
SUB('[sub_resource type="ShaderMaterial" id="Mat_vignette"]\n'
    'shader = SubResource("Shader_vignette")\nshader_parameter/strength = 0.34\n')

SUB('[sub_resource type="Shader" id="Shader_crt"]\ncode = "shader_type canvas_item;\n'
    '// makes the dashboard beat read as a screen, not a slide.\n'
    'uniform float scan : hint_range(0.0, 0.5) = 0.14;\n'
    'uniform float sweep : hint_range(0.0, 0.5) = 0.05;\n'
    'void fragment() {\n'
    '\tfloat fade = COLOR.a;   // carries the parent Control-s modulate\n'
    '\tfloat line = mod(FRAGCOORD.y, 3.0) < 1.0 ? scan : 0.0;\n'
    '\tfloat band = smoothstep(0.0, 0.06, abs(fract(UV.y - TIME * 0.12) - 0.5) - 0.44);\n'
    '\tvec4 c = vec4(0.0, 0.0, 0.0, line) + vec4(0.55, 0.85, 1.0, band * sweep);\n'
    '\tc.a *= fade;\n'
    '\tCOLOR = c;\n}\n"\n')
SUB('[sub_resource type="ShaderMaterial" id="Mat_crt"]\n'
    'shader = SubResource("Shader_crt")\nshader_parameter/scan = 0.14\n'
    'shader_parameter/sweep = 0.05\n')

# ── world (same coordinates as render.py) ────────────────────────────────
node("World", "Node2D")

# distant layers ride the camera a little -> depth during the long pan.
# base x is pulled left by scroll_scale * max_scroll so the far edge still covers.
# repeat_size tiles each layer, so coverage is guaranteed whatever scroll_scale
# is set to - drag the sliders in the inspector without opening a grey hole.
def plx(name, scale, z):
    node(name, "Parallax2D", "World",
         f'scroll_scale = Vector2({scale}, 1)\nrepeat_size = Vector2(640, 0)\n'
         f'repeat_times = 3\nz_index = {z}\n')

plx("Sky", 0.25, -20)
sprite("SkyArt", "sky", 0, 0, -20, "World/Sky", 'material = SubResource("Mat_stars")\n')
plx("Far", 0.5, -18)
sprite("HillsFar", "hills_far", 0, 95, -18, "World/Far")
plx("Near", 0.75, -17)
sprite("HillsNear", "hills_near", 0, 108, -17, "World/Near")

# moon stays in world space (a repeating parallax layer would clone it)
sprite("Moon", "moon", 541, 18, -19, "World")
node("MoonHalo", "PointLight2D", "World",
     f'position = Vector2(548, 26)\ncolor = {MOON}\nenergy = 0.55\n'
     f'blend_mode = 0\ntexture = SubResource("Cookie")\ntexture_scale = 0.55\n')

sprite("Ground", "ground", 0, 124, -16, "World")
sprite("Path", "path", 64, 152, -15, "World")
for i, x in enumerate(range(96, 392, 28)):
    sprite(f"Fence{i}", "fence", x, 128, -10, "World")
sprite("Post", "post", 250, 124, -9, "World")

node("Smoke", "CPUParticles2D", "World",
     'position = Vector2(69, 88)\nz_index = -9\namount = 10\nlifetime = 6.0\n'
     'preprocess = 5.0\nlifetime_randomness = 0.4\nrandomness = 0.6\n'
     f'texture = {E("puff")}\nemission_shape = 1\nemission_sphere_radius = 1.0\n'
     'direction = Vector2(0.35, -1)\nspread = 16.0\ngravity = Vector2(1.5, -4)\n'
     'initial_velocity_min = 3.0\ninitial_velocity_max = 6.0\n'
     'scale_amount_min = 0.5\nscale_amount_max = 1.2\n'
     'color = Color(0.55, 0.56, 0.62, 1)\ncolor_ramp = SubResource("Gradient_smoke")\n')

sprite("House", "house", 35, 90, -8, "World")
sprite("HouseDoorLit", "house_door_lit", 76, 134, -7, "World")
sprite("HouseDoor", "house_door", 76, 134, -6, "World")
sprite("BarnShell", "barn_shell", 384, 74, -8, "World")
sprite("BarnInterior", "barn_interior", 418, 118, -7, "World", 'visible = false\n')
sprite("Cow1", "cow", 422, 130, -6, "World", 'visible = false\n')
sprite("Cow2", "cow", 439, 132, -6, "World", 'visible = false\nflip_h = true\n')
sprite("Chicken1", "chicken", 434, 142, -5, "World", 'visible = false\n')
sprite("Chicken2", "chicken", 447, 143, -5, "World", 'visible = false\nflip_h = true\n')
sprite("BarnDoorL", "barn_door_l", 418, 118, -4, "World")
sprite("BarnDoorR", "barn_door_r", 438, 118, -4, "World")
node("Farmer", "AnimatedSprite2D", "World",
     'position = Vector2(88, 138)\ncentered = false\nz_index = -3\n'
     'sprite_frames = SubResource("SpriteFrames_farmer")\nanimation = &"walk"\n'
     'autoplay = "walk"\nvisible = false\n')
sprite("Beetle", "beetle", 242, 107, -2, "World")
sprite("Lantern", "lantern", 260, 111, -2, "World")

# ── lights: one per glow() call in render.py, but they actually light things ──
def light(name, x, y, col, r, energy, script=None, vis=True):
    node(name, "PointLight2D", "World",
         f'position = Vector2({x}, {y})\ncolor = {col}\nenergy = {energy}\n'
         f'blend_mode = 0\ntexture = SubResource("Cookie")\n'
         f'texture_scale = {round(2.0*r/128.0, 4)}\n'
         + (f'script = {SC(script)}\n' if script else "")
         + ("" if vis else "visible = false\n"))

light("LampLight",  263, 116, GL,  23, 1.6, script="Flicker.gd")
light("HouseWin",    49, 121, LIT, 18, 0.62)
light("HouseDoorLt", 82, 138, LIT, 17, 0.0)
light("BarnSpill",  430, 132, GL,  32, 0.0)
light("BarnTop",    430,  90, LIT, 12, 0.42)

node("Fireflies", "CPUParticles2D", "World",
     'position = Vector2(250, 132)\nz_index = -3\namount = 22\nlifetime = 7.0\n'
     'preprocess = 6.0\nlifetime_randomness = 0.6\nrandomness = 1.0\n'
     f'texture = {E("spark")}\nemission_shape = 3\n'
     'emission_rect_extents = Vector2(160, 16)\nspread = 180.0\n'
     'gravity = Vector2(0, 0)\ninitial_velocity_min = 2.0\ninitial_velocity_max = 7.0\n'
     'color = Color(1, 0.87, 0.36, 1)\ncolor_ramp = SubResource("Gradient_fade")\n')
node("BarnDust", "CPUParticles2D", "World",
     'position = Vector2(432, 140)\nz_index = -3\nvisible = false\namount = 16\n'
     'lifetime = 5.0\npreprocess = 4.0\nlifetime_randomness = 0.5\nrandomness = 0.8\n'
     f'texture = {E("spark")}\nemission_shape = 3\n'
     'emission_rect_extents = Vector2(15, 9)\nspread = 180.0\n'
     'gravity = Vector2(0, -3)\ninitial_velocity_min = 1.0\ninitial_velocity_max = 4.0\n'
     'color = Color(1, 0.8, 0.4, 0.8)\ncolor_ramp = SubResource("Gradient_fade")\n')

node("Camera2D", "Camera2D", ".",
     'position = Vector2(150, 112)\nlimit_left = 0\nlimit_top = 0\n'
     'limit_right = 640\nlimit_bottom = 200\nlimit_smoothed = false\n')

# ── overlays ─────────────────────────────────────────────────────────────
node("Grade", "CanvasLayer", ".", 'layer = 1\n')
node("Vignette", "ColorRect", "Grade",
     'material = SubResource("Mat_vignette")\noffset_right = 320.0\n'
     'offset_bottom = 180.0\ncolor = Color(1, 1, 1, 1)\n')

node("Overlay", "CanvasLayer", ".", 'layer = 2\n')
node("Dim", "ColorRect", "Overlay",
     'offset_right = 320.0\noffset_bottom = 180.0\n'
     'color = Color(0, 0, 0, 1)\nmodulate = Color(1, 1, 1, 0)\n')
node("Wordmark", "Sprite2D", "Overlay",
     f'position = Vector2(81, 24)\ncentered = false\ntexture = {E("wordmark")}\n'
     'modulate = Color(1, 1, 1, 0)\n')

node("Dashboard", "CanvasLayer", ".", 'layer = 3\n')
node("Root", "Control", "Dashboard",
     'offset_right = 320.0\noffset_bottom = 180.0\n'
     'mouse_filter = 2\nmodulate = Color(1, 1, 1, 0)\n')
node("Bg", "ColorRect", "Dashboard/Root",
     'offset_right = 320.0\noffset_bottom = 180.0\ncolor = Color(0.086, 0.098, 0.11, 1)\n')
node("HeaderBg", "ColorRect", "Dashboard/Root",
     'offset_right = 320.0\noffset_bottom = 13.0\ncolor = Color(0.114, 0.129, 0.145, 1)\n')

def dsprite(n, png, x, y, vis=True):
    node(n, "Sprite2D", "Dashboard/Root",
         f'position = Vector2({x}, {y})\ncentered = false\ntexture = {E(png)}\n'
         + ("" if vis else "visible = false\n"))

dsprite("HdrLogo", "hdr_logo", 6, 3); dsprite("HdrSite", "hdr_site", 78, 3)
dsprite("HdrArmed", "hdr_armed", 278, 3)
BAR = [(0.30, 'ok'), (0.18, 'ok'), (0.42, 'ok'), (0.64, 'warn')]
COL = {'ok': "Color(0.188, 0.82, 0.345, 1)", 'warn': "Color(1, 0.69, 0.125, 1)"}
for i, (lvl, col) in enumerate(BAR):
    y = 20 + i*13
    dsprite(f"Row{i}Name", f"row{i}_name", 8, y); dsprite(f"Row{i}Val", f"row{i}_val", 120, y)
    node(f"Bar{i}Bg", "ColorRect", "Dashboard/Root",
         f'offset_left = 170.0\noffset_top = {y+2}.0\noffset_right = 290.0\n'
         f'offset_bottom = {y+6}.0\ncolor = Color(0.114, 0.129, 0.145, 1)\n')
    node(f"Bar{i}", "ColorRect", "Dashboard/Root",
         f'offset_left = 170.0\noffset_top = {y+2}.0\noffset_right = {170+int(120*lvl)}.0\n'
         f'offset_bottom = {y+6}.0\ncolor = {COL[col]}\n')
node("Rule", "ColorRect", "Dashboard/Root",
     'offset_left = 8.0\noffset_top = 76.0\noffset_right = 312.0\n'
     'offset_bottom = 77.0\ncolor = Color(0.114, 0.129, 0.145, 1)\n')
for i in range(5): dsprite(f"Ev{i}", f"ev{i}", 8, 82+i*11, vis=False)
node("BannerBg", "ColorRect", "Dashboard/Root",
     'offset_left = 8.0\noffset_top = 154.0\noffset_right = 312.0\n'
     'offset_bottom = 170.0\ncolor = Color(0.114, 0.129, 0.145, 1)\nvisible = false\n')
dsprite("Banner", "banner", 14, 159, vis=False)
node("Crt", "ColorRect", "Dashboard/Root",
     'material = SubResource("Mat_crt")\noffset_right = 320.0\noffset_bottom = 180.0\n'
     'color = Color(1, 1, 1, 1)\n')

node("Fade", "CanvasLayer", ".", 'layer = 9\n')
node("Black", "ColorRect", "Fade",
     'offset_right = 320.0\noffset_bottom = 180.0\ncolor = Color(0, 0, 0, 1)\n')

# ── animation ────────────────────────────────────────────────────────────
V = lambda x, y: f"Vector2({x}, {y})"
A = lambda a: f"Color(1, 1, 1, {a})"

# camera: mirrors render.py exactly (follows the farmer, then pulls back on the
# beetle).  Baked to linear keys - cubic overshot and flew off the world.
def _fx(t): return 88 + ease(min(1.0, max(0.0, (t-5.6)/10.4)))*330

pan = [(0, 150.0)]
t = 5.6
while t <= 16.0001:
    pan.append((round(t, 2), max(150.0, min(480.0, _fx(t)+44)))); t += 0.4
pan += bake(16.0, 16.8, (462.0,), (480.0,), step=0.2, fmt=lambda x: x)[1:]
campos = [(t, V(round(x, 1), 112)) for t, x in pan] + [(24, V(480, 112))] \
    + bake(24, 28, (480.0, 112.0), (252.0, 122.0), step=0.25,
           fmt=lambda x, y: V(round(x, 1), round(y, 1)))[1:] \
    + [(39.9, V(252, 122))]
track("Camera2D:position", campos, interp=1)
track("Camera2D:zoom", [(0, V(1, 1)), (24, V(1, 1))]
      + bake(24, 28, (1.0, 1.0), (1.75, 1.75), step=0.25,
             fmt=lambda a, b: V(round(a, 3), round(b, 3)))[1:]
      + [(39.9, V(1.75, 1.75))], interp=1)

track("World/HouseDoor:scale",
      bake(4.4, 5.6, (1.0, 1.0), (0.12, 1.0), step=0.15,
           fmt=lambda a, b: V(round(a, 3), 1)), interp=1)
track("World/HouseDoorLt:energy",
      bake(4.4, 5.6, (0.0,), (0.48,), step=0.2, fmt=lambda a: str(round(a, 3))), interp=1)
track("World/Farmer:visible", [(0, "false"), (5.6, "true"), (20.5, "false")], update=1)
walk = [(round(5.6+0.4*k, 2), V(round(_fx(5.6+0.4*k), 1), 138)) for k in range(26)]
track("World/Farmer:position", walk + [(16, V(418, 138)), (20.5, V(436, 138))], interp=1)
track("World/BarnDoorL:position",
      bake(15, 17.4, (418.0, 118.0), (399.0, 118.0), step=0.2,
           fmt=lambda x, y: V(round(x, 1), 118)), interp=1)
track("World/BarnDoorR:position",
      bake(15, 17.4, (438.0, 118.0), (457.0, 118.0), step=0.2,
           fmt=lambda x, y: V(round(x, 1), 118)), interp=1)
track("World/BarnSpill:energy",
      bake(15, 17.4, (0.0,), (1.05,), step=0.2, fmt=lambda a: str(round(a, 3))), interp=1)
track("World/BarnInterior:visible", [(0, "false"), (15, "true")], update=1)
track("World/BarnDust:visible", [(0, "false"), (17.4, "true")], update=1)
for n in ("Cow1", "Cow2", "Chicken1", "Chicken2"):
    track(f"World/{n}:visible", [(0, "false"), (16, "true")], update=1)
track("Overlay/Wordmark:modulate", [(27, A(0)), (28.6, A(1)), (31, A(1)), (31.8, A(0))], interp=1)
track("Overlay/Dim:modulate", [(27, A(0)), (28.6, A(0.5)), (31, A(0.5)), (31.8, A(0))], interp=1)
track("Dashboard/Root:modulate", [(31, A(0)), (32, A(1)), (38.4, A(1)),
                                  (39.2, A(0))], interp=1)
for i, t in enumerate([32.4, 33.1, 33.8, 34.5, 35.2]):
    track(f"Dashboard/Root/Ev{i}:visible", [(0, "false"), (t, "true")], update=1)
track("Dashboard/Root/BannerBg:visible", [(0, "false"), (35.9, "true")], update=1)
track("Dashboard/Root/Banner:visible", [(0, "false"), (35.9, "true")], update=1)
for i, (lvl, _) in enumerate(BAR):
    base = 170 + int(120*lvl); y = 20 + i*13
    track(f"Dashboard/Root/Bar{i}:offset_right",
          [(0, str(base)), (3.1+i, str(base+5)), (6.2+i*1.3, str(base-4)),
           (9.4+i, str(base))], interp=1)
track("Fade/Black:color", [(0, "Color(0, 0, 0, 1)"), (0.9, "Color(0, 0, 0, 0)"),
                           (39.2, "Color(0, 0, 0, 0)"), (40, "Color(0, 0, 0, 1)")], interp=1)

anim = ('[sub_resource type="Animation" id="Animation_loop"]\n'
        'resource_name = "loop"\nlength = 40.0\nloop_mode = 1\nstep = 0.05\n'
        + "".join(tracks))
frames = ('[sub_resource type="SpriteFrames" id="SpriteFrames_farmer"]\n'
          'animations = [{\n"frames": [{\n"duration": 1.0,\n"texture": '
          + E("farmer_walk_a") + '\n}, {\n"duration": 1.0,\n"texture": '
          + E("farmer_walk_b") + '\n}],\n"loop": true,\n"name": &"walk",\n"speed": 7.0\n}]\n')
lib = ('[sub_resource type="AnimationLibrary" id="AnimLib"]\n'
       '_data = {\n"loop": SubResource("Animation_loop")\n}\n')

steps = len(ext) + len(scripts) + len(subres) + 3 + 1
head = f'[gd_scene load_steps={steps} format=3]\n\n'
head += "".join(f'[ext_resource type="Texture2D" path="res://sprites/{n}.png" id="{i+1}_{n}"]\n'
                for i, n in enumerate(ext))
head += "".join(f'[ext_resource type="Script" path="res://{p}" id="s{i}"]\n'
                for i, p in enumerate(scripts))
head += "\n" + "\n".join(subres) + "\n" + frames + "\n" + anim + "\n" + lib + "\n"
body = '[node name="Main" type="Node2D"]\n\n' + "\n".join(nodes) + "\n"
body += ('[node name="AnimationPlayer" type="AnimationPlayer" parent="."]\n'
         'libraries = {\n"": SubResource("AnimLib")\n}\n'
         'autoplay = "loop"\n')
open("Main.tscn", "w").write(head + body)
print(f"Main.tscn written: {len(ext)} textures, {len(subres)} sub-resources, "
      f"{len(tracks)} animation tracks")
