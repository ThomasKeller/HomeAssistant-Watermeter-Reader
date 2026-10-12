"""Tests der Abrufplanung (python -m unittest discover -s tests)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))
from schedule import PhaseLock, plan_wait, CYCLE, METER_LEN  # noqa: E402

PH = 3.7  # Beginn des Zaehlerstandsfensters im Modell


def in_meter(t, ph=PH):
    return ((t - ph) % CYCLE) < METER_LEN


def in_meter_from(phase, t):
    return ((t - phase) % CYCLE) < METER_LEN


def filled(n=20, seed=1, ph=PH):
    r = random.Random(seed)
    lk = PhaseLock()
    t = 1000.0
    for _ in range(n):
        t += r.uniform(5, 40)
        lk.observe(t, in_meter(t, ph))
    return lk, t


class PhaseLockTest(unittest.TestCase):
    def test_zu_wenige_beobachtungen(self):
        lk = PhaseLock()
        for t in (0.0, 5.0, 10.0):
            lk.observe(t, True)
        self.assertIsNone(lk.estimate())

    def test_nur_zaehlerstandsbeobachtungen_geben_trotzdem_eine_phase(self):
        lk = PhaseLock()
        for k in range(10):                   # alle 18 s an derselben relativen Stelle im Fenster
            lk.observe(1000.0 + 18.0 * k + 6.0, True)
        est = lk.estimate()
        self.assertIsNotNone(est)
        c = lk.next_window_center(1000.0 + 18.0 * 10 + 6.0)
        self.assertTrue(in_meter_from(est[0], c))

    def test_phase_wird_gefunden(self):
        lk, _ = filled(30)
        ph, score = lk.estimate()
        d = abs(((ph - PH + CYCLE / 2) % CYCLE) - CYCLE / 2)   # zyklische Differenz
        self.assertLess(d, 1.5)
        self.assertGreaterEqual(score, 0.99)

    def test_ziel_liegt_im_zaehlerstandsfenster(self):
        lk, t = filled(30)
        for k in range(30):
            c = lk.next_window_center(t + 7.3 * k)
            self.assertGreaterEqual(c, t + 7.3 * k)
            self.assertTrue(in_meter(c - 1.5) and in_meter(c + 1.5))   # klar im Fenster

    def test_nach_anderer_anzeige_kurz_warten(self):
        lk, t = filled(30)
        # direkt nach einem Bild mit anderer Anzeige: hoechstens ein Zyklus, nie das volle lange Intervall
        w = plan_wait("other", t, t - 10.0, 60.0, lk)
        self.assertLessEqual(w, CYCLE)
        c = t + w + 0.4
        self.assertTrue(in_meter(c))

    def test_ohne_phase_gilt_das_intervall(self):
        lk = PhaseLock()
        self.assertEqual(round(plan_wait("ok", 100.0, 90.0, 20.0, lk), 1), 10.0)

    def test_abbruch_wird_kurz_wiederholt(self):
        lk, t = filled(30)
        self.assertLessEqual(plan_wait("fetch_error", t, t - 12.0, 60.0, lk), 5.0)

    def test_unlesbare_zaehlerstandsanzeige_wird_kurz_wiederholt(self):
        lk, t = filled(30)
        self.assertLessEqual(plan_wait("unreadable", t, t - 5.0, 60.0, lk), 4.0)

    def test_widerspruechliche_beobachtungen_ergeben_keine_phase(self):
        r = random.Random(7)
        lk = PhaseLock()
        t = 0.0
        for _ in range(40):
            t += r.uniform(5, 40)
            lk.observe(t, r.random() < 0.5)       # Zufall: kein fester Zyklus
        self.assertIsNone(lk.estimate())


if __name__ == "__main__":
    unittest.main()
