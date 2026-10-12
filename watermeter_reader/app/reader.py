"""Kern der Auswertung: Bild ausrichten, Anzeige erkennen, 7-Segment-Ziffern lesen.

Arbeitet auf Graustufen-JPEGs der Kamera (800x600). Alle Koordinaten stehen in `Calibration` und gelten im
Koordinatensystem des Referenzbildes; Aufnahmen werden vor dem Lesen darauf ausgerichtet.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

Box = Tuple[int, int, int, int]  # x0, y0, x1, y1

# Segmente a..g -> Ziffer. (a oben, b oben rechts, c unten rechts, d unten, e unten links, f oben links, g Mitte)
SEG_TO_DIGIT = {
    "abcdef": "0", "bc": "1", "abdeg": "2", "abcdg": "3", "bcfg": "4", "acdfg": "5",
    "acdefg": "6", "abc": "7", "abcf": "7", "abcdefg": "8", "abcdfg": "9",
}
# Segmentzonen als Anteile der (entneigten) Ziffernbox: (x0, y0, x1, y1)
ZONES = {
    # Der Mittelbalken g ist (besonders bei den kleinen Ziffern) dick und belegt ca. 0.42..0.62 der Hoehe: die
    # senkrechten Segmente werden deshalb oberhalb 0.40 bzw. unterhalb 0.62 gemessen.
    "a": (0.20, 0.00, 0.80, 0.16), "g": (0.20, 0.42, 0.80, 0.60), "d": (0.20, 0.84, 0.80, 1.00),
    "f": (0.00, 0.10, 0.32, 0.40), "b": (0.68, 0.10, 1.00, 0.40),
    "e": (0.00, 0.64, 0.32, 0.90), "c": (0.68, 0.64, 1.00, 0.90),
}


@dataclass
class Calibration:
    ref_size: Tuple[int, int] = (800, 600)
    anchors: Dict[str, Box] = field(default_factory=dict)         # Name -> Box im Referenzbild
    unit_boxes: Dict[str, Box] = field(default_factory=dict)      # Einheitensymbole (Anzeigenerkennung)
    unit_threshold: Dict[str, float] = field(default_factory=dict)
    # Ziffernfelder: Zeile -> Liste (x0, y0, x1, y1)
    cells: Dict[str, List[Box]] = field(default_factory=dict)
    decimal_after: int = 6                                        # so viele Ziffern vor dem Komma in Zeile "value"
    slant: float = 0.08                                           # Kursivneigung (px je px)
    seg_on: float = 0.35                                          # Anteil dunkler Pixel, ab dem ein Segment "an" ist
    search_pad: int = 45

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)

    @staticmethod
    def from_json(s: str) -> "Calibration":
        d = json.loads(s)
        c = Calibration()
        for k, v in d.items():
            if k in ("anchors", "unit_boxes", "cells"):
                v = {n: (tuple(b) if not isinstance(b[0], (list, tuple)) else [tuple(x) for x in b]) for n, b in v.items()}
            setattr(c, k, v)
        return c


@dataclass
class Reading:
    screen: str = "?"                 # "meter" | "other"
    text: str = ""                    # z.B. "000001.960"
    value: Optional[float] = None     # m3
    flow_text: str = ""
    flow: Optional[float] = None      # m3/h
    confidence: float = 0.0           # 0..1, minimale Ziffernsicherheit
    align_score: float = 0.0
    unit_scores: Dict[str, float] = field(default_factory=dict)
    digits: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def decode_jpeg(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("JPEG nicht lesbar")
    return img


class Reader:
    def __init__(self, cal: Calibration, ref_img: np.ndarray):
        self.cal = cal
        self.ref = ref_img
        self.tpl_anchor = {n: ref_img[b[1]:b[3], b[0]:b[2]].copy() for n, b in cal.anchors.items()}
        self.tpl_unit = {n: ref_img[b[1]:b[3], b[0]:b[2]].copy() for n, b in cal.unit_boxes.items()}

    # ---- Ausrichtung ----
    def align(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """Richtet img am Referenzbild aus (Verschiebung aus den Ankern). Gibt (Bild, schlechtester Score) zurueck."""
        pts_ref, pts_img, worst = [], [], 1.0
        for n, b in self.cal.anchors.items():
            x0, y0, x1, y1 = b
            p = self.cal.search_pad
            X0, Y0 = max(0, x0 - p), max(0, y0 - p)
            X1, Y1 = min(img.shape[1], x1 + p), min(img.shape[0], y1 + p)
            res = cv2.matchTemplate(img[Y0:Y1, X0:X1], self.tpl_anchor[n], cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(res)
            worst = min(worst, float(mx))
            if mx > 0.5:
                pts_ref.append((x0, y0))
                pts_img.append((X0 + loc[0], Y0 + loc[1]))
        if len(pts_ref) >= 2:
            d = np.array(pts_ref, np.float32) - np.array(pts_img, np.float32)
            dx, dy = float(np.median(d[:, 0])), float(np.median(d[:, 1]))
        else:
            dx = dy = 0.0
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return img, worst
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE), worst

    # ---- Anzeigenerkennung ----
    def unit_scores(self, img: np.ndarray) -> Dict[str, float]:
        out = {}
        for n, b in self.cal.unit_boxes.items():
            pad = 12
            x0, y0, x1, y1 = b
            win = img[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            res = cv2.matchTemplate(win, self.tpl_unit[n], cv2.TM_CCOEFF_NORMED)
            out[n] = float(res.max())
        return out

    # ---- Ziffern ----
    @staticmethod
    def normalize_background(img: np.ndarray) -> np.ndarray:
        """Teilt durch den (per Closing geschaetzten) Hintergrund: gleicht Randabschattung und LED-Verlauf aus.
        Ergebnis: float32, ca. 1.0 = Hintergrund, kleiner = Tinte."""
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
        bg = cv2.morphologyEx(img, cv2.MORPH_CLOSE, k)
        bg = cv2.GaussianBlur(bg, (0, 0), 6)
        return img.astype(np.float32) / (bg.astype(np.float32) + 1.0)

    def _binarize(self, norm: np.ndarray, box: Box) -> np.ndarray:
        x0, y0, x1, y1 = box
        pad = 6
        roi = norm[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
        roi8 = np.clip(roi * 160.0, 0, 255).astype(np.uint8)
        roi8 = cv2.GaussianBlur(roi8, (0, 0), 0.8)
        # Otsu je Zelle auf dem hintergrundnormierten Bild
        _, b = cv2.threshold(roi8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return b

    def _deslant(self, b: np.ndarray) -> np.ndarray:
        h = b.shape[0]
        M = np.float32([[1, self.cal.slant, -self.cal.slant * h / 2], [0, 1, 0]])
        return cv2.warpAffine(b, M, (b.shape[1], b.shape[0]), flags=cv2.INTER_NEAREST)

    def read_cell(self, norm: np.ndarray, box: Box) -> dict:
        """Liest eine Ziffer. Die Zonen beziehen sich auf die FESTE Zelle (nicht auf eine enge Box um die Tinte):
        so ist eine "1" (nur rechts, mit Faehnchen oben) klar von einer "7" (Balken ueber die ganze Breite) getrennt."""
        b = self._deslant(self._binarize(norm, box))
        pad = 6
        h0 = b.shape[0] - 2 * pad
        # Kleine Flecken (Dezimalpunkt, Staub, Rauschen) entfernen, damit sie keine Segmente vortaeuschen:
        # Komponenten, deren Breite UND Hoehe unter einem Fuenftel der Zellhoehe liegen.
        n, lab, stats, _ = cv2.connectedComponentsWithStats((b > 0).astype(np.uint8), connectivity=8)
        lim = max(4, int(0.2 * h0))
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_WIDTH] < lim and stats[i, cv2.CC_STAT_HEIGHT] < lim:
                b[lab == i] = 0
        cell = b[:, pad:b.shape[1] - pad]  # waagerecht: feste Zelle ohne Polster
        # Senkrecht: tatsaechliche Ausdehnung der Ziffer (Zeilen mit Tinte). Alle Ziffern haben volle Hoehe, daher
        # sind die Zonen so unabhaengig von einer kleinen Hoehenabweichung des Zellrahmens.
        rows = np.where((cell > 0).sum(axis=1) >= 2)[0]
        if len(rows) < 8:
            return {"ch": " ", "conf": 1.0, "segs": "", "ink": int((cell > 0).sum())}
        cell = cell[rows.min():rows.max() + 1, :]
        h, w = cell.shape
        ink = int((cell > 0).sum())
        if ink < 0.03 * h * w:
            return {"ch": " ", "conf": 1.0, "segs": "", "ink": ink}
        on, conf, fr = [], 1.0, {}
        for s, (zx0, zy0, zx1, zy1) in ZONES.items():
            zone = cell[int(zy0 * h):max(int(zy1 * h), int(zy0 * h) + 1), int(zx0 * w):max(int(zx1 * w), int(zx0 * w) + 1)]
            frac = float((zone > 0).mean()) if zone.size else 0.0
            fr[s] = round(frac, 2)
            if frac > self.cal.seg_on:
                on.append(s)
            conf = min(conf, min(abs(frac - self.cal.seg_on) / 0.35 + 0.35, 1.0))
        key = "".join(sorted(on))
        ch = SEG_TO_DIGIT.get(key, "?")
        return {"ch": ch, "conf": round(conf, 2), "segs": key, "frac": fr}

    def read_row(self, norm: np.ndarray, name: str) -> Tuple[str, List[dict]]:
        cells = self.cal.cells.get(name, [])
        out = [self.read_cell(norm, c) for c in cells]
        return "".join(d["ch"] for d in out), out

    def read(self, jpeg_or_img) -> Reading:
        img = decode_jpeg(jpeg_or_img) if isinstance(jpeg_or_img, (bytes, bytearray)) else jpeg_or_img
        r = Reading()
        img, r.align_score = self.align(img)
        r.unit_scores = self.unit_scores(img)
        ok = all(r.unit_scores.get(n, 0) >= t for n, t in self.cal.unit_threshold.items())
        r.screen = "meter" if ok else "other"
        if not ok:
            return r
        norm = self.normalize_background(img)
        txt, d1 = self.read_row(norm, "value")
        ftx, d2 = self.read_row(norm, "flow")
        r.digits = d1 + d2
        n = self.cal.decimal_after
        r.text = (txt[:n] + "." + txt[n:]) if len(txt) > n else txt
        r.flow_text = ftx
        r.confidence = min([d["conf"] for d in d1 if d["ch"] != " "] or [0.0])
        if "?" in txt or " " in txt.strip() or len(txt) != len(self.cal.cells.get("value", [])):
            r.notes.append("Ziffern unvollstaendig")
        else:
            try:
                r.value = float(r.text)
            except ValueError:
                r.notes.append("Wert nicht lesbar")
        # Durchfluss: 5 Stellen, 3 Nachkommastellen im Anzeigeformat 00.000
        if ftx and "?" not in ftx and len(ftx) >= 5:
            try:
                r.flow = float(ftx[:-3] + "." + ftx[-3:])
            except ValueError:
                pass
        return r


def default_calibration() -> Calibration:
    """Geometrie fuer Heitland/Axioma Qalcosonic W1 bei Aufnahmen 800x600 aus dem Halter (Kamera ca. 66 mm ueber
    dem Glas). Gilt, bis die Einrichtungsseite eigene Bereiche liefert; Koordinaten im Referenzbild."""
    c = Calibration()
    c.anchors = {"QR": (120, 35, 250, 155), "DM": (525, 30, 655, 145), "SN": (295, 124, 480, 153)}
    c.unit_boxes = {"m3": (585, 235, 650, 300), "m3h": (585, 335, 665, 405)}
    c.unit_threshold = {"m3": 0.83, "m3h": 0.90}
    big = [(x, 215, x + 45, 304) for x in (162, 214, 266, 318, 370, 422)]
    dec = [(476, 228, 507, 298), (509, 228, 541, 298), (546, 228, 578, 298)]
    c.cells["value"] = big + dec
    c.cells["flow"] = [(384, 312, 416, 372), (422, 312, 456, 372), (460, 312, 492, 372), (498, 312, 530, 372),
                       (536, 312, 568, 372)]
    c.decimal_after = 6
    return c
