"""Tests der Plausibilitaetspruefung (python -m unittest discover -s tests)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))
from plausibility import Tracker  # noqa: E402


def run(t, readings, step=20.0, t0=1000.0):
    out = []
    for i, v in enumerate(readings):
        out.append(t.update(v, t0 + i * step))
    return out


class TrackerTest(unittest.TestCase):
    def test_erster_wert_braucht_bestaetigung(self):
        t = Tracker(0.1, 2)
        d = run(t, [1.960, 1.960])
        self.assertFalse(d[0].accepted)
        self.assertTrue(d[1].accepted and d[1].changed)
        self.assertEqual(t.value, 1.960)

    def test_gleicher_wert_wird_nicht_als_aenderung_gemeldet(self):
        t = Tracker(0.1, 2)
        d = run(t, [1.960, 1.960, 1.960, 1.960])
        self.assertTrue(d[2].accepted and not d[2].changed)

    def test_fliessendes_wasser_wird_uebernommen(self):
        """Letzte Stelle aendert sich in jedem Bild: darf nicht an der Bestaetigung scheitern."""
        t = Tracker(0.1, 2)
        d = run(t, [1.960, 1.961, 1.963, 1.964, 1.966])
        self.assertTrue(all(x.accepted for x in d[1:]))
        self.assertEqual(t.value, 1.964)  # eine Messung Verzoegerung: der letzte Wert wartet auf seine Folgemessung

    def test_einzelner_ausreisser_wird_verworfen(self):
        t = Tracker(0.1, 2)
        run(t, [1.960, 1.960])
        d = run(t, [7.960], t0=1100.0)
        self.assertFalse(d[0].accepted)
        self.assertEqual(t.value, 1.960)

    def test_kleinerer_wert_wird_verworfen(self):
        t = Tracker(0.1, 2)
        run(t, [1.960, 1.960])
        d = run(t, [1.950, 1.950], t0=1100.0)
        self.assertFalse(d[0].accepted or d[1].accepted)
        self.assertEqual(t.value, 1.960)

    def test_ratsche_kein_haengenbleiben_nach_einzelnem_hohen_fehler(self):
        """Ein hoher Fehlwert im Ratenrahmen (1.969) darf nie uebernommen werden: Die Folgemessung (1.961) stuetzt ihn
        nicht, die Kette beginnt neu. Danach kommt der richtige Stand 1.961 durch (kein Haengenbleiben)."""
        t = Tracker(0.1, 2)
        run(t, [1.960, 1.960])
        seen = []
        for i, v in enumerate([1.969, 1.961, 1.961, 1.962]):
            t.update(v, 1100.0 + 20.0 * i)
            seen.append(t.value)
        self.assertNotIn(1.969, seen)
        self.assertLess(t.value, 1.969)
        self.assertGreaterEqual(t.value, 1.961)

    def test_zu_schneller_anstieg(self):
        t = Tracker(0.1, 2)
        run(t, [1.960, 1.960])                    # bei 1000 s und 1020 s
        # 0,5 m3 in 20 s = 1,5 m3/min >> 0,1
        d = run(t, [2.460, 2.460], t0=1040.0)
        self.assertFalse(any(x.accepted for x in d))
        self.assertEqual(t.value, 1.960)

    def test_nach_langer_pause_darf_stand_hoeher_sein(self):
        t = Tracker(0.1, 2)
        run(t, [1.960, 1.960])
        d = run(t, [2.400, 2.400], t0=1000.0 + 3600.0)  # eine Stunde spaeter
        self.assertTrue(d[1].accepted)
        self.assertEqual(t.value, 2.400)

    def test_ohne_wert_aendert_nichts(self):
        t = Tracker(0.1, 2)
        run(t, [1.960, 1.960])
        d = t.update(None, 2000.0)
        self.assertFalse(d.accepted)
        self.assertEqual(t.value, 1.960)

    def test_zustand_laden_und_zuruecksetzen(self):
        t = Tracker(0.1, 2)
        t.load({"value": 5.000, "ts": 1000.0})
        self.assertEqual(t.value, 5.000)
        t.reset(None)
        d = run(t, [1.0, 1.0])
        self.assertTrue(d[1].accepted)
        self.assertEqual(t.value, 1.0)


if __name__ == "__main__":
    unittest.main()
