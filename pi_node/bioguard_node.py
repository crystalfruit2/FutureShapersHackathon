#!/usr/bin/env python3
"""
BioGuard device node — runs ON the Raspberry Pi. Python 3.7+, stdlib only.

This replaces the Arduino firmware. It is the REFLEX LAYER: it reads sensors,
actuates locally (fan/valve/vent/sprinkler) with no network needed, and speaks
the BioGuard line protocol to the laptop bridge over TCP.

    Pi:      python3 bioguard_node.py            # listens on 0.0.0.0:7777
    Laptop:  python3 dashboard/app.py --pi <pi-ip>   (or pick it in the UI)

OLEKSANDR — your part is ONLY the two marked sections below:
  1. SENSOR HOOKS  — make each read_*() return a real number (or leave None:
     that channel then runs simulated / driven by the dashboard SIM sliders,
     which is organizer-sanctioned for missing sensors).
  2. ACTUATOR HOOKS — put your GPIO writes inside set_*(). They currently
     just print, so the node runs fine on any machine for testing.

Everything else (protocol, security, emergency logic) is done — don't edit
below the hooks unless we talk first. Test without hardware:
    python3 bioguard_node.py        # on your laptop — all channels simulated

Protocol (newline-terminated, one line each way):
  up:   TEL|k=v,...   EVT|slot|zone|WHAT|val|SEV   STATE|MODE
        SEC|...       ACK|ctr    LOG|slot|type|val|min|chain    LOG|END
  down: CMD|counter|mac|ACTION   SIM|key=val   FW|version|signature
Security: every CMD carries crc8(SECRET, crc8("counter|action")) and a
monotonic counter — replays and forged MACs are rejected ON THIS DEVICE.
"""
import random, socket, threading, time

SECRET = b"STRAJER26"        # must match the bridge
PORT   = 7777
TICK   = 1.0                 # seconds per control-loop cycle

# ── SENSOR HOOKS (Oleksandr) ─────────────────────────────────────────────
# Return a float, or None to keep that channel simulated / SIM-driven.
def read_gas():   return None   # CH4, manure pit      (a.u., critical 700)
def read_nh3():   return None   # NH3, poultry hall    (ppm, limit 25)
def read_flame(): return None   # flame, feed store    (0/1)
def read_t1():    return None   # temp 1, hall         (°C)
def read_t2():    return None   # temp 2, hall         (°C)
def read_hum():   return None   # humidity, hall       (%)
def read_water(): return None   # water level, store   (%)
def read_mot():   return None   # motion, perimeter    (0/1)
def read_snd():   return None   # sound level, hall    (a.u.)
def read_tamp():  return None   # cabinet tamper       (0/1)

# ── ACTUATOR HOOKS (Oleksandr) ───────────────────────────────────────────
# Called with True/False on every change. Put GPIO writes here.
def set_fan(on):       print(f"[gpio] pit fan      -> {'ON' if on else 'off'}")
def set_relay(on):     print(f"[gpio] gas valve    -> {'OPEN' if on else 'CUT'}")
def set_vent(on):      print(f"[gpio] vent flap    -> {'open' if on else 'shut'}")
def set_cfan(on):      print(f"[gpio] exhaust fan  -> {'ON' if on else 'off'}")
def set_sprinkler(on): print(f"[gpio] sprinkler    -> {'ON' if on else 'off'}")
def set_light(on):     print(f"[gpio] hall light   -> {'ON' if on else 'off'}")
def set_buzzer(on):    print(f"[gpio] buzzer+red   -> {'ON' if on else 'off'}")

# ═════════════════════ no user-serviceable parts below ═══════════════════

def crc8(data, crc=0):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def mac_for(counter, action):
    return crc8(SECRET, crc8(f"{counter}|{action}".encode()))

def fw_sig(ver):
    return crc8(SECRET, crc8(ver.encode()))

READERS = {"gas":read_gas, "nh3":read_nh3, "flame":read_flame, "t1":read_t1,
           "t2":read_t2, "hum":read_hum, "water":read_water, "mot":read_mot,
           "snd":read_snd, "tamp":read_tamp}
ACTUATORS = {"fan":set_fan, "relay":set_relay, "vent":set_vent,
             "cfan":set_cfan, "spr":set_sprinkler, "light":set_light}

S = {"gas":120.0,"nh3":8.0,"flame":0.0,"t1":24.0,"t2":24.0,"hum":55.0,
     "water":72.0,"food":58.0,"mot":0.0,"snd":0.0,"tamp":0.0}
A = {"fan":0,"relay":1,"vent":0,"cfan":0,"spr":0,"light":1}
sim_driven = set()               # channels pinned by dashboard SIM sliders
mode = "DAY"
premode = "DAY"
last_ctr = 0
fw_version = "1.3"
audit = []                       # (type_code, val) ring, chained CRC
lock = threading.Lock()
clients = []

LOGT = {"BOOT":1,"MODE":2,"GAS":3,"INTRUDER":4,"TAMPER":5,
        "PIN_FAIL":6,"LOCKDOWN":7,"CMD_REJECT":8,"DISARM":9}

def send(line):
    dead = []
    for c in list(clients):
        try: c.sendall((line + "\n").encode())
        except OSError: dead.append(c)
    for c in dead:
        try: clients.remove(c); c.close()
        except (ValueError, OSError): pass

def log_event(what, val):
    chain = audit[-1][3] if audit else 0
    chain = crc8(f"{what}|{val}".encode(), chain)
    audit.append((len(audit), LOGT.get(what, 0), val, chain))
    if len(audit) > 16: audit.pop(0)

def evt(zone, what, val, sev):
    send(f"EVT|0|{zone}|{what}|{val}|{sev}")

def set_actuator(name, on):
    on = 1 if on else 0
    if A[name] != on:
        A[name] = on
        ACTUATORS[name](bool(on))

def set_mode(m):
    global mode
    if mode != m:
        mode = m
        log_event("MODE", m)
        send(f"STATE|{m}")
        set_buzzer(m in ("EMERGENCY", "LOCKDOWN"))

def enter_lockdown(reason):
    global premode
    if mode != "LOCKDOWN":
        if mode != "EMERGENCY": premode = mode
        set_actuator("fan", 1)       # air always
        set_actuator("spr", 0)       # pump off — no flooding
        log_event("LOCKDOWN", reason)
        send(f"SEC|LOCKDOWN|{reason}")
        evt("ctrl", "LOCKDOWN", 3, "ALERT")
        set_mode("LOCKDOWN")

def handle_cmd(ctr, mac, action):
    global last_ctr, premode
    if ctr <= last_ctr:
        send("SEC|REPLAY_REJECTED|STALE_COUNTER"); return
    if mac != mac_for(ctr, action):
        send("SEC|CMD_REJECTED|BAD_MAC"); return
    last_ctr = ctr
    if mode == "LOCKDOWN" and action not in ("UNLOCK", "FAN_ON"):
        log_event("CMD_REJECT", action)
        send(f"SEC|CMD_REJECT|LOCKDOWN|{action}"); return
    send(f"ACK|{ctr}")
    if   action == "ARM":     premode = "NIGHT"; set_mode("NIGHT")
    elif action == "DISARM":  premode = "DAY"; log_event("DISARM","OK"); set_mode("DAY")
    elif action == "LOCKDOWN": enter_lockdown("BRIDGE_ORDER")
    elif action == "UNLOCK":
        if mode == "LOCKDOWN":
            send("SEC|LOCKDOWN_CLEARED|ADMIN_PIN"); set_mode(premode)
    elif action == "FAN_ON":   set_actuator("fan", 1)
    elif action == "FAN_OFF":  set_actuator("fan", 0)
    elif action == "VENT":     set_actuator("vent", not A["vent"])
    elif action == "CFAN_ON":  set_actuator("cfan", 1)
    elif action == "CFAN_OFF": set_actuator("cfan", 0)
    elif action == "LIGHT_ON": set_actuator("light", 1)
    elif action == "LIGHT_OFF":set_actuator("light", 0)
    elif action == "SPRINKLER_ON":  set_actuator("spr", 1)
    elif action == "SPRINKLER_OFF": set_actuator("spr", 0)
    elif action == "REFILL_WATER":
        S["water"] = 100; evt("hall", "WATER_REFILLED", 100, "INFO")
    elif action == "REFILL_FOOD":
        S["food"] = 100; evt("hall", "FOOD_REFILLED", 100, "INFO")
    elif action == "DUMPLOG":
        for slot, code, val, chain in audit:
            send(f"LOG|{slot}|{code}|{val}|{slot}|OK")
        send("LOG|END")

def handle_line(line):
    line = line.strip()
    try:
        if line.startswith("CMD|"):
            _, ctr, mac, action = line.split("|")
            with lock: handle_cmd(int(ctr), int(mac), action)
        elif line.startswith("SIM|"):
            k, v = line[4:].split("=")
            with lock:
                if k in S: S[k] = float(v); sim_driven.add(k)
        elif line.startswith("FW|"):
            _, ver, sig = line.split("|")
            with lock:
                global fw_version
                if int(sig) == fw_sig(ver):
                    fw_version = ver
                    evt("ctrl", "FW_VERIFIED", f"v{ver}", "INFO")
                else:
                    send("SEC|FW_REJECTED|BAD_SIGNATURE")
    except (ValueError, IndexError):
        send("SEC|CMD_REJECTED|MALFORMED")

def sample():
    """Real sensor where wired; SIM-pinned value where driven; gentle noise else."""
    for k, reader in READERS.items():
        try: v = reader()
        except Exception: v = None          # a dying sensor must not kill the loop
        if v is not None:
            S[k] = float(v); sim_driven.discard(k)
        elif k not in sim_driven:
            if k == "gas":
                S["gas"] = max(80, S["gas"] + (120 - S["gas"]) * 0.15 + random.uniform(-5, 5))
            elif k == "t1":
                S["t1"] = 24 + random.randint(-1, 1); S["t2"] = S["t1"]

def reflex():
    """The layer the pitch is about: acts locally, needs no network."""
    if S["gas"] >= 700 and mode != "EMERGENCY":
        global premode
        if mode != "LOCKDOWN": premode = mode
        set_actuator("relay", 0); set_actuator("fan", 1); set_actuator("vent", 1)
        log_event("GAS", int(S["gas"]))
        evt("pit", "GAS_CRITICAL", int(S["gas"]), "EMERG")
        set_mode("EMERGENCY")
    if mode == "EMERGENCY" and S["gas"] < 400 and not S["flame"]:
        set_actuator("relay", 1); set_actuator("spr", 0)
        evt("pit", "GAS_CLEARED", 0, "INFO")
        set_mode(premode)
    if S["flame"] and mode != "EMERGENCY":
        if mode != "LOCKDOWN": premode = mode
        set_actuator("relay", 0); set_actuator("fan", 1)
        set_actuator("vent", 1); set_actuator("spr", 1)
        evt("store", "FLAME_DETECTED", 1, "EMERG")
        set_mode("EMERGENCY")
    if S["nh3"] >= 25:
        set_actuator("fan", 1)
    if S["mot"] and mode == "NIGHT":
        log_event("INTRUDER", 1)
        evt("perim", "INTRUDER", 1, "ALERT")
        S["mot"] = 0; sim_driven.discard("mot")
    if S["tamp"] and mode == "NIGHT":
        log_event("TAMPER", 1)
        evt("ctrl", "TAMPER", 1, "ALERT")

def telemetry():
    # 's' suffix marks a channel currently pinned by a dashboard SIM slider
    parts = [f"{k}={int(S[k])}{'s' if k in sim_driven else ''}"
             for k in ("gas","nh3","flame","t1","t2","hum","water","food","mot","snd","tamp")]
    parts.append(f"light={A['light']}")
    saved = 70 - 10 * (A["fan"] + A["cfan"])  # crude: running fans cost energy
    send("TEL|" + ",".join(parts) +
         f",fan={A['fan']},relay={A['relay']},vent={A['vent']},"
         f"cfan={A['cfan']},spr={A['spr']},saved_pct={max(40, saved)}")

def control_loop():
    while True:
        with lock:
            sample()
            reflex()
            telemetry()
        time.sleep(TICK)

def client_thread(conn, addr):
    print(f"[net] bridge connected: {addr[0]}")
    clients.append(conn)
    with lock:
        send(f"STATE|{mode}")
        evt("ctrl", "NODE_ONLINE", fw_version, "INFO")
    buf = b""
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk: break
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                handle_line(raw.decode(errors="replace"))
    except OSError:
        pass
    finally:
        try: clients.remove(conn); conn.close()
        except (ValueError, OSError): pass
        print(f"[net] bridge disconnected: {addr[0]}")

def main():
    log_event("BOOT", "OK")
    threading.Thread(target=control_loop, daemon=True).start()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(2)
    print(f"BioGuard node up — waiting for the bridge on :{PORT} "
          f"(reflex layer runs regardless)")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
