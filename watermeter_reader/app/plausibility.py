"""Plausibilitaetspruefung fuer Zaehlerstaende.

Ein Zaehlerstand (m3) wird nur uebernommen, wenn
  1. er nicht kleiner ist als der zuletzt uebernommene Stand (ein Wasserzaehler laeuft nur vorwaerts),
  2. er seit dem letzten uebernommenen Stand nicht schneller gestiegen ist als `max_rate_m3_per_min` zulaesst und
  3. ihn `confirm_frames - 1` Folgemessungen stuetzen: jeweils nicht kleiner als die vorige Messung und im
     Ratenrahmen darueber. (Nicht "gleich": bei fliessendem Wasser aendert sich die letzte Stelle in jedem Bild.)

Der Zaehlerstand wirkt wie eine Ratsche (total_increasing): ein einmal uebernommener zu hoher Wert wuerde alle
richtigen Werte danach blockieren. Deshalb die Bestaetigung ueber mehrere Messungen und die harte Obergrenze der Rate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

TOL = 0.0005  # m3: unter dieser Aufloesung (0,5 l) gelten Werte als gleich


@dataclass
class Decision:
    accepted: bool = False          # Wert wurde uebernommen (neu oder unveraendert bestaetigt)
    changed: bool = False           # uebernommener Stand hat sich geaendert (oder erstmals gesetzt)
    value: Optional[float] = None   # aktuell gueltiger Stand
    reason: str = ""                # Begruendung bei Ablehnung / Hinweis
    chain: int = 0                  # Laenge der zueinander passenden Messungen


@dataclass
class Tracker:
    max_rate_per_min: float = 0.1
    confirm_frames: int = 2
    value: Optional[float] = None   # zuletzt uebernommener Stand
    ts: Optional[float] = None      # Zeitpunkt (s) dieses Standes
    _win: list = field(default_factory=list)   # letzte zueinander passende Messungen [(wert, ts), ...]
    stats: Dict[str, int] = field(default_factory=lambda: {
        "gelesen": 0, "uebernommen": 0, "kleiner": 0, "zu_schnell": 0, "unbestaetigt": 0, "ohne_wert": 0})
    stuck: int = 0                  # aufeinanderfolgende Ablehnungen durch die harten Regeln, trotz passender Kette

    # ---- Zustand sichern/laden (JSON-faehig) ----
    def dump(self) -> dict:
        return {"value": self.value, "ts": self.ts}

    def load(self, d: dict) -> None:
        self.value = d.get("value")
        self.ts = d.get("ts")

    def reset(self, value: Optional[float] = None, ts: Optional[float] = None) -> None:
        """Manuelles Setzen (z.B. nach Zaehlertausch). None = beim naechsten bestaetigten Wert neu beginnen."""
        self.value, self.ts = value, ts
        self._win = []
        self.stuck = 0

    # ---- Hauptlogik ----
    def update(self, value: Optional[float], ts: float) -> Decision:
        """Gibt eine Entscheidung zu `value` (m3) zum Zeitpunkt `ts` (s) zurueck.

        Ein Stand wird erst uebernommen, wenn ihn `confirm_frames - 1` FOLGEMESSUNGEN stuetzen (nicht kleiner als er
        selbst, im Ratenrahmen darueber). Uebernommen wird dabei die AELTESTE Messung des Blocks, also mit der
        Verzoegerung von `confirm_frames - 1` Bildern. So kann ein einzelner Fehlwert nie uebernommen werden, auch
        wenn er zur vorigen Messung passt."""
        if value is None:
            self.stats["ohne_wert"] += 1
            return Decision(False, False, self.value, "kein gueltiger Wert", len(self._win))
        self.stats["gelesen"] += 1

        # Block fortsetzen, wenn die Messung zur letzten im Block passt, sonst neu beginnen
        if self._win:
            lv, lts = self._win[-1]
            dt = max((ts - lts) / 60.0, 0.05)
            if not ((lv - TOL) <= value <= (lv + self.max_rate_per_min * dt + TOL)):
                self._win = []
        self._win.append((value, ts))
        if len(self._win) > self.confirm_frames:
            self._win = self._win[-self.confirm_frames:]
        if len(self._win) < self.confirm_frames:
            self.stats["unbestaetigt"] += 1
            return Decision(False, False, self.value, "noch nicht bestaetigt", len(self._win))

        cv, cts = self._win[0]  # Kandidat: aelteste Messung des bestaetigten Blocks

        # Harte Regeln gegenueber dem uebernommenen Stand
        if self.value is not None and self.ts is not None:
            if cv < self.value - TOL:
                self.stats["kleiner"] += 1
                self.stuck += 1
                return Decision(False, False, self.value, f"kleiner als der letzte Stand ({self.value:.3f})",
                                len(self._win))
            dt_acc = max((cts - self.ts) / 60.0, 0.05)
            if cv - self.value > self.max_rate_per_min * dt_acc + TOL:
                self.stats["zu_schnell"] += 1
                self.stuck += 1
                return Decision(False, False, self.value,
                                f"Anstieg um {cv - self.value:.3f} m3 in {dt_acc:.1f} min zu gross", len(self._win))

        changed = self.value is None or abs(cv - self.value) > TOL
        self.value, self.ts = cv, cts
        self.stuck = 0
        if changed:
            self.stats["uebernommen"] += 1
        return Decision(True, changed, cv, "", len(self._win))
