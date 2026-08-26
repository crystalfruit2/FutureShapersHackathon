#!/usr/bin/env python3
"""
Mock of Oleksandr's ESP32 sensor board — serves the EXACT shape the real one
serves at http://192.168.4.1/ so the --esp path can be built and rehearsed
with no hardware and no BioGuard WiFi:

    python3 dashboard/mock_board.py                 # port 8181
    python3 dashboard/app.py --esp http://127.0.0.1:8181/

Matches the real board's contract (Oleksandr, 26.08): gas + water_level are
RAW 0-4095 ADC counts (conversion is the server's job), temperature/humidity
are floats or null when the sensor isn't wired, sound_level is a raw level the
bridge auto-baselines into the hall's sound flag (board firmware, 26.08). --nulls keeps temp/hum null
like the sample response; default has them live so every mapped channel moves.
"""
import argparse, json, random
from http.server import BaseHTTPRequestHandler, HTTPServer

state = {"gas": 1548.0, "temp": 24.2, "hum": 51.0, "water": 9, "snd": 92.0}

class H(BaseHTTPRequestHandler):
    nulls = False
    pin_gas = False
    def do_GET(self):
        s = state
        if not self.pin_gas:
            s["gas"] = min(4095, max(200, s["gas"] + random.uniform(-40, 45)))
        s["temp"] += random.uniform(-0.2, 0.2)
        s["hum"] = min(95, max(20, s["hum"] + random.uniform(-0.5, 0.5)))
        s["snd"] = min(4095, max(40, s["snd"] + random.uniform(-8, 8)))
        body = json.dumps({
            "gas": int(s["gas"]),
            "temperature": None if self.nulls else round(s["temp"], 2),
            "humidity": None if self.nulls else round(s["hum"], 2),
            "water_level": s["water"],
            "sound_level": int(s["snd"]),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8181)
    ap.add_argument("--gas", type=float,
                    help="pin the raw gas count (rehearse the alarm: 2900+ crosses the 700 a.u. limit)")
    ap.add_argument("--nulls", action="store_true",
                    help="temperature/humidity stay null, like the 26.08 sample response")
    args = ap.parse_args()
    H.nulls = args.nulls
    if args.gas is not None:
        state["gas"] = args.gas
        H.pin_gas = True
    print(f"mock ESP32 board on http://127.0.0.1:{args.port}/  (nulls={args.nulls})")
    HTTPServer(("0.0.0.0", args.port), H).serve_forever()
