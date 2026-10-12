#!/usr/bin/env python3
"""Spielt aufgezeichnete Kamerabilder durch den kompletten Dienst (ohne Kamera und ohne MQTT-Broker).

  python tools/replay.py --frames dev_frames/set1 --ref f012
Zeigt je Bild die Entscheidung und alle MQTT-Nachrichten, die veroeffentlicht wuerden.
"""
import argparse
import datetime
import glob
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))
from service import Service  # noqa: E402


class FakePub:
    def __init__(self):
        self.log = []

    def publish(self, sub, payload):
        self.log.append((sub, str(payload)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="dev_frames/set1")
    ap.add_argument("--ref", default="f012")
    ap.add_argument("--rate", type=float, default=0.1)
    ap.add_argument("--confirm", type=int, default=2)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.frames, "f*.jpg")))
    ref = [f for f in files if os.path.basename(f).startswith(a.ref)][0]
    times = {}
    logf = os.path.join(a.frames, "_capture_log.json")
    if os.path.exists(logf):
        for fr in json.load(open(logf))["frames"]:
            times[fr["file"]] = datetime.datetime.fromisoformat(fr["t"]).timestamp()
    work = tempfile.mkdtemp(prefix="wm_replay_")
    pub = FakePub()
    clock = {"t": 0.0}
    cur = {"jpg": b""}
    svc = Service({"camera_url": "x", "max_rate_m3_per_min": a.rate, "confirm_frames": a.confirm,
                   "save_debug_frames": 0}, work, fetch=lambda: cur["jpg"], pub=pub, now=lambda: clock["t"])
    shutil.copy(ref, os.path.join(work, "reference.jpg"))
    svc.reader = svc._load_reader()
    t0 = None
    for f in files:
        name = os.path.basename(f)
        ts = times.get(name)
        if ts is None:
            ts = (t0 or 0) + 15.0 * len(pub.log)
        t0 = t0 or ts
        clock["t"] = ts
        cur["jpg"] = open(f, "rb").read()
        n0 = len(pub.log)
        st = svc.step()
        new = pub.log[n0:]
        pubs = [f"{s}={v}" for s, v in new if s in ("value", "flow")]
        print(f"{name[:4]}  {st['state']:28s} gelesen {st['text']:12s} Stand {st['value']}  {' '.join(pubs)}")
    print("\nZaehler:", svc.counters)
    print("Bewertung:", svc.tracker.stats)
    topics = {}
    for s, v in pub.log:
        topics.setdefault(s, []).append(v)
    for s, v in topics.items():
        print(f"  {s}: {len(v)} Nachrichten, letzte = {v[-1]}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
