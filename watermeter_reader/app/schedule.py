"""Abrufplanung anhand des Anzeigezyklus des Zaehlers.

Das Display des Qalcosonic W1 durchlaeuft einen festen Zyklus von 18,0 s: 10 s Zaehlerstand, 4 s Version, 4 s Pruefsumme
(an 43 Aufnahmen verifiziert). Aus den Aufnahmezeitpunkten und der Erkennung "Zaehlerstand ja/nein" laesst sich die
Phase des Zyklus schaetzen. Damit
  * landet jeder Abruf in der Mitte des 10-s-Fensters (statt in nur ca. 56 % der Faelle den Zaehlerstand zu treffen),
  * wird nach einem Bild mit anderer Anzeige genau bis zum naechsten Zaehlerstandsfenster gewartet statt das volle
    Intervall,
  * wird bei Uebertragungsfehlern kurz wiederholt, aber nicht in Dauerschleife.
Ohne belastbare Phase (zu wenige oder widerspruechliche Beobachtungen) gilt das normale Intervall.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

CYCLE = 18.0       # s
METER_LEN = 10.0   # s, so lange steht der Zaehlerstand


class PhaseLock:
    def __init__(self, maxobs: int = 40, min_obs: int = 8, min_score: float = 0.9, step: float = 0.25):
        self.obs: Deque[Tuple[float, bool]] = deque(maxlen=maxobs)
        self.min_obs, self.min_score, self.step = min_obs, min_score, step

    def observe(self, t_capture: float, is_meter: bool) -> None:
        self.obs.append((t_capture, is_meter))

    def estimate(self) -> Optional[Tuple[float, float]]:
        """(Phase, Uebereinstimmung): Phase = Zeitpunkt (mod 18 s), zu dem das Zaehlerstandsfenster beginnt.
        None, wenn zu wenige Beobachtungen oder die Uebereinstimmung zu gering ist."""
        n = len(self.obs)
        if n < self.min_obs or not any(m for _, m in self.obs) or all(m for _, m in self.obs):
            return None
        t0 = self.obs[0][0]
        k = int(CYCLE / self.step)
        score = []
        for i in range(k):
            ph = i * self.step
            ok = sum(1 for t, m in self.obs if (((t - t0 - ph) % CYCLE) < METER_LEN) == m)
            score.append(ok)
        best = max(score)
        if best / n < self.min_score:
            return None
        # Mitte des laengsten zusammenhaengenden Bereichs bester Phasen (zyklisch)
        idx = [i for i, s in enumerate(score) if s == best]
        runs, cur = [], [idx[0]]
        for a, b in zip(idx, idx[1:]):
            if b == a + 1:
                cur.append(b)
            else:
                runs.append(cur)
                cur = [b]
        runs.append(cur)
        if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == k - 1:  # Umbruch am Zyklusende
            runs[0] = runs[-1] + runs[0]
            runs.pop()
        run = max(runs, key=len)
        mid = (run[0] + (len(run) - 1) / 2.0) * self.step
        return ((t0 + mid) % CYCLE, best / n)

    def next_window_center(self, t_min: float, aim: float = METER_LEN / 2) -> Optional[float]:
        """Naechster Zeitpunkt >= t_min, der in der Mitte (aim s nach Beginn) eines Zaehlerstandsfensters liegt."""
        est = self.estimate()
        if est is None:
            return None
        ph, _ = est
        base = ph + aim
        n = int((t_min - base) // CYCLE) + 1 if t_min > base else 0
        c = base + n * CYCLE
        while c < t_min:
            c += CYCLE
        return c


def plan_wait(kind: str, now: float, t_req_last: float, interval: float, lock: PhaseLock, capture_offset: float = 0.4,
              retry_s: float = 4.0, other_floor: float = 2.0) -> float:
    """Sekunden bis zum naechsten Abruf.

    kind: 'fetch_error' | 'unreadable' (Zaehlerstandsanzeige, Ziffern nicht lesbar) | 'other' (andere Anzeige) |
          'ok' (Zaehlerstand gelesen, auch abgelehnt/unbestaetigt)."""
    if kind == "fetch_error":
        return retry_s
    if kind == "unreadable":
        return min(retry_s, 3.0)
    earliest = now + (other_floor if kind == "other" else 0.0)
    if kind != "other":
        earliest = max(earliest, t_req_last + interval)
    c = lock.next_window_center(earliest + capture_offset)
    if c is None:  # keine belastbare Phase: ohne Annahmen
        return max(1.0, (t_req_last + interval) - now) if kind != "other" else max(other_floor, min(interval, 6.0))
    return max(0.0, c - capture_offset - now)
