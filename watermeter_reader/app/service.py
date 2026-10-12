"""Dienstschleife: Bild holen -> auswerten -> Plausibilitaet -> MQTT. Die Logik steckt in `Service.step()` und ist
ohne Kamera und ohne Broker testbar (Funktionen fetch/pub/now werden eingesetzt)."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Callable, Optional

import cv2

from plausibility import Tracker
from schedule import PhaseLock, plan_wait
from reader import Reader, Reading, default_calibration, Calibration, decode_jpeg

log = logging.getLogger("watermeter")


class Service:
    def __init__(self, opt: dict, data_dir: str, fetch: Optional[Callable[[], bytes]] = None, pub=None,
                 now: Callable[[], float] = time.time):
        self.opt, self.dir, self.pub, self.now = opt, data_dir, pub, now
        os.makedirs(data_dir, exist_ok=True)
        self.fetch = fetch or self._fetch_camera
        self.tracker = Tracker(float(opt.get("max_rate_m3_per_min", 0.1)), int(opt.get("confirm_frames", 2)))
        self._load_state()
        self.reader: Optional[Reader] = self._load_reader()
        self.last_frame: Optional[bytes] = None
        self.last_publish = 0.0
        self.last_flow: Optional[float] = None
        self.lock = PhaseLock()
        self.last_kind = "ok"       # fetch_error | other | unreadable | ok (steuert die Wartezeit)
        self.t_req = 0.0
        self.last_activity = self.now()   # Start gilt als aktiv: schnell kalibrieren und anlaufen
        self.counters = {"abrufe": 0, "abruf_fehler": 0, "andere_anzeige": 0, "zaehlerstand_bilder": 0}
        self.status = {"state": "gestartet", "text": "", "value": self.tracker.value, "flow": None,
                       "confidence": None, "reason": "", "calibrated": self.reader is not None,
                       "last_update": None, "fetch_s": None}

    # ---- Kamera ----
    def _fetch_camera(self) -> bytes:
        url = self.opt["camera_url"].rstrip("/") + self.opt.get("capture_path", "/capture_led")
        data = urllib.request.urlopen(url, timeout=60).read()
        if len(data) < 3000 or data[:2] != b"\xff\xd8":
            raise ValueError(f"kein JPEG ({len(data)} Byte)")
        return data

    # ---- Zustand / Kalibrierung ----
    def _p(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def _load_state(self) -> None:
        try:
            self.tracker.load(json.load(open(self._p("state.json"), encoding="utf-8")))
        except (OSError, ValueError):
            pass

    def _save_state(self) -> None:
        tmp = self._p("state.json.tmp")
        json.dump(self.tracker.dump(), open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, self._p("state.json"))

    def _load_reader(self) -> Optional[Reader]:
        ref = cv2.imread(self._p("reference.jpg"), cv2.IMREAD_GRAYSCALE)
        if ref is None:
            return None
        try:
            cal = Calibration.from_json(open(self._p("calibration.json"), encoding="utf-8").read())
        except (OSError, ValueError):
            cal = default_calibration()
        return Reader(cal, ref)

    def calibrate(self, jpeg: Optional[bytes] = None) -> dict:
        """Aktuelles Kamerabild als Referenz speichern (Zaehlerstandsanzeige muss sichtbar sein)."""
        jpeg = jpeg or self.fetch()
        open(self._p("reference.jpg"), "wb").write(jpeg)
        if not os.path.exists(self._p("calibration.json")):
            open(self._p("calibration.json"), "w", encoding="utf-8").write(default_calibration().to_json())
        self.reader = self._load_reader()
        self.status["calibrated"] = self.reader is not None
        if self.reader:  # Pruefung: erkennt der Kern in diesem Bild die Zaehlerstandsanzeige?
            r = self.reader.read(jpeg)
            return {"ok": r.screen == "meter", "screen": r.screen, "text": r.text, "unit_scores": r.unit_scores}
        return {"ok": False}

    def reset_value(self, value: Optional[float]) -> None:
        self.tracker.reset(value, self.now() if value is not None else None)
        self._save_state()

    # ---- Ausgabe ----
    def _publish_state(self, text: str) -> None:
        self.status["state"] = text
        if self.pub:
            self.pub.publish("state", text)

    def _debug_frame(self, jpeg: bytes, tag: str) -> None:
        n = int(self.opt.get("save_debug_frames", 0))
        if n <= 0:
            return
        d = self._p("debug")
        os.makedirs(d, exist_ok=True)
        name = time.strftime("%Y%m%d_%H%M%S", time.localtime(self.now())) + f"_{tag}.jpg"
        open(os.path.join(d, name), "wb").write(jpeg)
        files = sorted(os.listdir(d))
        for old in files[:-n]:
            try:
                os.remove(os.path.join(d, old))
            except OSError:
                pass

    # ---- Abrufintervall: zwei Takte ----
    def current_interval(self, now: Optional[float] = None) -> float:
        """Ruhe: `poll_interval_s` (selten). Aktiv: `active_interval_s`, solange in den letzten `active_window_s`
        Sekunden Wasser gelaufen ist (Durchfluss > 0 oder sich aendernder Stand). Ein Verbrauch geht nie verloren (der
        Zaehlerstand ist kumulativ); nur der Beginn faellt ins Ruhefenster."""
        now = self.now() if now is None else now
        idle = float(self.opt.get("poll_interval_s", 180))
        active = float(self.opt.get("active_interval_s", 36))
        window = float(self.opt.get("active_window_s", 120))
        if now - self.last_activity < window:
            return min(active, idle)
        return idle

    # ---- ein Durchlauf ----
    def step(self) -> dict:
        t0 = self.now()
        self.t_req = t0
        self.counters["abrufe"] += 1
        try:
            jpeg = self.fetch()
        except Exception as e:
            self.last_kind = "fetch_error"
            self.counters["abruf_fehler"] += 1
            self.status["reason"] = f"Kamera: {e}"
            self._publish_state("Kamera nicht erreichbar")
            return self.status
        self.status["fetch_s"] = round(self.now() - t0, 1)
        self.last_frame = jpeg
        if self.reader is None:
            self._publish_state("nicht kalibriert")
            return self.status
        try:
            r: Reading = self.reader.read(jpeg)
        except Exception as e:
            self.status["reason"] = f"Auswertung: {e}"
            self._publish_state("Auswertung fehlgeschlagen")
            return self.status
        # Aufnahmezeitpunkt ~ Abrufbeginn + LED-Vorlauf: fuer die Phase des Anzeigezyklus
        self.lock.observe(t0 + float(self.opt.get("capture_offset_s", 0.4)), r.screen == "meter")
        est = self.lock.estimate()
        self.status["phase"] = {"phase_s": round(est[0], 2), "uebereinstimmung": round(est[1], 2)} if est else None
        if r.screen != "meter":
            self.last_kind = "other"
            self.counters["andere_anzeige"] += 1
            self.status["reason"] = ""
            self._publish_state("andere Anzeige")
            return self.status
        self.counters["zaehlerstand_bilder"] += 1
        self.last_kind = "ok" if r.value is not None else "unreadable"
        d = self.tracker.update(r.value, t0)
        self.status.update({"text": r.text, "flow": r.flow, "confidence": round(r.confidence * 100),
                            "reason": d.reason or "; ".join(r.notes)})
        # Durchfluss ist eigenstaendig (aendert sich unabhaengig vom Zaehlerstand): bei Aenderung sofort senden.
        # Plausibel: 0 .. 10 m3/h (Q3 des Zaehlers: 4 m3/h).
        if r.flow is not None and 0.0 <= r.flow <= 10.0:
            self.status["flow"] = r.flow
            if self.pub and r.flow != self.last_flow:
                self.pub.publish("flow", f"{r.flow:.3f}")
            self.last_flow = r.flow
            if r.flow > 0.0:
                self.last_activity = t0
        if d.accepted:
            if d.changed:
                self.last_activity = t0
            self.status["value"] = d.value
            self.status["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0))
            heartbeat = (t0 - self.last_publish) > 300
            if self.pub and (d.changed or heartbeat):
                self.pub.publish("value", f"{d.value:.3f}")
                self.pub.publish("confidence", round(r.confidence * 100))
                self.pub.publish("last_update", self.status["last_update"])
                self.last_publish = t0
            if d.changed:
                self._save_state()
            self._publish_state("ok")
        else:
            if d.reason == "noch nicht bestaetigt":
                self._publish_state("wartet auf Bestaetigung")
            else:
                self._publish_state("unplausibel: " + (d.reason or "unbestaetigt"))
                self._debug_frame(jpeg, "abgelehnt")
        return self.status

    def run_forever(self) -> None:
        while True:
            t = time.time()
            try:
                self.step()
            except Exception:
                log.exception("Durchlauf fehlgeschlagen")
                self.last_kind = "fetch_error"
            now = time.time()
            interval = self.current_interval(now)
            self.status["interval_s"] = interval
            self.status["aktiv"] = interval < float(self.opt.get("poll_interval_s", 180))
            if self.opt.get("phase_lock", True):
                wait = plan_wait(self.last_kind, now, self.t_req or t, interval, self.lock,
                                 float(self.opt.get("capture_offset_s", 0.4)), float(self.opt.get("retry_s", 4.0)))
            else:
                wait = interval - (now - t)
            time.sleep(max(0.5, wait))
