"""Bio Guard — attract loop renderer.  320x180 internal, nearest-upscaled.
Renders frames -> ffmpeg -> loop.mp4.  No browser, no engine, no assets."""
from PIL import Image, ImageDraw
import math, random, os, sys

W,H = 320,180                 # camera
WW,WH = 640,200               # world
FPS = 24

C = {
 'K':(12,10,12),
 'sky0':(10,15,31),'sky1':(16,25,48),'sky2':(26,36,64),'sky3':(38,49,82),
 'star':(198,210,240),'starb':(255,252,232),
 'moon':(232,226,190),'moonh':(255,252,232),
 'hillA':(13,25,27),'hillB':(18,34,34),
 'gr0':(20,42,32),'gr1':(26,52,38),'gr2':(16,34,27),
 'dirt':(46,35,25),'dirt2':(57,44,31),
 'wd':(52,34,24),'wd2':(70,47,32),'wd3':(88,60,40),'roof':(38,26,23),'roof2':(50,34,30),
 'bn':(74,29,27),'bn2':(94,38,34),'bn3':(116,48,42),'bnr':(40,27,25),'bnr2':(54,36,33),
 'lit':(255,196,88),'lit2':(255,228,158),'gl':(255,168,54),'gl2':(196,110,36),
 # beetle (from the app icon)
 'B':(132,79,44),'b':(94,54,29),'b2':(66,37,20),'S':(146,146,154),'s':(104,104,112),'s2':(74,74,82),
 'W':(244,248,252),
 # farmer
 'hat':(198,164,86),'hat2':(150,120,58),'skin':(226,180,140),'skin2':(176,132,98),
 'coat':(72,86,64),'coat2':(52,64,46),'trs':(48,54,74),'trs2':(34,40,56),'boot':(38,30,26),
 # livestock
 'cw':(226,226,222),'cw2':(178,178,176),'cwp':(58,44,38),'pink':(214,150,146),
 'ch':(238,238,232),'ch2':(190,190,186),'beak':(232,168,54),'comb':(206,64,52),
 # ui
 'ok':(48,209,88),'warn':(255,176,32),'dng':(255,69,58),'cyb':(191,90,242),
 'txt':(236,239,241),'dim':(152,161,168),'pnl':(22,25,28),'pnl2':(29,33,37),
}

# ── sprites: ASCII maps -> pixels ────────────────────────────────────────
def sprite(rows, key):
    """returns list of (x,y,colour)"""
    out=[]
    for y,r in enumerate(rows):
        for x,ch in enumerate(r):
            if ch in key: out.append((x,y,C[key[ch]]))
    return out

BEETLE = sprite([
 "......KK...KK.....",
 ".....KbBK.KBbK....",
 "......KBK.KBK.....",
 ".....KKBBBBBKK....",
 "....KKsSSSSKBK....",
 "...KSSSSSSSKBWK...",
 "...KSSSSSSSKBBK...",
 "..KKSSSSSSSSKKK...",
 "..KbSSSSSSSSSKK...",
 "..KbBSSSSSSSSBK...",
 "..KbBSsSSSSsSBK...",
 "..KbBSSSSSSSSBK...",
 "...KbBSSSSSSBK....",
 "....KbBBBBBBK.....",
 ".....KbB..BbK.....",
 ".....KbB..BbK.....",
 "....KKbK..KbKK....",
], {'K':'K','B':'B','b':'b','S':'S','s':'s','W':'W'})

def farmer(step):
    body = [
     ".....KKKKK....",
     "...KKhhhhhKK..",
     "..KhhhhhhhhhK.",
     "..KKhhhhhhhKK.",
     "....KKssKKK...",
     "....KsSSsK....",
     "....KsSSWK....",
     "....KKssKK....",
     "...KcCCCCcK...",
     "..KcCCCCCCcK..",
     "..KcCCCCCCcK..",
     "..KsCCCCCCcK..",
     "..KcCCCCCCcK..",
     "...KcCCCCcK...",
     "....KCCCCK....",
     "....KttttK....",
    ]
    legs_a = ["...KtTTtK.....","..KtTK.KtTK...","..KtTK.KtTK...","..KooK.KooK..."]
    legs_b = ["....KtTTtK....","...KtTTtK.....","...KtTTtK.....","...KooKKooK..."]
    rows = body + (legs_a if step else legs_b)
    return sprite(rows, {'K':'K','h':'hat','H':'hat','s':'skin2','S':'skin','W':'W',
                         'c':'coat2','C':'coat','t':'trs2','T':'trs','o':'boot'})

COW = sprite([
 "....KKKKKKKKKK....",
 "..KKwWWWWWWWWWKK..",
 ".KwWWppWWWWppWWK..",
 ".KWWWWWWWWWWWWWKK.",
 ".KWppWWWWWppWWWnK.",
 ".KWWWWWWWWWWWWKPK.",
 ".KwWWWWWWWWWWWKKK.",
 "..KWWKWWWWKWWK....",
 "..KooK.KooK.KoK...",
], {'K':'K','W':'cw','w':'cw2','p':'cwp','n':'cw','P':'pink','o':'cwp'})

CHICKEN = sprite([
 "...KrK....",
 "..KrrK....",
 ".KKCCKK...",
 "KCCCCCCK..",
 "KCCCCCCKb.",
 "KcCCCCCKK.",
 ".KCCCCCK..",
 "..KyKyK...",
], {'K':'K','C':'ch','c':'ch2','r':'comb','y':'beak','b':'beak'})

def blit(px, spr, ox, oy, flip=False, w=None):
    if flip and w is None: w=max(p[0] for p in spr)
    for x,y,c in spr:
        X = ox + ((w-x) if flip else x); Y = oy+y
        if 0<=X<WW and 0<=Y<WH: px[X,Y]=c

# ── world ────────────────────────────────────────────────────────────────
random.seed(11)
STARS=[(random.randrange(WW),random.randrange(0,78),random.random()) for _ in range(150)]
GRASS=[(random.randrange(WW),random.randrange(126,WH),random.choice([0,1,2])) for _ in range(700)]
HOUSE=(40,104); BARN=(392,78); POST_X=250
BASE_CACHE={}

def glow(px,cx,cy,r,col,strength):
    for y in range(max(0,cy-r),min(WH,cy+r)):
        for x in range(max(0,cx-r),min(WW,cx+r)):
            dd=math.hypot(x-cx,y-cy)
            if dd>r: continue
            step=1.0-(int(dd/(r/5.0))/5.0)
            a=strength*step*step
            if a<=0: continue
            o=px[x,y]
            px[x,y]=(min(255,int(o[0]+(col[0]-o[0])*a)),
                     min(255,int(o[1]+(col[1]-o[1])*a)),
                     min(255,int(o[2]+(col[2]-o[2])*a)))

def _base():
    """static layer: sky bands, hills, ground, path, buildings, fence"""
    if 'i' in BASE_CACHE: return BASE_CACHE['i'].copy()
    img=Image.new('RGB',(WW,WH),C['sky0']); d=ImageDraw.Draw(img)
    R=lambda x0,y0,x1,y1,c: d.rectangle([x0,y0,x1,y1],fill=c)
    for c,a,b in [('sky0',0,32),('sky1',32,58),('sky2',58,82),('sky3',82,102)]:
        R(0,a,WW,b,C[c])
    for lo,hi,y in [('sky0','sky1',32),('sky1','sky2',58),('sky2','sky3',82)]:
        for x in range(0,WW,2):
            d.point((x,y-1),fill=C[hi]); d.point((x+1,y),fill=C[lo])
    mx,my=548,26
    R(mx-6,my-4,mx+5,my+5,C['moon']); R(mx-4,my-6,mx+3,my+7,C['moon'])
    R(mx-4,my-4,mx-1,my-1,C['moonh']); R(mx+2,my+2,mx+3,my+4,C['moonh'])
    for x in range(WW):
        R(x,102+int(7*math.sin(x/46.)+3*math.sin(x/15.+1.2)),x,124,C['hillA'])
    for x in range(WW):
        R(x,113+int(4*math.sin(x/31.+2.4)+2*math.sin(x/11.)),x,128,C['hillB'])
    R(0,124,WW,WH,C['gr0'])
    for (gx,gy,k) in GRASS: R(gx,gy,gx+k,gy,C['gr1'] if k else C['gr2'])
    # walking path: a band, side-on
    R(64,152,470,164,C['dirt'])
    for i in range(260):
        rx=random.Random(i).randrange(64,470); ry=random.Random(i*7).randrange(152,164)
        R(rx,ry,rx+random.Random(i*3).choice([0,1]),ry,C['dirt2'])
    for x in range(64,470,3): d.point((x,151),fill=C['dirt2']); d.point((x+1,164),fill=C['dirt2'])
    # fence (midground, behind the walking lane)
    for fx in range(96,392,28):
        R(fx,128,fx+2,148,C['wd2']); R(fx,128,fx,148,C['wd'])
    for x0 in range(96,378,28):
        R(x0,132,x0+28,133,C['wd2']); R(x0,140,x0+28,141,C['wd'])
    # the beetle's post, taller
    R(POST_X,124,POST_X+3,149,C['wd3']); R(POST_X,124,POST_X,149,C['wd'])
    # house
    hx,hy=HOUSE
    R(hx,hy+18,hx+62,hy+46,C['wd'])
    for x in range(hx,hx+63,7): R(x,hy+18,x,hy+46,C['wd2'])
    for i in range(30): R(hx-5+i,hy+18-int(i*.95),hx+67-5-i,hy+19-int(i*.95),C['roof'])
    for i in range(0,30,6): R(hx-5+i,hy+18-int(i*.95),hx+67-5-i,hy+18-int(i*.95),C['roof2'])
    R(hx+26,hy-14,hx+31,hy-2,C['wd2'])
    R(hx+9,hy+26,hx+20,hy+36,C['lit']); R(hx+10,hy+27,hx+14,hy+31,C['lit2'])
    R(hx+14,hy+26,hx+15,hy+36,C['wd']); R(hx+9,hy+30,hx+20,hy+31,C['wd'])
    # barn shell
    bx,by=BARN
    R(bx,by+26,bx+92,by+74,C['bn'])
    for x in range(bx,bx+93,6): R(x,by+26,x,by+74,C['bn2'])
    R(bx,by+26,bx+92,by+27,C['bn3'])
    for i in range(30): R(bx-8+i,by+26-int(i*1.05),bx+100-8-i,by+27-int(i*1.05),C['bnr'])
    for i in range(0,30,7): R(bx-8+i,by+26-int(i*1.05),bx+100-8-i,by+26-int(i*1.05),C['bnr2'])
    R(bx+38,by+6,bx+54,by+26,C['bnr']); R(bx+42,by+11,bx+50,by+21,C['lit'])
    BASE_CACHE['i']=img
    return img.copy()

def draw_world(t, door_open, farmer_x, farmer_on, barn_open):
    img=_base(); d=ImageDraw.Draw(img)
    R=lambda x0,y0,x1,y1,c: d.rectangle([x0,y0,x1,y1],fill=c)
    for (sx,sy,ph) in STARS:
        if sy<100:
            tw2=0.55+0.45*math.sin(t*1.7+ph*9.0)
            d.point((sx,sy),fill=C['starb'] if tw2>0.86 else C['star'])
    hx,hy=HOUSE; bx,by=BARN
    # house door, swinging open
    R(hx+36,hy+30,hx+48,hy+46,C['roof'])
    dw=int(11*door_open)
    if dw>0:
        R(hx+36,hy+30,hx+36+dw,hy+46,C['lit'])
        if dw>=3: R(hx+37,hy+31,hx+35+dw,hy+45,C['lit2'])
        R(hx+36+dw,hy+30,hx+37+dw,hy+46,C['wd3'])
    # barn interior + sliding doors
    R(bx+26,by+40,bx+66,by+74,C['K'])
    if barn_open>0.02:
        R(bx+26,by+40,bx+66,by+74,C['gl2'])
        R(bx+29,by+43,bx+63,by+74,C['lit'])
    if barn_open>0.30:
        px=img.load()
        blit(px,COW,bx+30,by+52); blit(px,COW,bx+47,by+54,flip=True,w=17)
        blit(px,CHICKEN,bx+42,by+64); blit(px,CHICKEN,bx+55,by+65,flip=True,w=9)
    dx=int(19*barn_open)
    R(bx+26,by+40,bx+46-dx,by+74,C['roof']); R(bx+46+dx,by+40,bx+66,by+74,C['roof'])
    R(bx+45-dx,by+40,bx+46-dx,by+74,C['bn3']); R(bx+46+dx,by+40,bx+47+dx,by+74,C['bn3'])
    px=img.load()
    if farmer_on:
        R(int(farmer_x)+3,158,int(farmer_x)+11,158,C['dirt'])
        blit(px,farmer(int((farmer_x//6)%2)), int(farmer_x), 138)
    # beetle on its post
    bxx,byy=POST_X-8,107
    blit(px,BEETLE,bxx,byy)
    lx,ly=bxx+18,byy+4
    R(bxx+16,byy+4,bxx+17,byy+9,C['b']); R(bxx+17,byy+3,bxx+19,byy+4,C['B'])
    R(lx,ly,lx+7,ly+1,C['K']); R(lx,ly+1,lx+7,ly+9,C['K'])
    R(lx+1,ly+2,lx+6,ly+8,C['gl']); R(lx+2,ly+3,lx+5,ly+7,C['lit2'])
    R(lx+3,ly-2,lx+5,ly-1,C['K'])
    px=img.load()
    flick=0.44+0.06*math.sin(t*11.0)+0.03*math.sin(t*23.0)
    glow(px,lx+3,ly+5,22,C['gl'],flick)
    glow(px,hx+14,hy+31,15,C['lit'],0.30)
    if door_open>0.05: glow(px,hx+40,hy+38,16,C['lit'],0.26*door_open)
    if barn_open>0.05: glow(px,bx+46,by+56,30,C['gl'],0.40*barn_open)
    glow(px,bx+46,by+16,11,C['lit'],0.24)
    return img

def camera(world, cx, cy, zoom):
    cw,ch = W/zoom, H/zoom
    x0=max(0,min(WW-cw, cx-cw/2)); y0=max(0,min(WH-ch, cy-ch/2))
    crop=world.crop((int(x0),int(y0),int(x0+cw),int(y0+ch)))
    return crop.resize((W,H),Image.NEAREST)

def ease(u): return u*u*(3-2*u)

# ── wordmark + dashboard beat ────────────────────────────────────────────
FONT = {
 'A':["01110","10001","10001","11111","10001","10001","10001"],
 'B':["11110","10001","10001","11110","10001","10001","11110"],
 'C':["01110","10001","10000","10000","10000","10001","01110"],
 'D':["11110","10001","10001","10001","10001","10001","11110"],
 'E':["11111","10000","10000","11110","10000","10000","11111"],
 'F':["11111","10000","10000","11110","10000","10000","10000"],
 'G':["01110","10001","10000","10111","10001","10001","01111"],
 'H':["10001","10001","10001","11111","10001","10001","10001"],
 'I':["111","010","010","010","010","010","111"],
 'K':["10001","10010","10100","11000","10100","10010","10001"],
 'L':["10000","10000","10000","10000","10000","10000","11111"],
 'N':["10001","11001","11001","10101","10011","10011","10001"],
 'O':["01110","10001","10001","10001","10001","10001","01110"],
 'R':["11110","10001","10001","11110","10100","10010","10001"],
 'S':["01111","10000","10000","01110","00001","00001","11110"],
 'T':["11111","00100","00100","00100","00100","00100","00100"],
 'U':["10001","10001","10001","10001","10001","10001","01110"],
 'V':["10001","10001","10001","10001","10001","01010","00100"],
 'X':["10001","10001","01010","00100","01010","10001","10001"],
 'Z':["11111","00010","00100","01000","10000","10000","11111"],
 '0':["01110","10011","10101","10101","10101","11001","01110"],
 '1':["001","011","101","001","001","001","111"],
 '2':["01110","10001","00001","00010","00100","01000","11111"],
 '3':["11110","00001","00001","01110","00001","00001","11110"],
 '4':["00010","00110","01010","10010","11111","00010","00010"],
 ':':["0","1","0","0","0","1","0"],
 '.':["0","0","0","0","0","0","1"],
 '-':["000","000","000","111","000","000","000"],
 'J':["00111","00010","00010","00010","00010","10010","01100"],
 'M':["10001","11011","10101","10101","10001","10001","10001"],
 'P':["11110","10001","10001","11110","10000","10000","10000"],
 'Q':["01110","10001","10001","10001","10101","10010","01101"],
 'W':["10001","10001","10001","10101","10101","11011","10001"],
 'Y':["10001","10001","01010","00100","00100","00100","00100"],
 '5':["11111","10000","11110","00001","00001","10001","01110"],
 '6':["00110","01000","10000","11110","10001","10001","01110"],
 '7':["11111","00001","00010","00100","01000","01000","01000"],
 '8':["01110","10001","10001","01110","10001","10001","01110"],
 '9':["01110","10001","10001","01111","00001","00010","01100"],
 '/':["00001","00010","00010","00100","01000","01000","10000"],
 ' ':["00","00","00","00","00","00","00"],
}
def text(d, s, x, y, col, scale=1, sp=1):
    cx=x
    for ch in s.upper():
        g=FONT.get(ch,FONT[' '])
        for j,row in enumerate(g):
            for i,b in enumerate(row):
                if b=='1':
                    d.rectangle([cx+i*scale, y+j*scale, cx+(i+1)*scale-1, y+(j+1)*scale-1], fill=col)
        cx += (len(g[0])+sp)*scale
    return cx
def tw(s, scale=1, sp=1):
    return sum((len(FONT.get(c,FONT[' '])[0])+sp)*scale for c in s.upper())

def wordmark(frame, a):
    if a<=0.01: return frame
    ov=Image.new('RGB',(W,H),(0,0,0)); d=ImageDraw.Draw(ov)
    s=3; t1="BIO GUARD"
    text(d,t1,(W-tw(t1,s))//2,26,C['lit2'],s)
    t2="THE FARM THAT WATCHES ITSELF"
    text(d,t2,(W-tw(t2,1))//2,52,C['gl'],1)
    base=frame.point(lambda v:int(v*(1-0.5*a)))
    return _mix(base,ov,a)

def _mix(base, ov, a):
    bp=base.load(); op=ov.load()
    for y in range(H):
        for x in range(W):
            o=op[x,y]
            if o!=(0,0,0):
                b=bp[x,y]
                bp[x,y]=(int(b[0]+(o[0]-b[0])*a),int(b[1]+(o[1]-b[1])*a),int(b[2]+(o[2]-b[2])*a))
    return base

def dashboard(t, a):
    img=Image.new('RGB',(W,H),C['pnl']); d=ImageDraw.Draw(img)
    R=lambda x0,y0,x1,y1,c: d.rectangle([x0,y0,x1,y1],fill=c)
    R(0,0,W,13,C['pnl2']); text(d,"BIO GUARD",6,4,C['txt'],1)
    text(d,"FERMA STRAJER - HALA 1",78,4,C['dim'],1)
    text(d,"ARMED",W-40,4,C['ok'],1)
    rows=[("NH3 AMMONIA","12 PPM",'ok',0.30),("CH4 PIT","118",'ok',0.18),
          ("TEMP HALL","21.4 C",'ok',0.42),("VENT DUTY","64 PCT",'warn',0.64)]
    y=22
    for name,val,col,lvl in rows:
        text(d,name,8,y,C['dim'],1); text(d,val,120,y,C['txt'],1)
        bw=int(120*(lvl+0.02*math.sin(t*2.1+lvl*9)))
        R(170,y+1,290,y+5,C['pnl2']); R(170,y+1,170+bw,y+5,C[col])
        y+=13
    R(8,78,W-8,79,C['pnl2'])
    ev=[("03:12","TELEMETRY OK",'dim'),("03:14","INTRUDER - ZONE 3",'dng'),
        ("03:14","COMMAND REJECTED - BAD MAC",'cyb'),("03:14","REPLAY BLOCKED - CTR 4471",'cyb'),
        ("03:15","LOG CHAIN VERIFIED - INTACT",'ok')]
    y=86
    shown=int(min(len(ev), max(0,(t%12.0)-1.0)*1.1))
    for i,(tm,msg,col) in enumerate(ev[:shown]):
        text(d,tm,8,y,C['dim'],1); text(d,msg,40,y,C[col],1); y+=11
    if shown>=3:
        R(8,H-24,W-8,H-8,C['pnl2'])
        blink = 0.55+0.45*math.sin(t*4.0)
        cc = tuple(int(C['cyb'][k]*blink+C['pnl2'][k]*(1-blink)) for k in range(3))
        text(d,"ATTACK BLOCKED - FARM STILL RUNNING",14,H-19,cc,1)
    if a<1.0:
        return img.point(lambda v:int(v*a))
    return img

# ── timeline ─────────────────────────────────────────────────────────────
def build(outdir, seconds=40):
    os.makedirs(outdir,exist_ok=True)
    n=int(seconds*FPS)
    for f in range(n):
        t=f/float(FPS)
        door=0.0; fx=88.0; fon=False; barn=0.0
        camx,camy,zoom = 150,112,1.0
        if t<5.0:
            camx=150
        if 4.4<=t<5.6: door=ease(min(1,(t-4.4)/1.2))
        elif t>=5.6: door=1.0
        if 5.6<=t<16.0:
            fon=True; u=(t-5.6)/10.4
            fx=88+ease(u)*330
            camx=max(150,min(480,fx+44))
        elif t>=16.0:
            fon=True; fx=418; camx=480
        if 15.0<=t<17.4: barn=ease((t-15.0)/2.4)
        elif t>=17.4: barn=1.0
        if t>=21.0: fon=False           # he's inside
        if 24.0<=t<28.0:
            u=ease((t-24.0)/4.0)
            camx=480+(252-480)*u; camy=112+(122-112)*u; zoom=1.0+0.75*u
        elif t>=28.0:
            camx,camy,zoom=252,122,1.75
        world=draw_world(t,door,fx,fon,barn)
        fr=camera(world,camx,camy,zoom)
        if t>=27.0: fr=wordmark(fr, min(1.0,(t-27.0)/1.6))
        if t>=31.0:
            a=min(1.0,(t-31.0)/1.0)
            db=dashboard(t,1.0)
            fr=Image.blend(fr,db,a)
        if t>=38.5:                      # fade back for a seamless loop
            a=min(1.0,(t-38.5)/1.5)
            first=camera(draw_world(0,0,88,False,0),150,112,1.0)
            fr=Image.blend(fr,first,a)
        fr.resize((W*4,H*4),Image.NEAREST).save(f"{outdir}/f{f:05d}.png")
        if f%48==0: print("frame",f,"/",n,flush=True)
    return n

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--still":
        t=float(sys.argv[2]); 
        door = 1.0 if t>5.6 else 0.0
        barn = 1.0 if t>17.4 else 0.0
        fx = 88+min(1,max(0,(t-5.6)/10.4))*330
        w=draw_world(t,door,fx,5.6<t<21,barn)
        cam = 480 if t>16 else (150 if t<5 else min(480,fx+44))
        camera(w,cam,112,1.0).resize((W*4,H*4),Image.NEAREST).save(f"still_{int(t)}.png")
        print("ok")
    else:
        build("frames", 40)
