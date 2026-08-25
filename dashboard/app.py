#!/usr/bin/env python3
"""
Ferma Strajer - supervisory bridge + FIRMWARE TEST BENCH (laptop side).

Roles:
  1. Serial bridge: owns the USB link to the Arduino, rebroadcasts as SSE.
  2. Browser dashboard: floor plan, events, sim sliders, cyber demo (fallback UI).
  3. Firmware test bench (for Oleksandr): port picker, raw protocol console,
     conformance counters (unparsed lines flagged), scripted test sequences.
  4. Bridge for the Flutter app (same SSE + POST endpoints).

Run:
    python3 app.py --fake              # no hardware - UI dev / demo rehearsal
    python3 app.py                     # real firmware: pick the port in the UI
Open http://localhost:5001   (0.0.0.0 binding is default so the phone can join)

Deps:  pip install flask pyserial
"""
import argparse, glob, json, queue, random, threading, time
from collections import deque
from flask import Flask, Response, request

SECRET = b"STRAJER26"          # must match SECRET in the firmware

def crc8(data: bytes, crc: int = 0) -> int:
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def mac_for(counter: int, action: str) -> int:
    return crc8(SECRET, crc8(f"{counter}|{action}".encode()))

LOG_TYPES = {1:"BOOT",2:"MODE",3:"GAS",4:"INTRUDER",5:"TAMPER",
             6:"PIN_FAIL",7:"LOCKDOWN",8:"CMD_REJECT",9:"DISARM"}
KNOWN_UP = ("EVT|","TEL|","STATE|","SEC|","ACK|","NAK|","LOG|")

# ── shared state ─────────────────────────────────────────────────────────
state = {"mode":"?", "tel":{}, "log":[]}
events = deque(maxlen=200)
raw_log = deque(maxlen=400)          # {"dir":"rx"/"tx","line","t","ok"}
counters = {"rx":0, "tx":0, "unparsed":0}
subscribers = []
cmd_counter = int(time.time()) % 100000
last_sent = {"counter":0, "action":""}
lock = threading.Lock()

ser = None                # live pyserial handle
ser_port = None
ser_stop = threading.Event()
fake_on = False

def publish(msg: dict):
    for q in list(subscribers):
        try: q.put_nowait(msg)
        except queue.Full: pass

def now_t():
    return time.strftime("%H:%M:%S")

def push_raw(direction: str, line: str, ok: bool = True):
    rec = {"dir":direction, "line":line, "t":now_t(), "ok":ok}
    raw_log.append(rec)
    counters["rx" if direction=="rx" else "tx"] += 1
    if not ok: counters["unparsed"] += 1
    publish({"type":"raw", "raw":rec, "counters":counters})

def handle_line(line: str, from_serial=False):
    line = line.strip()
    if not line: return
    parsed = line.startswith(KNOWN_UP)
    if from_serial:
        push_raw("rx", line, ok=parsed)
    parts = line.split("|")
    if parts[0] == "TEL" and len(parts) > 1:
        tel = {}
        for kv in parts[1].split(","):
            if "=" not in kv: continue
            k, v = kv.split("=", 1)
            sim = v.endswith("s")
            if sim: v = v[:-1]
            try: tel[k] = {"v": float(v), "sim": sim, "age": time.time()}
            except ValueError: pass
        state["tel"] = tel
        publish({"type":"tel", "tel":tel})
    elif parts[0] == "STATE" and len(parts) > 1:
        state["mode"] = parts[1]
        publish({"type":"state", "mode":parts[1]})
    elif parts[0] in ("EVT","SEC","ACK","NAK"):
        ev = {"raw":line, "t":now_t(),
              "sev": parts[5] if parts[0]=="EVT" and len(parts)>5 else
                     ("SEC" if parts[0]=="SEC" else "INFO")}
        events.append(ev)
        publish({"type":"event", "event":ev})
    elif parts[0] == "LOG":
        if parts[1] == "END":
            publish({"type":"log", "log":state["log"]}); state["log"] = []
        elif len(parts) >= 6:
            state["log"].append({"slot":int(parts[1]),
                "what":LOG_TYPES.get(int(parts[2]) if parts[2].isdigit() else -1, parts[2]),
                "val":parts[3], "min":parts[4], "chain":parts[5]})

def send_raw(s: str):
    push_raw("tx", s)
    if ser:
        try: ser.write((s + "\n").encode())
        except Exception as e:
            publish({"type":"serial", "connected":False, "port":ser_port, "detail":f"write failed: {e}"})
    elif fake_on:
        fake_rx(s)

# ── serial management (test-bench core) ──────────────────────────────────
def list_ports():
    try:
        from serial.tools import list_ports as lp
        return [{"device":p.device, "desc":p.description} for p in lp.comports()]
    except Exception:
        return [{"device":d, "desc":""} for d in glob.glob("/dev/cu.usb*")]

def reader_loop(port, baud):
    global ser, ser_port
    import serial
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        publish({"type":"serial", "connected":False, "port":port, "detail":str(e)})
        return
    ser_port = port
    ser_stop.clear()
    publish({"type":"serial", "connected":True, "port":port, "detail":"connected"})
    events.append({"raw":f"DASH|serial connected {port}", "t":now_t(), "sev":"INFO"})
    try:
        while not ser_stop.is_set():
            line = ser.readline().decode(errors="replace")
            if line: handle_line(line, from_serial=True)
    except Exception as e:
        publish({"type":"serial", "connected":False, "port":port, "detail":f"lost: {e}"})
    finally:
        try: ser.close()
        except Exception: pass
        ser = None
        ser_port = None
        publish({"type":"serial", "connected":False, "port":None, "detail":"disconnected"})

# ── scripted test sequences (run against real firmware OR fake) ──────────
def script_gas_ramp():
    for v in (200, 350, 500, 650, 800, 900):
        send_raw(f"SIM|gas={v}"); time.sleep(1.5)
    time.sleep(4)
    for v in (500, 300, 120):
        send_raw(f"SIM|gas={v}"); time.sleep(1.5)

def script_replay():
    global cmd_counter
    with lock:
        cmd_counter += 1
        c = cmd_counter
    send_raw(f"CMD|{c}|{mac_for(c,'FAN_ON')}|FAN_ON"); time.sleep(1.5)
    send_raw(f"CMD|{c}|{mac_for(c,'FAN_ON')}|FAN_ON")          # replay -> reject
    time.sleep(1.5)
    send_raw(f"CMD|{c+999}|0|FAN_OFF")                          # bad MAC -> reject

def script_night_intruder():
    global cmd_counter
    with lock:
        cmd_counter += 1
        c = cmd_counter
    send_raw(f"CMD|{c}|{mac_for(c,'ARM')}|ARM"); time.sleep(2)
    send_raw("SIM|mot=1"); time.sleep(3); send_raw("SIM|mot=0")

def script_flame():
    send_raw("SIM|flame=1"); time.sleep(5); send_raw("SIM|flame=0")

SCRIPTS = {"gas_ramp":script_gas_ramp, "replay":script_replay,
           "night_intruder":script_night_intruder, "flame":script_flame}

# ── fake-data generator ──────────────────────────────────────────────────
fake = {"gas":120,"nh3":8,"flame":0,"t1":24,"t2":24,"hum":55,"water":600,
        "mot":0,"snd":0,"tamp":0,"fan":0,"relay":1,"vent":0,"mode":"DAY",
        "ctr":0, "sim":set(["nh3","flame"])}

def fake_rx(s: str):
    if s.startswith("SIM|"):
        k, v = s[4:].split("=");  fake[k] = float(v); fake["sim"].add(k)
    elif s.startswith("CMD|"):
        _, ctr, mac, action = s.split("|")
        ctr = int(ctr)
        if ctr <= fake["ctr"]:
            handle_line("SEC|REPLAY_REJECTED|STALE_COUNTER"); return
        if int(mac) != mac_for(ctr, action):
            handle_line("SEC|CMD_REJECTED|BAD_MAC"); return
        fake["ctr"] = ctr
        handle_line(f"ACK|{ctr}")
        if action == "ARM": fake["mode"] = "NIGHT"
        elif action == "DISARM": fake["mode"] = "DAY"
        elif action == "FAN_ON": fake["fan"] = 1
        elif action == "FAN_OFF": fake["fan"] = 0
        elif action == "VENT": fake["vent"] ^= 1
        elif action == "DUMPLOG":
            for i,(w,c) in enumerate([("BOOT","OK"),("MODE","OK"),("GAS","OK"),("CMD_REJECT","OK")]):
                state["log"].append({"slot":i,"what":w,"val":"0","min":str(i),"chain":c})
            publish({"type":"log","log":state["log"]}); state["log"] = []
        handle_line(f"STATE|{fake['mode']}")

def fake_loop():
    handle_line("STATE|DAY")
    while True:
        if ser:                       # real serial wins; fake sleeps
            time.sleep(1); continue
        f = fake
        if "gas" not in f["sim"]:
            f["gas"] = max(80, f["gas"] + random.randint(-15, 15))
        f["t1"] = 24 + random.randint(-1, 1)
        f["t2"] = f["t1"] + random.choice([0, 0, 1])
        if f["gas"] >= 700 and f["mode"] != "EMERGENCY":
            f["mode"] = "EMERGENCY"; f["relay"] = 0; f["fan"] = 1; f["vent"] = 1
            handle_line(f"EVT|0|pit|GAS_CRITICAL|{int(f['gas'])}|EMERG")
            handle_line("STATE|EMERGENCY")
        if f["gas"] < 400 and f["mode"] == "EMERGENCY":
            f["mode"] = "DAY"; f["relay"] = 1
            handle_line("EVT|0|pit|GAS_CLEARED|0|INFO"); handle_line("STATE|DAY")
        if f["flame"] and f["mode"] != "EMERGENCY":
            f["mode"] = "EMERGENCY"
            handle_line("EVT|0|store|FLAME_DETECTED|1|EMERG"); handle_line("STATE|EMERGENCY")
        if f["mot"] and f["mode"] == "NIGHT":
            handle_line("EVT|0|perim|INTRUDER|1|ALERT"); f["mot"] = 0
        tel = ",".join(f"{k}={int(f[k])}{'s' if k in f['sim'] else ''}"
                       for k in ("gas","nh3","flame","t1","t2","hum","water","mot","snd","tamp"))
        handle_line(f"TEL|{tel},fan={f['fan']},relay={f['relay']},vent={f['vent']},saved_pct={random.randint(60,70)}")
        time.sleep(1)

# ── flask ────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/stream")
def stream():
    q = queue.Queue(maxsize=200)
    subscribers.append(q)
    def gen():
        q.put({"type":"hello",
               "state":{"mode":state["mode"], "tel":state["tel"]},
               "events":list(events)[-30:], "raws":list(raw_log)[-100:],
               "counters":counters,
               "serial":{"connected":ser is not None, "port":ser_port}})
        try:
            while True:
                yield f"data: {json.dumps(q.get())}\n\n"
        finally:
            subscribers.remove(q)
    return Response(gen(), mimetype="text/event-stream")

@app.route("/ports")
def ports():
    return {"ports": list_ports(), "connected": ser is not None, "port": ser_port}

@app.route("/connect", methods=["POST"])
def connect():
    port = request.json["port"]
    if ser: ser_stop.set(); time.sleep(1.2)
    threading.Thread(target=reader_loop, args=(port, 115200), daemon=True).start()
    return {"ok": True}

@app.route("/disconnect", methods=["POST"])
def disconnect():
    ser_stop.set()
    return {"ok": True}

@app.route("/raw", methods=["POST"])
def raw():
    send_raw(request.json["line"].strip())
    return {"ok": True}

@app.route("/script", methods=["POST"])
def script():
    name = request.json["name"]
    if name not in SCRIPTS: return {"ok": False}, 404
    events.append({"raw":f"DASH|test sequence: {name}", "t":now_t(), "sev":"INFO"})
    publish({"type":"event","event":events[-1]})
    threading.Thread(target=SCRIPTS[name], daemon=True).start()
    return {"ok": True}

@app.route("/cmd", methods=["POST"])
def cmd():
    global cmd_counter
    action = request.json["action"]
    with lock:
        cmd_counter += 1
        last_sent.update(counter=cmd_counter, action=action)
        send_raw(f"CMD|{cmd_counter}|{mac_for(cmd_counter, action)}|{action}")
    return {"ok": True}

@app.route("/attack", methods=["POST"])
def attack():
    with lock:
        c, a = last_sent["counter"], last_sent["action"] or "FAN_OFF"
        if not last_sent["counter"]: c = 1
        send_raw(f"CMD|{c}|{mac_for(c, a)}|{a}")
    return {"ok": True}

@app.route("/sim", methods=["POST"])
def sim():
    d = request.json
    send_raw(f"SIM|{d['name']}={int(float(d['value']))}")
    return {"ok": True}

@app.route("/")
def index():
    return PAGE

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bio Guard — Bridge & Test Bench</title>
<style>
 :root{--bg:#0d1117;--card:#161b22;--line:#30363d;--tx:#e6edf3;--dim:#8b949e;
       --ok:#3fb950;--warn:#d29922;--alert:#f85149;--sim:#a371f7;--acc:#58a6ff}
 *{box-sizing:border-box;font-family:ui-monospace,Menlo,monospace}
 body{margin:0;background:var(--bg);color:var(--tx);padding:12px}
 h1{font-size:18px;margin:0 0 4px} .dim{color:var(--dim);font-size:12px}
 .row{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;flex:1;min-width:300px}
 #mode{font-size:26px;font-weight:bold;padding:8px 16px;border-radius:8px;display:inline-block}
 .DAY{background:#1f6feb33;color:#58a6ff}.NIGHT{background:#6e40c933;color:var(--sim)}
 .EMERGENCY{background:#f8514933;color:var(--alert);animation:bl 1s infinite}
 .LOCKDOWN{background:#d2992233;color:var(--warn)}
 @keyframes bl{50%{opacity:.4}}
 .zones{display:grid;grid-template-columns:1fr 1fr;gap:8px}
 .zone{border:2px solid var(--line);border-radius:8px;padding:10px;min-height:84px}
 .zone h3{margin:0 0 6px;font-size:13px;color:var(--dim)}
 .zone.warn{border-color:var(--warn)} .zone.alert{border-color:var(--alert);animation:bl 1s infinite}
 .v{font-size:15px} .simtag{color:var(--sim);font-size:10px;border:1px solid var(--sim);border-radius:4px;padding:0 4px;margin-left:4px}
 button{background:#21262d;color:var(--tx);border:1px solid var(--line);border-radius:6px;padding:8px 14px;cursor:pointer;font-size:13px;margin:2px}
 button:hover{background:#30363d} button.red{border-color:var(--alert);color:var(--alert)}
 button.acc{border-color:var(--acc);color:var(--acc)}
 select,input[type=text]{background:#0d1117;color:var(--tx);border:1px solid var(--line);border-radius:6px;padding:8px;font-size:13px}
 #log{height:200px;overflow-y:auto;font-size:12px;line-height:1.5}
 #console{height:260px;overflow-y:auto;font-size:12px;line-height:1.45;background:#0a0d10;
   border:1px solid var(--line);border-radius:6px;padding:8px;margin-top:8px}
 .rx{color:#7ee787}.tx{color:#79c0ff}.bad{color:var(--alert);font-weight:bold}
 .EMERG{color:var(--alert);font-weight:bold}.ALERT{color:var(--alert)}
 .WARN{color:var(--warn)}.SEC{color:var(--sim);font-weight:bold}.INFO{color:var(--dim)}
 input[type=range]{width:100%} .sl{margin:8px 0} .sl label{font-size:12px;color:var(--dim)}
 table{width:100%;font-size:12px;border-collapse:collapse}
 td,th{border-bottom:1px solid var(--line);padding:3px 6px;text-align:left}
 .OK{color:var(--ok)}.BROKEN{color:var(--alert);font-weight:bold}
 #energy{font-size:30px;color:var(--ok);font-weight:bold}
 #banner{display:none;position:fixed;inset:0 0 auto 0;z-index:9;padding:18px;text-align:center;
   font-size:22px;font-weight:bold;cursor:pointer}
 #banner.EMERG{display:block;background:var(--alert);color:#fff;animation:bl 1s infinite}
 #banner.ALERT{display:block;background:var(--warn);color:#000}
 #banner.SEC{display:block;background:var(--sim);color:#fff}
 .noenter{color:var(--alert);font-weight:bold;font-size:15px;border:2px dashed var(--alert);
   border-radius:6px;padding:2px 6px;display:inline-block;margin-top:4px}
 .pill{display:inline-block;border:1px solid var(--line);border-radius:20px;padding:3px 10px;font-size:12px;margin-left:6px}
 .pill.on{border-color:var(--ok);color:var(--ok)} .pill.off{border-color:var(--warn);color:var(--warn)}
</style></head><body>
<div id="banner" onclick="this.className=''"></div>
<h1>BIO GUARD <span class="dim">— bridge & firmware test bench</span>
 <span id="serialpill" class="pill off">serial: none</span>
 <span class="dim" id="stats"></span></h1>

<div class="row">
 <div class="card" style="flex:2">
  <div class="dim">ENGINEER — FIRMWARE TEST BENCH</div>
  <div style="margin:8px 0">
   <select id="ports" style="min-width:260px"></select>
   <button onclick="loadPorts()">refresh</button>
   <button class="acc" onclick="connectSer()">CONNECT</button>
   <button onclick="fetch('/disconnect',{method:'POST',headers:H})">disconnect</button>
  </div>
  <div class="dim">Test sequences (work on real firmware AND fake mode):</div>
  <div style="margin:6px 0">
   <button onclick="script('gas_ramp')">GAS RAMP 200→900→clear</button>
   <button onclick="script('replay')">CMD + REPLAY + BAD MAC</button>
   <button onclick="script('night_intruder')">ARM + INTRUDER</button>
   <button onclick="script('flame')">FLAME 5s</button>
   <button onclick="cmd('DUMPLOG')">AUDIT DUMP</button>
  </div>
  <div id="console"></div>
  <div style="margin-top:8px;display:flex;gap:6px">
   <input type="text" id="rawline" placeholder="raw line to firmware, e.g. SIM|gas=750 or garbage to test tolerance" style="flex:1"
     onkeydown="if(event.key=='Enter')sendRawLine()">
   <button class="acc" onclick="sendRawLine()">SEND</button>
  </div>
 </div>
 <div class="card" style="flex:0 0 260px"><div class="dim">MODE</div><div id="mode" class="DAY">—</div>
  <div style="margin-top:10px">
   <button onclick="cmd('ARM')">ARM night</button><button onclick="cmd('DISARM')">DISARM</button><br>
   <button onclick="cmd('FAN_ON')">FAN ON</button><button onclick="cmd('FAN_OFF')">FAN OFF</button>
   <button onclick="cmd('VENT')">VENT</button><br>
   <button class="red" onclick="fetch('/attack',{method:'POST',headers:H})">REPLAY ATTACK</button>
  </div>
  <div class="dim" style="margin-top:12px">ENERGY</div>
  <div id="energy">—</div><div class="dim">saved vs always-on</div>
 </div>
</div>

<div class="row">
 <div class="card"><div class="dim" style="margin-bottom:6px">FLOOR PLAN</div>
  <div class="zones">
   <div class="zone" id="z-hall"><h3>POULTRY HALL</h3><div class="v" id="v-hall">—</div></div>
   <div class="zone" id="z-pit"><h3>MANURE PIT</h3><div class="v" id="v-pit">—</div></div>
   <div class="zone" id="z-store"><h3>FEED & WATER STORE</h3><div class="v" id="v-store">—</div></div>
   <div class="zone" id="z-ctrl"><h3>CONTROL ROOM</h3><div class="v" id="v-ctrl">—</div></div>
  </div></div>
 <div class="card"><div class="dim">SIMULATED SENSORS <span class="simtag">SIM</span> — organizer-sanctioned stand-ins</div>
  <div class="sl"><label>NH3 ammonia (hall) — limit 25 ppm</label><input type="range" min="0" max="80" value="8" oninput="sim('nh3',this.value)"></div>
  <div class="sl"><label>Gas CH4 (pit)</label><input type="range" min="0" max="1023" value="120" oninput="sim('gas',this.value)"></div>
  <div class="sl"><label>Flame (store)</label><button onclick="sim('flame',1)">FLAME</button><button onclick="sim('flame',0)">clear</button>
   <label style="margin-left:14px">Motion</label><button onclick="sim('mot',1)">INTRUDER</button><button onclick="sim('mot',0)">clear</button></div>
 </div>
</div>

<div class="row">
 <div class="card"><div class="dim">EVENT LOG</div><div id="log"></div></div>
 <div class="card"><div class="dim">CHAINED AUDIT LOG (EEPROM)</div>
  <table id="audit"><tr><th>#</th><th>event</th><th>val</th><th>min</th><th>chain</th></tr></table></div>
</div>
<script>
const H={'Content-Type':'application/json'};
const cmd=a=>fetch('/cmd',{method:'POST',headers:H,body:JSON.stringify({action:a})});
const sim=(n,v)=>fetch('/sim',{method:'POST',headers:H,body:JSON.stringify({name:n,value:v})});
const script=n=>fetch('/script',{method:'POST',headers:H,body:JSON.stringify({name:n})});
const el=id=>document.getElementById(id);
function sendRawLine(){const i=el('rawline');if(!i.value.trim())return;
 fetch('/raw',{method:'POST',headers:H,body:JSON.stringify({line:i.value})});i.value='';}
async function loadPorts(){const r=await(await fetch('/ports')).json();
 el('ports').innerHTML=r.ports.map(p=>`<option value="${p.device}">${p.device} ${p.desc?'— '+p.desc:''}</option>`).join('')
   ||'<option value="">no ports found — is the UNO plugged in?</option>';}
function connectSer(){const p=el('ports').value;if(p)fetch('/connect',{method:'POST',headers:H,body:JSON.stringify({port:p})});}
function onSerial(s){const p=el('serialpill');
 p.className='pill '+(s.connected?'on':'off');
 p.textContent='serial: '+(s.connected?(s.port||'?'):(s.detail||'none'));}
function onRaw(r){const c=el('console');const d=document.createElement('div');
 d.className=r.ok?r.dir:'bad';
 d.textContent=`${r.t} ${r.dir==='rx'?'←':'→'} ${r.line}${r.ok?'':'   ⟵ UNPARSED'}`;
 c.appendChild(d);while(c.childNodes.length>400)c.removeChild(c.firstChild);
 c.scrollTop=c.scrollHeight;}
function onCounters(k){el('stats').textContent=` rx ${k.rx} · tx ${k.tx} · unparsed ${k.unparsed}`;
 el('stats').style.color=k.unparsed>0?'var(--alert)':'var(--dim)';}
function fmt(t,k,unit){if(!t[k])return '—';return t[k].v+unit+(t[k].sim?' <span class=simtag>SIM</span>':'')}
function onTel(t){
 el('v-hall').innerHTML=`NH3 ${fmt(t,'nh3',' ppm')}<br>T ${fmt(t,'t1','°')} / ${fmt(t,'t2','°')} · H ${fmt(t,'hum','%')}<br>snd ${fmt(t,'snd','')}`;
 el('v-pit').innerHTML=`CH4 ${fmt(t,'gas','')} <br>valve ${t.relay&&t.relay.v?'OPEN':'<b class=ALERT>CUT</b>'} · fan ${t.fan&&t.fan.v?'ON':'off'}`+
   (t.gas&&t.gas.v>=700?`<br><span class=noenter>DO NOT ENTER — rescuers are >1/4 of manure-gas victims</span>`:'');
 el('v-store').innerHTML=`water ${fmt(t,'water','')}<br>flame ${fmt(t,'flame','')}`;
 el('v-ctrl').innerHTML=`cabinet ${t.tamp&&t.tamp.v?'<b class=ALERT>OPEN</b>':'closed'} · vent ${t.vent&&t.vent.v?'open':'shut'}`;
 if(t.saved_pct)el('energy').textContent=t.saved_pct.v+'%';
 el('z-pit').className='zone'+(t.gas&&t.gas.v>=700?' alert':t.gas&&t.gas.v>=450?' warn':'');
 el('z-hall').className='zone'+(t.nh3&&t.nh3.v>=25?' warn':'');
 el('z-store').className='zone'+(t.flame&&t.flame.v>0?' alert':(t.water&&t.water.v<200?' warn':''));
 el('z-ctrl').className='zone'+(t.tamp&&t.tamp.v?' alert':'');
}
function banner(cls,msg){const b=el('banner');b.className=cls;b.textContent=msg+'  (tap to dismiss)';}
function onEvent(e,old){const d=document.createElement('div');d.className=e.sev;
 d.textContent=`${e.t}  ${e.raw}`;el('log').prepend(d);
 if(old)return;
 const p=e.raw.split('|');
 if(e.sev==='EMERG')banner('EMERG','EMERGENCY: '+(p[3]||'')+' — zone '+(p[2]||'?'));
 else if(e.sev==='ALERT')banner('ALERT','ALERT: '+(p[3]||'')+' — '+(p[2]||''));
 else if(e.sev==='SEC')banner('SEC','CYBER: '+p.slice(1).join(' · '));
 else if((p[3]||'').startsWith('GAS_CLEARED')||(p[3]||'')==='PIN_OK_DISARMED')el('banner').className='';}
function onLog(rows){const tb=el('audit');tb.innerHTML='<tr><th>#</th><th>event</th><th>val</th><th>min</th><th>chain</th></tr>';
 rows.filter(r=>r.chain!='EMPTY').forEach(r=>{tb.innerHTML+=`<tr><td>${r.slot}</td><td>${r.what}</td><td>${r.val}</td><td>${r.min}</td><td class=${r.chain}>${r.chain}</td></tr>`})}
function onMode(m){const e=el('mode');e.textContent=m;e.className=m;}
const es=new EventSource('/stream');
es.onmessage=ev=>{const m=JSON.parse(ev.data);
 if(m.type=='tel')onTel(m.tel);
 else if(m.type=='raw'){onRaw(m.raw);onCounters(m.counters);}
 else if(m.type=='state')onMode(m.mode);
 else if(m.type=='event')onEvent(m.event);
 else if(m.type=='log')onLog(m.log);
 else if(m.type=='serial')onSerial(m);
 else if(m.type=='hello'){onMode(m.state.mode);onTel(m.state.tel||{});
   (m.events||[]).forEach(e=>onEvent(e,true));(m.raws||[]).forEach(onRaw);
   onCounters(m.counters||{rx:0,tx:0,unparsed:0});onSerial(m.serial||{});}};
loadPorts();
</script></body></html>"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="serial port to auto-connect at startup (optional; UI can pick)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--fake", action="store_true", help="generated data, no Arduino")
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    if args.fake:
        fake_on = True
        threading.Thread(target=fake_loop, daemon=True).start()
    if args.port:
        threading.Thread(target=reader_loop, args=(args.port, args.baud), daemon=True).start()
    app.run(host=args.host, port=5001, threaded=True)
