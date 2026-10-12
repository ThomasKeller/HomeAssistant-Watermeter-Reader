"""Tests des Zwei-Takt-Intervalls (python -m unittest discover -s tests)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))
from service import Service  # noqa: E402


def make(now_ref, **opt):
    o = {"camera_url": "x", "poll_interval_s": 180, "active_interval_s": 36, "active_window_s": 120}
    o.update(opt)
    return Service(o, tempfile.mkdtemp(), fetch=lambda: b"", now=lambda: now_ref["t"])


class IntervalTest(unittest.TestCase):
    def test_start_ist_aktiv(self):
        t = {"t": 1000.0}
        s = make(t)
        self.assertEqual(s.current_interval(), 36)

    def test_ruhe_nach_dem_fenster(self):
        t = {"t": 1000.0}
        s = make(t)
        t["t"] = 1000.0 + 121
        self.assertEqual(s.current_interval(), 180)

    def test_aktivitaet_verlaengert_das_aktive_fenster(self):
        t = {"t": 1000.0}
        s = make(t)
        t["t"] = 2000.0
        self.assertEqual(s.current_interval(), 180)
        s.last_activity = 2000.0           # Wasser laeuft / Stand hat sich geaendert
        t["t"] = 2100.0
        self.assertEqual(s.current_interval(), 36)
        t["t"] = 2125.0
        self.assertEqual(s.current_interval(), 180)

    def test_ruheintervall_kleiner_als_aktiv_gilt_immer(self):
        t = {"t": 1000.0}
        s = make(t, poll_interval_s=20, active_interval_s=60)
        self.assertEqual(s.current_interval(), 20)
        t["t"] = 5000.0
        self.assertEqual(s.current_interval(), 20)


if __name__ == "__main__":
    unittest.main()
