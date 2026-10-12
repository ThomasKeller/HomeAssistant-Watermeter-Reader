#!/usr/bin/env python3
"""Entwicklungswerkzeug: Kalibrierung aus dem Referenzbild bauen und die Auswertung gegen die Entwicklungsbilder pruefen.

  python tools/evaluate.py --frames dev_frames/set1 --ref f012 [--save-cal cal.json] [--debug out_dir]
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))
import cv2  # noqa: E402
from reader import Calibration, Reader, default_calibration  # noqa: E402


def build_calibration() -> Calibration:
    return default_calibration()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="dev_frames/set1")
    ap.add_argument("--ref", default="f012")
    ap.add_argument("--save-cal", default="")
    ap.add_argument("--debug", default="", help="Ordner fuer Debugbilder (Zellen eingezeichnet)")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.frames, "f*.jpg")))
    ref_path = [f for f in files if os.path.basename(f).startswith(a.ref)][0]
    ref = cv2.imread(ref_path, cv2.IMREAD_GRAYSCALE)
    cal = build_calibration()
    if a.save_cal:
        open(a.save_cal, "w", encoding="utf-8").write(cal.to_json())
    rd = Reader(cal, ref)
    if a.debug:
        os.makedirs(a.debug, exist_ok=True)
    n_meter = n_ok = 0
    prev = None
    print("Bild   Anzeige  Zaehlerstand  Konf.  Durchfluss  Ausrichtung  Einheiten (m3 / m3h)  Hinweise")
    for f in files:
        r = rd.read(cv2.imread(f, cv2.IMREAD_GRAYSCALE))
        name = os.path.basename(f)[:4]
        if r.screen == "meter":
            n_meter += 1
            n_ok += 1 if r.value is not None else 0
        us = " / ".join(f"{v:.2f}" for v in r.unit_scores.values())
        print(f"{name}  {r.screen:7s}  {r.text:12s}  {r.confidence:4.2f}   {r.flow_text:8s}    {r.align_score:.2f}        {us:12s}  {'; '.join(r.notes)}")
        if a.debug and r.screen == "meter":
            img = cv2.cvtColor(cv2.imread(f, cv2.IMREAD_GRAYSCALE), cv2.COLOR_GRAY2BGR)
            for row in cal.cells.values():
                for (x0, y0, x1, y1) in row:
                    cv2.rectangle(img, (x0, y0), (x1, y1), (0, 200, 255), 1)
            for d, (x0, y0, x1, y1) in zip(r.digits, cal.cells["value"] + cal.cells["flow"]):
                cv2.putText(img, d["ch"], (x0 + 4, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imwrite(os.path.join(a.debug, name + ".png"), img)
    print(f"\nZaehlerbilder erkannt: {n_meter}, davon mit vollstaendigem Wert: {n_ok}")


if __name__ == "__main__":
    main()
