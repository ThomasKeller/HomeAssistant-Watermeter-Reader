"""Tests der MQTT-Ausgabe: Discovery-Praefix (python -m unittest discover -s tests)."""
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "watermeter_reader", "app"))


class FakeClient:
    def __init__(self, *a, **k):
        self.sent = []

    def username_pw_set(self, *a): pass
    def will_set(self, *a, **k): pass
    def reconnect_delay_set(self, *a): pass
    def connect_async(self, *a, **k): pass
    def loop_start(self): pass
    def publish(self, t, p, **k): self.sent.append((t, p))


def load(prefix=None):
    fake = types.ModuleType("paho.mqtt.client")
    fake.Client = FakeClient
    fake.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
    sys.modules["paho"] = types.ModuleType("paho")
    sys.modules["paho.mqtt"] = types.ModuleType("paho.mqtt")
    sys.modules["paho.mqtt.client"] = fake
    import importlib
    import mqtt_out
    importlib.reload(mqtt_out)
    kw = {} if prefix is None else {"discovery_prefix": prefix}
    p = mqtt_out.Publisher("h", 1883, "", "", "wasserzaehler/reader", **kw)
    p._discovery()
    return p.c.sent


class DiscoveryTest(unittest.TestCase):
    def test_standardpraefix(self):
        topics = [t for t, _ in load()]
        self.assertEqual(len(topics), 5)
        self.assertTrue(all(t.startswith("homeassistant/sensor/watermeter/") and t.endswith("/config") for t in topics))

    def test_eigenes_praefix_mit_schraegstrich(self):
        topics = [t for t, _ in load("ha/measurement")]
        self.assertTrue(all(t.startswith("ha/measurement/sensor/watermeter/") for t in topics))
        self.assertFalse(any(t.startswith("homeassistant/") for t in topics))

    def test_leeres_praefix_faellt_auf_standard(self):
        self.assertTrue(all(t.startswith("homeassistant/") for t, _ in load("")))

    def test_nutzdaten_zeigen_auf_das_basis_topic(self):
        for t, p in load("ha/measurement"):
            self.assertTrue(json.loads(p)["state_topic"].startswith("wasserzaehler/reader/"))


if __name__ == "__main__":
    unittest.main()
