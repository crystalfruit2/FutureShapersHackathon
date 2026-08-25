"""Generates Main.tscn.  Run ONCE to scaffold; after that the .tscn is the source
of truth and you edit it in the Godot editor, not here."""
import os
S="sprites"
ext=[]; nodes=[]; tracks=[]
def E(name):
    if name not in ext: ext.append(name)
    return f'ExtResource("{ext.index(name)+1}_{name}")'
def sprite(node, png, x, y, z=0, parent=".", extra=""):
    nodes.append(f'[node name="{node}" type="Sprite2D" parent="{parent}"]\n'
                 f'position = Vector2({x}, {y})\ncentered = false\n'
                 f'texture = {E(png)}\nz_index = {z}\n{extra}')
def track(path, keys, interp=1, update=0):
    times=", ".join(str(t) for t,_ in keys)
    vals=", ".join(v for _,v in keys)
    trans=", ".join("1" for _ in keys)
    i=len(tracks)
    tracks.append(f'tracks/{i}/type = "value"\ntracks/{i}/imported = false\n'
        f'tracks/{i}/enabled = true\ntracks/{i}/path = NodePath("{path}")\n'
        f'tracks/{i}/interp = {interp}\ntracks/{i}/loop_wrap = true\n'
        f'tracks/{i}/keys = {{\n"times": PackedFloat32Array({times}),\n'
        f'"transitions": PackedFloat32Array({trans}),\n"update": {update},\n'
        f'"values": [{vals}]\n}}\n')

# ── world (same coordinates as render.py) ────────────────────────────────
nodes.append('[node name="World" type="Node2D" parent="."]\n')
sprite("Sky","sky",0,0,-20,"World")
sprite("Moon","moon",541,18,-19,"World")
sprite("HillsFar","hills_far",0,95,-18,"World")
sprite("HillsNear","hills_near",0,108,-17,"World")
sprite("Ground","ground",0,124,-16,"World")
sprite("Path","path",64,152,-15,"World")
for i,x in enumerate(range(96,392,28)):
    sprite(f"Fence{i}","fence",x,128,-10,"World")
sprite("Post","post",250,124,-9,"World")
sprite("House","house",35,90,-8,"World")
sprite("HouseDoorLit","house_door_lit",76,134,-7,"World")
sprite("HouseDoor","house_door",76,134,-6,"World")
sprite("BarnShell","barn_shell",384,74,-8,"World")
sprite("BarnInterior","barn_interior",418,118,-7,"World",'visible = false\n')
sprite("Cow1","cow",422,130,-6,"World",'visible = false\n')
sprite("Cow2","cow",439,132,-6,"World",'visible = false\nflip_h = true\n')
sprite("Chicken1","chicken",434,142,-5,"World",'visible = false\n')
sprite("Chicken2","chicken",447,143,-5,"World",'visible = false\nflip_h = true\n')
sprite("BarnDoorL","barn_door_l",418,118,-4,"World")
sprite("BarnDoorR","barn_door_r",438,118,-4,"World")
nodes.append('[node name="Farmer" type="AnimatedSprite2D" parent="World"]\n'
             'position = Vector2(88, 138)\ncentered = false\nz_index = -3\n'
             f'sprite_frames = SubResource("SpriteFrames_farmer")\nanimation = &"walk"\n'
             'autoplay = "walk"\nvisible = false\n')
sprite("Beetle","beetle",242,107,-2,"World")
sprite("Lantern","lantern",260,111,-2,"World")
sprite("Glow","glow",263,116,-1,"World",'centered = true\nmodulate = Color(1, 1, 1, 0.85)\n')

nodes.append('[node name="Camera2D" type="Camera2D" parent="."]\n'
             'position = Vector2(150, 112)\nlimit_left = 0\nlimit_top = 0\n'
             'limit_right = 640\nlimit_bottom = 200\nlimit_smoothed = false\n')

# ── overlays ─────────────────────────────────────────────────────────────
nodes.append('[node name="Overlay" type="CanvasLayer" parent="."]\nlayer = 2\n')
nodes.append('[node name="Dim" type="ColorRect" parent="Overlay"]\n'
             'offset_right = 320.0\noffset_bottom = 180.0\n'
             'color = Color(0, 0, 0, 1)\nmodulate = Color(1, 1, 1, 0)\n')
nodes.append('[node name="Wordmark" type="Sprite2D" parent="Overlay"]\n'
             f'position = Vector2(81, 24)\ncentered = false\ntexture = {E("wordmark")}\n'
             'modulate = Color(1, 1, 1, 0)\n')
nodes.append('[node name="Dashboard" type="CanvasLayer" parent="."]\nlayer = 3\n'
             'visible = false\n')
nodes.append('[node name="Bg" type="ColorRect" parent="Dashboard"]\n'
             'offset_right = 320.0\noffset_bottom = 180.0\ncolor = Color(0.086, 0.098, 0.11, 1)\n')
nodes.append('[node name="HeaderBg" type="ColorRect" parent="Dashboard"]\n'
             'offset_right = 320.0\noffset_bottom = 13.0\ncolor = Color(0.114, 0.129, 0.145, 1)\n')
def dsprite(node,png,x,y,vis=True):
    nodes.append(f'[node name="{node}" type="Sprite2D" parent="Dashboard"]\n'
                 f'position = Vector2({x}, {y})\ncentered = false\ntexture = {E(png)}\n'
                 + ("" if vis else "visible = false\n"))
dsprite("HdrLogo","hdr_logo",6,3); dsprite("HdrSite","hdr_site",78,3)
dsprite("HdrArmed","hdr_armed",278,3)
BAR=[(0.30,'ok'),(0.18,'ok'),(0.42,'ok'),(0.64,'warn')]
COL={'ok':"Color(0.188, 0.82, 0.345, 1)",'warn':"Color(1, 0.69, 0.125, 1)"}
for i,(lvl,col) in enumerate(BAR):
    y=20+i*13
    dsprite(f"Row{i}Name",f"row{i}_name",8,y); dsprite(f"Row{i}Val",f"row{i}_val",120,y)
    nodes.append(f'[node name="Bar{i}Bg" type="ColorRect" parent="Dashboard"]\n'
                 f'offset_left = 170.0\noffset_top = {y+2}.0\noffset_right = 290.0\n'
                 f'offset_bottom = {y+6}.0\ncolor = Color(0.114, 0.129, 0.145, 1)\n')
    nodes.append(f'[node name="Bar{i}" type="ColorRect" parent="Dashboard"]\n'
                 f'offset_left = 170.0\noffset_top = {y+2}.0\noffset_right = {170+int(120*lvl)}.0\n'
                 f'offset_bottom = {y+6}.0\ncolor = {COL[col]}\n')
nodes.append('[node name="Rule" type="ColorRect" parent="Dashboard"]\n'
             'offset_left = 8.0\noffset_top = 76.0\noffset_right = 312.0\n'
             'offset_bottom = 77.0\ncolor = Color(0.114, 0.129, 0.145, 1)\n')
for i in range(5): dsprite(f"Ev{i}",f"ev{i}",8,82+i*11,vis=False)
nodes.append('[node name="BannerBg" type="ColorRect" parent="Dashboard"]\n'
             'offset_left = 8.0\noffset_top = 154.0\noffset_right = 312.0\n'
             'offset_bottom = 170.0\ncolor = Color(0.114, 0.129, 0.145, 1)\nvisible = false\n')
dsprite("Banner","banner",14,159,vis=False)
nodes.append('[node name="Fade" type="CanvasLayer" parent="."]\nlayer = 9\n')
nodes.append('[node name="Black" type="ColorRect" parent="Fade"]\n'
             'offset_right = 320.0\noffset_bottom = 180.0\ncolor = Color(0, 0, 0, 1)\n')

# ── animation ────────────────────────────────────────────────────────────
V=lambda x,y: f"Vector2({x}, {y})"
A=lambda a: f"Color(1, 1, 1, {a})"
track("Camera2D:position",[(0,V(150,112)),(5.6,V(150,112)),(16,V(480,112)),
                           (24,V(480,112)),(28,V(252,122)),(39.9,V(252,122))],interp=2)
track("Camera2D:zoom",[(0,V(1,1)),(24,V(1,1)),(28,V(1.75,1.75)),(39.9,V(1.75,1.75))],interp=2)
track("World/HouseDoor:scale",[(4.4,V(1,1)),(5.6,V(0.12,1))],interp=1)
track("World/Farmer:visible",[(0,"false"),(5.6,"true"),(20.5,"false")],update=1)
track("World/Farmer:position",[(5.6,V(88,138)),(16,V(414,138)),(20.5,V(436,138))],interp=2)
track("World/BarnDoorL:position",[(15,V(418,118)),(17.4,V(399,118))],interp=2)
track("World/BarnDoorR:position",[(15,V(438,118)),(17.4,V(457,118))],interp=2)
track("World/BarnInterior:visible",[(0,"false"),(15,"true")],update=1)
for n in ("Cow1","Cow2","Chicken1","Chicken2"):
    track(f"World/{n}:visible",[(0,"false"),(16,"true")],update=1)
track("World/Glow:modulate",[(0,A(0.85)),(1.2,A(1.0)),(2.6,A(0.8)),(4.0,A(0.95)),
                             (5.4,A(0.82)),(6.8,A(1.0)),(8.0,A(0.85))],interp=1)
track("Overlay/Wordmark:modulate",[(27,A(0)),(28.6,A(1)),(31,A(1)),(31.8,A(0))],interp=1)
track("Overlay/Dim:modulate",[(27,A(0)),(28.6,A(0.5)),(31,A(0.5)),(31.8,A(0))],interp=1)
track("Dashboard:visible",[(0,"false"),(31.2,"true"),(38.9,"false")],update=1)
for i,t in enumerate([32.4,33.1,33.8,34.5,35.2]):
    track(f"Dashboard/Ev{i}:visible",[(0,"false"),(t,"true")],update=1)
track("Dashboard/BannerBg:visible",[(0,"false"),(35.9,"true")],update=1)
track("Dashboard/Banner:visible",[(0,"false"),(35.9,"true")],update=1)
for i,(lvl,_) in enumerate(BAR):
    base=170+int(120*lvl); y=20+i*13
    track(f"Dashboard/Bar{i}:offset_right",
          [(0,str(base)),(3.1+i,str(base+5)),(6.2+i*1.3,str(base-4)),(9.4+i,str(base))],interp=1)
track("Fade/Black:color",[(0,"Color(0, 0, 0, 1)"),(0.9,"Color(0, 0, 0, 0)"),
                          (38.9,"Color(0, 0, 0, 0)"),(40,"Color(0, 0, 0, 1)")],interp=1)

anim = ('[sub_resource type="Animation" id="Animation_loop"]\n'
        'resource_name = "loop"\nlength = 40.0\nloop_mode = 1\nstep = 0.05\n'
        + "".join(tracks))
frames = ('[sub_resource type="SpriteFrames" id="SpriteFrames_farmer"]\n'
          'animations = [{\n"frames": [{\n"duration": 1.0,\n"texture": '
          + E("farmer_walk_a") + '\n}, {\n"duration": 1.0,\n"texture": '
          + E("farmer_walk_b") + '\n}],\n"loop": true,\n"name": &"walk",\n"speed": 7.0\n}]\n')
lib = ('[sub_resource type="AnimationLibrary" id="AnimLib"]\n'
       '_data = {\n"loop": SubResource("Animation_loop")\n}\n')

head = f'[gd_scene load_steps={len(ext)+4} format=3]\n\n'
head += "".join(f'[ext_resource type="Texture2D" path="res://sprites/{n}.png" id="{i+1}_{n}"]\n'
                for i,n in enumerate(ext))
head += "\n" + frames + "\n" + anim + "\n" + lib + "\n"
body = '[node name="Main" type="Node2D"]\n\n' + "\n".join(nodes) + "\n"
body += ('[node name="AnimationPlayer" type="AnimationPlayer" parent="."]\n'
         'libraries = {\n"": SubResource("AnimLib")\n}\n'
         'autoplay = "loop"\n')
open("Main.tscn","w").write(head+body)
print(f"Main.tscn written: {len(ext)} textures, {len(tracks)} animation tracks")
