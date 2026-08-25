"""Export every drawn element of the attract loop as a transparent PNG,
so it can be assembled in Godot (or anywhere else) instead of recomputed."""
from PIL import Image, ImageDraw
import os, math, importlib.util
spec=importlib.util.spec_from_file_location("render", os.path.join(os.path.dirname(__file__),"render.py"))
R=importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
C=R.C
OUT=os.path.join(os.path.dirname(__file__),"sprites"); os.makedirs(OUT,exist_ok=True)

def from_sprite(spr, name, pad=0):
    w=max(p[0] for p in spr)+1+pad*2; h=max(p[1] for p in spr)+1+pad*2
    im=Image.new("RGBA",(w,h),(0,0,0,0))
    for x,y,c in spr: im.putpixel((x+pad,y+pad),c+(255,))
    im.save(f"{OUT}/{name}.png"); return im.size

def canvas(w,h):
    im=Image.new("RGBA",(w,h),(0,0,0,0)); return im, ImageDraw.Draw(im)

sizes={}
sizes['beetle']=from_sprite(R.BEETLE,'beetle')
sizes['farmer_walk_a']=from_sprite(R.farmer(1),'farmer_walk_a')
sizes['farmer_walk_b']=from_sprite(R.farmer(0),'farmer_walk_b')
sizes['cow']=from_sprite(R.COW,'cow')
sizes['chicken']=from_sprite(R.CHICKEN,'chicken')

# lantern (body only; the glow is a separate soft sprite)
im,d=canvas(9,12)
d.rectangle([0,0,7,1],fill=C['K']); d.rectangle([0,1,7,9],fill=C['K'])
d.rectangle([1,2,6,8],fill=C['gl']); d.rectangle([2,3,5,7],fill=C['lit2'])
d.rectangle([3,-2,5,-1],fill=C['K'])
im.save(f"{OUT}/lantern.png"); sizes['lantern']=im.size

# radial glow, 5 discrete rings (keeps the pixel banding)
r=32; im,d=canvas(r*2,r*2)
for y in range(r*2):
    for x in range(r*2):
        dd=math.hypot(x-r,y-r)
        if dd>r: continue
        step=1.0-(int(dd/(r/5.0))/5.0)
        a=int(255*step*step)
        if a>0: im.putpixel((x,y),C['gl']+(a,))
im.save(f"{OUT}/glow.png"); sizes['glow']=im.size

# house
im,d=canvas(72,64); hx,hy=5,0
d.rectangle([hx,hy+18,hx+62,hy+46],fill=C['wd'])
for x in range(hx,hx+63,7): d.rectangle([x,hy+18,x,hy+46],fill=C['wd2'])
for i in range(30): d.rectangle([hx-5+i,hy+18-int(i*.95),hx+67-5-i,hy+19-int(i*.95)],fill=C['roof'])
for i in range(0,30,6): d.rectangle([hx-5+i,hy+18-int(i*.95),hx+67-5-i,hy+18-int(i*.95)],fill=C['roof2'])
d.rectangle([hx+26,hy+2,hx+31,hy+14],fill=C['wd2'])
d.rectangle([hx+9,hy+26,hx+20,hy+36],fill=C['lit']); d.rectangle([hx+10,hy+27,hx+14,hy+31],fill=C['lit2'])
d.rectangle([hx+14,hy+26,hx+15,hy+36],fill=C['wd']); d.rectangle([hx+9,hy+30,hx+20,hy+31],fill=C['wd'])
im.save(f"{OUT}/house.png"); sizes['house']=im.size
im,d=canvas(12,16); d.rectangle([0,0,11,15],fill=C['roof']); im.save(f"{OUT}/house_door.png")

# barn shell (no doors) + the two sliding doors as separate sprites
im,d=canvas(100,102); bx,by=8,0
d.rectangle([bx,by+26,bx+92,by+74],fill=C['bn'])
for x in range(bx,bx+93,6): d.rectangle([x,by+26,x,by+74],fill=C['bn2'])
d.rectangle([bx,by+26,bx+92,by+27],fill=C['bn3'])
for i in range(30): d.rectangle([bx-8+i,by+26-int(i*1.05),bx+100-8-i,by+27-int(i*1.05)],fill=C['bnr'])
for i in range(0,30,7): d.rectangle([bx-8+i,by+26-int(i*1.05),bx+100-8-i,by+26-int(i*1.05)],fill=C['bnr2'])
d.rectangle([bx+38,by+6,bx+54,by+26],fill=C['bnr']); d.rectangle([bx+42,by+11,bx+50,by+21],fill=C['lit'])
im.save(f"{OUT}/barn_shell.png"); sizes['barn_shell']=im.size
for nm,edge in (("barn_door_l",'r'),("barn_door_r",'l')):
    im,d=canvas(20,35)
    d.rectangle([0,0,19,34],fill=C['roof'])
    d.rectangle([19,0,19,34] if edge=='r' else [0,0,0,34],fill=C['bn3'])
    im.save(f"{OUT}/{nm}.png"); sizes[nm]=im.size
im,d=canvas(40,34)                       # lit interior behind the doors
d.rectangle([0,0,39,33],fill=C['gl2']); d.rectangle([3,3,36,33],fill=C['lit'])
im.save(f"{OUT}/barn_interior.png"); sizes['barn_interior']=im.size

# fence section + post
im,d=canvas(28,21)
d.rectangle([0,0,2,20],fill=C['wd2']); d.rectangle([0,0,0,20],fill=C['wd'])
d.rectangle([0,4,27,5],fill=C['wd2']); d.rectangle([0,12,27,13],fill=C['wd'])
im.save(f"{OUT}/fence.png"); sizes['fence']=im.size
im,d=canvas(4,26); d.rectangle([0,0,3,25],fill=C['wd3']); d.rectangle([0,0,0,25],fill=C['wd'])
im.save(f"{OUT}/post.png"); sizes['post']=im.size

# background strips, full world width
im,d=canvas(R.WW,102)
for c,a,b in [('sky0',0,32),('sky1',32,58),('sky2',58,82),('sky3',82,102)]:
    d.rectangle([0,a,R.WW,b],fill=C[c])
for lo,hi,y in [('sky0','sky1',32),('sky1','sky2',58),('sky2','sky3',82)]:
    for x in range(0,R.WW,2): im.putpixel((x,y-1),C[hi]+(255,)); im.putpixel((x+1,y),C[lo]+(255,))
im.save(f"{OUT}/sky.png"); sizes['sky']=im.size
im,d=canvas(R.WW,30)
for x in range(R.WW): d.rectangle([x,int(7*math.sin(x/46.)+3*math.sin(x/15.+1.2))+7,x,29],fill=C['hillA'])
im.save(f"{OUT}/hills_far.png")
im,d=canvas(R.WW,26)
for x in range(R.WW): d.rectangle([x,int(4*math.sin(x/31.+2.4)+2*math.sin(x/11.))+5,x,25],fill=C['hillB'])
im.save(f"{OUT}/hills_near.png")
im,d=canvas(R.WW,80); d.rectangle([0,0,R.WW,80],fill=C['gr0'])
import random
for i in range(700):
    rr=random.Random(i); gx=rr.randrange(R.WW); gy=rr.randrange(0,80); k=rr.choice([0,1,2])
    d.rectangle([gx,gy,gx+k,gy],fill=C['gr1'] if k else C['gr2'])
im.save(f"{OUT}/ground.png"); sizes['ground']=im.size
im,d=canvas(406,14); d.rectangle([0,0,405,13],fill=C['dirt'])
for i in range(260):
    rr=random.Random(i*11); d.rectangle([rr.randrange(406),rr.randrange(14)]*2,fill=C['dirt2'])
im.save(f"{OUT}/path.png"); sizes['path']=im.size

# moon
im,d=canvas(14,16)
d.rectangle([1,3,12,12],fill=C['moon']); d.rectangle([3,1,10,14],fill=C['moon'])
d.rectangle([3,3,6,6],fill=C['moonh']); d.rectangle([9,9,10,11],fill=C['moonh'])
im.save(f"{OUT}/moon.png"); sizes['moon']=im.size

print(f"{len(os.listdir(OUT))} sprites -> {OUT}")
for k,v in sorted(sizes.items()): print(f"  {k:16s} {v}")

# ── text art: rendered with the loop's own pixel font, so Godot stays pixel-pure ──
def text_png(lines, name, pad=2):
    w=max(R.tw(t,s) for t,s,_ in lines)+pad*2
    h=sum(7*s+4 for _,s,_ in lines)+pad*2
    im=Image.new("RGBA",(w,h),(0,0,0,0)); d=ImageDraw.Draw(im)
    y=pad
    for t,s,col in lines:
        R.text(d,t,(w-R.tw(t,s))//2,y,col,s); y+=7*s+4
    im.save(f"{OUT}/{name}.png"); return im.size

print("wordmark", text_png([("BIO GUARD",3,C['lit2']),
                            ("THE FARM THAT WATCHES ITSELF",1,C['gl'])],"wordmark"))

def line_png(segs, name):
    w=sum(R.tw(t,1) for t,_ in segs)+4; im=Image.new("RGBA",(w,11),(0,0,0,0))
    d=ImageDraw.Draw(im); x=2
    for t,col in segs: x=R.text(d,t,x,2,col,1)
    im.save(f"{OUT}/{name}.png"); return im.size

EV=[("03:12 ","dim","TELEMETRY OK","dim"),
    ("03:14 ","dim","INTRUDER - ZONE 3","dng"),
    ("03:14 ","dim","COMMAND REJECTED - BAD MAC","cyb"),
    ("03:14 ","dim","REPLAY BLOCKED - CTR 4471","cyb"),
    ("03:15 ","dim","LOG CHAIN VERIFIED - INTACT","ok")]
for i,(tm,tc,msg,mc) in enumerate(EV):
    line_png([(tm,C[tc]),(msg,C[mc])], f"ev{i}")
line_png([("ATTACK BLOCKED - FARM STILL RUNNING",C['cyb'])],"banner")
for i,(nm,val) in enumerate([("NH3 AMMONIA","12 PPM"),("CH4 PIT","118"),
                             ("TEMP HALL","21.4 C"),("VENT DUTY","64 PCT")]):
    line_png([(nm,C['dim'])], f"row{i}_name"); line_png([(val,C['txt'])], f"row{i}_val")
line_png([("BIO GUARD",C['txt'])],"hdr_logo")
line_png([("FERMA STRAJER - HALA 1",C['dim'])],"hdr_site")
line_png([("ARMED",C['ok'])],"hdr_armed")
print("text sprites done")
