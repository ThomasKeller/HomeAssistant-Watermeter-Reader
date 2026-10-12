"""Kleine Weboberflaeche (Home-Assistant-Ingress, Port 8099), nur Standardbibliothek.

  GET  /              Statusseite
  GET  /api/status    JSON
  GET  /api/frame     letztes Kamerabild (JPEG)
  POST /api/calibrate aktuelles Kamerabild als Referenz speichern (Zaehlerstandsanzeige muss sichtbar sein)
  POST /api/reset     ?value=1.234 setzt den Zaehlerstand (z.B. nach Zaehlertausch); ohne value: neu beginnen
Links sind relativ, weil Ingress den Pfad vorangestellt bekommt.
"""
from __future__ import annotations

import html
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

log = logging.getLogger("watermeter.web")


def make_handler(service):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):  # ruhig
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            p = urlparse(self.path).path.rstrip("/") or "/"
            if p.endswith("/api/status"):
                return self._json(self._full_status())
            if p.endswith("/api/frame"):
                if service.last_frame:
                    return self._send(200, service.last_frame, "image/jpeg")
                return self._send(404, b"kein Bild", "text/plain")
            return self._send(200, self._page().encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            u = urlparse(self.path)
            p = u.path.rstrip("/")
            q = parse_qs(u.query)
            try:
                if p.endswith("/api/calibrate"):
                    return self._json(service.calibrate())
                if p.endswith("/api/reset"):
                    v = float(q["value"][0]) if q.get("value") else None
                    service.reset_value(v)
                    return self._json({"ok": True, "value": v})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)
            return self._json({"ok": False, "error": "unbekannt"}, 404)

        def _full_status(self) -> dict:
            s = dict(service.status)
            s["counters"] = service.counters
            s["stats"] = service.tracker.stats
            s["stuck"] = service.tracker.stuck
            return s

        def _page(self) -> str:
            s = self._full_status()
            rows = "".join(f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
                           for k, v in [("Status", s["state"]), ("Zaehlerstand (uebernommen)", s["value"]),
                                        ("zuletzt gelesen", s["text"]), ("Durchfluss m3/h", s["flow"]),
                                        ("Sicherheit %", s["confidence"]), ("Hinweis", s["reason"]),
                                        ("kalibriert", s["calibrated"]), ("letzte Aenderung", s["last_update"]),
                                        ("Abrufdauer s", s["fetch_s"]), ("Zaehler", s["counters"]),
                                        ("Bewertung", s["stats"]), ("Steckengeblieben", s["stuck"])])
            return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                    "<title>Wasserzaehler</title><body style='font-family:sans-serif;margin:16px;max-width:720px'>"
                    "<h3>Wasserz&auml;hler</h3><table border=0 cellpadding=4>" + rows + "</table>"
                    "<p><img src='api/frame' style='max-width:100%'></p>"
                    "<p><button onclick=\"fetch('api/calibrate',{method:'POST'}).then(r=>r.json())"
                    ".then(j=>{alert(JSON.stringify(j));location.reload()})\">Aktuelles Bild als Referenz speichern"
                    "</button></p><p><small>Die Zaehlerstandsanzeige muss dabei sichtbar sein.</small></p>")

    return H


def start(service, port: int = 8099) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("0.0.0.0", port), make_handler(service))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log.info("Weboberflaeche auf Port %d", port)
    return srv
