"""Kamera-Attrappe: liefert aufgezeichnete Bilder im 18-s-Anzeigezyklus (10 s Zaehlerstand, 4 s Version, 4 s Summe)."""
import glob
import http.server
import random
import os
import time

D = "/frames"
# Nur echte Zaehlerstandsbilder (die Nummern wurden einzeln gegen den Inhalt geprueft)
def _pick(nums):
    return [glob.glob(f"{D}/f{n:03d}_*.jpg")[0] for n in nums]


OLD = _pick([4, 5, 7])                                              # 1.952

NEW = _pick([12, 13, 15, 16, 17, 20, 21, 23, 27, 29, 31, 33, 35, 37, 38, 40, 41, 43])  # 1.960
VER = glob.glob(D + "/f001_*.jpg")[0]
CRC = glob.glob(D + "/f000_*.jpg")[0]
T0 = time.time()
N = 0
FAIL = float(os.environ.get('FAIL', '0'))


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        global N
        if not self.path.startswith("/capture"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"version":"fake"}')
            return
        N += 1
        now = time.time()
        if random.random() < FAIL:
            print(f'[{now - T0:6.1f}s] Abruf {N}: FEHLER 500', flush=True)
            self.send_response(500)
            self.end_headers()
            return
        pos = (now + 0.4 - T0 - 3.0) % 18.0           # Zaehlerstandsfenster beginnt 3 s nach Start
        if pos < 10:
            f = random.choice(OLD if now - T0 < 75 else NEW)   # nach 75 s steigt der Stand von 1.952 auf 1.960
            what = "Zaehlerstand"
        elif pos < 14:
            f, what = VER, "Version"
        else:
            f, what = CRC, "Summe"
        time.sleep(random.uniform(2.0, 5.0))             # Uebertragungsdauer
        data = open(f, "rb").read()
        print(f"[{now - T0:6.1f}s] Abruf {N}: {what}", flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


http.server.ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
