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


if __name__ == "__main__" and "--day" not in sys.argv:
    main()


# ---------------- Zwei-Takt-Intervall (ab 0.2.3) ----------------
def simulate_day(mode, seed, draws=15, dur=(30, 180), offset=0.4, idle=180.0, active=36.0, window=120.0,
                 fetch_range=(8, 15)):
    """24 h mit `draws` Zapfvorgaengen der Dauer `dur` (s). mode: 'fest36' | 'fest180' | 'adaptiv'.
    Liefert: Abrufe, erkannte Zapfen, mittlere Verzoegerung bis zur ersten Ablesung eines erkannten Zapfens,
    Zaehlerstandsablesungen waehrend laufendem Wasser (Aufloesung der Verbrauchskurve)."""
    rnd = random.Random(seed)
    starts = sorted(rnd.uniform(6 * 3600, 22 * 3600) for _ in range(draws))
    draw = [(a, a + rnd.uniform(*dur)) for a in starts]
    lock = PhaseLock()
    t, end, fetches, last_act, during = 0.0, 24 * 3600.0, 0, -1e9, 0
    first_seen = {}
    while t < end:
        fetches += 1
        t_req = t
        t_cap = t_req + offset
        meter = is_meter(t_cap)
        lock.observe(t_cap, meter)
        flowing = any(a <= t_cap < b for a, b in draw)
        if meter and flowing:
            last_act = t_cap
            during += 1
            for i, (a, b) in enumerate(draw):
                if a <= t_cap < b and i not in first_seen:
                    first_seen[i] = t_cap - a
        t = t_req + rnd.uniform(*fetch_range)
        if mode == "fest36":
            interval = 36.0
        elif mode == "fest180":
            interval = idle
        else:
            interval = active if (t_cap - last_act) < window else idle
        t += plan_wait("ok" if meter else "other", t, t_req, interval, lock, offset)
    seen = list(first_seen.values())
    return {"abrufe": fetches, "erkannt": len(seen),
            "verzoegerung": (sum(seen) / len(seen)) if seen else float("nan"), "waehrend": during}


def compare_day(draws, dur, seeds=20, label=""):
    print(f"\n{label}: {draws} Zapfvorgaenge je {dur[0]}-{dur[1]} s, Mittel ueber {seeds} Laeufe")
    print(f"  {'Modus':9s} {'Abrufe/Tag':>10s} {'Zapfen erkannt':>15s} {'Verzoegerung':>13s} {'Ablesungen im Lauf':>19s}")
    for mode in ("fest36", "fest180", "adaptiv"):
        r = [simulate_day(mode, sd, draws, dur) for sd in range(seeds)]
        m = lambda k: sum(x[k] for x in r if x[k] == x[k]) / max(1, len([1 for x in r if x[k] == x[k]]))
        print(f"  {mode:9s} {m('abrufe'):10.0f} {m('erkannt'):9.1f} / {draws:<3d} {m('verzoegerung'):10.0f} s {m('waehrend'):19.0f}")


if __name__ == "__main__" and "--day" in sys.argv:
    compare_day(15, (30, 180), label="kurze Zapfen (Haende waschen, Glas fuellen, WC)")
    compare_day(6, (300, 900), label="lange Verbraeuche (Duschen, Giessen, Wanne)")
