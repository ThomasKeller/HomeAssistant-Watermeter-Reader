#!/usr/bin/env python3
"""Simuliert die Abrufplanung gegen ein Modell des Anzeigezyklus (18 s: 10 s Zaehlerstand, 4 s Version, 4 s Summe)
und vergleicht festes Intervall mit Phasenkopplung. Ohne Kamera.

  python tools/simulate_schedule.py [--minutes 60] [--interval 20] [--fetch 8,15] [--fail 0.05]
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))
from schedule import PhaseLock, plan_wait, CYCLE, METER_LEN  # noqa: E402


def is_meter(t, phase=3.7):
    return ((t - phase) % CYCLE) < METER_LEN


def run(mode, minutes, interval, fetch_range, fail_p, seed, offset=0.4):
    rnd = random.Random(seed)
    lock = PhaseLock()
    t, end = 0.0, minutes * 60.0
    req_last = -interval
    reads = []            # Zeitpunkte erfolgreicher Zaehlerstandsablesungen
    fetches = fails = others = 0
    while t < end:
        t_req = t
        fetches += 1
        dur = rnd.uniform(*fetch_range)
        t_cap = t_req + offset
        if rnd.random() < fail_p:        # Uebertragung bricht ab
            fails += 1
            t = t_req + dur
            kind = "fetch_error"
        else:
            m = is_meter(t_cap)
            lock.observe(t_cap, m)
            t = t_req + dur
            if m:
                reads.append(t_cap)
                kind = "ok"
            else:
                others += 1
                kind = "other"
        req_last = t_req
        if mode == "fest":
            t = max(t, t_req + interval)           # wie die bisherige Schleife: Intervall ab Abrufbeginn
            if kind == "fetch_error":
                t = t_req + interval
        else:
            t += plan_wait(kind, t, t_req, interval, lock, offset)
    gaps = [b - a for a, b in zip(reads, reads[1:])]
    return {"Abrufe": fetches, "Zaehlerstandsbilder": len(reads), "andere Anzeige": others, "Abbrueche": fails,
            "Trefferquote %": round(100 * len(reads) / max(1, fetches - fails), 1),
            "mittl. Abstand der Ablesungen s": round(sum(gaps) / max(1, len(gaps)), 1),
            "laengste Luecke s": round(max(gaps) if gaps else 0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--interval", type=float, default=20)
    ap.add_argument("--fetch", default="8,15", help="Abrufdauer min,max in s")
    ap.add_argument("--fail", type=float, default=0.05)
    ap.add_argument("--seeds", type=int, default=20)
    a = ap.parse_args()
    fr = tuple(float(x) for x in a.fetch.split(","))
    for mode in ("fest", "phasengekoppelt"):
        acc = {}
        for s in range(a.seeds):
            for k, v in run(mode, a.minutes, a.interval, fr, a.fail, s).items():
                acc.setdefault(k, []).append(v)
        print(f"\n{mode} (Intervall {a.interval:.0f} s, Abruf {fr[0]:.0f}-{fr[1]:.0f} s, {a.fail*100:.0f} % Abbrueche, "
              f"{a.minutes:.0f} min, {a.seeds} Laeufe):")
        for k, v in acc.items():
            print(f"  {k:34s} {sum(v)/len(v):8.1f}")


if __name__ == "__main__":
    main()
