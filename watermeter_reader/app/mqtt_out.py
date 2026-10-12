"""MQTT-Ausgabe mit Home-Assistant-Discovery.

Topics (Basis `base`, Standard "wasserzaehler"):
  <base>/status        online/offline (LWT, retained)
  <base>/value         Zaehlerstand in m3, 3 Nachkommastellen (retained)
  <base>/flow          Durchfluss in m3/h (retained)
  <base>/confidence    Sicherheit der letzten Ablesung 0..100 (retained)
  <base>/last_update   Zeitstempel der letzten uebernommenen Ablesung, ISO 8601 (retained)
  <base>/state         Text: "ok", "keine Anzeige", "unplausibel: ..." (retained)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Optional

log = logging.getLogger("watermeter.mqtt")


def supervisor_mqtt() -> Optional[dict]:
    """MQTT-Zugang vom Supervisor (Add-on-Dienst `mqtt:want`). None, wenn nicht verfuegbar."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    try:
        req = urllib.request.Request("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
        d = json.loads(urllib.request.urlopen(req, timeout=5).read()).get("data") or {}
        if d.get("host"):
            return {"host": d["host"], "port": int(d.get("port", 1883)),
                    "user": d.get("username", ""), "password": d.get("password", "")}
    except Exception as e:
        log.warning("MQTT-Dienst des Supervisors nicht abrufbar: %s", e)
    return None


class Publisher:
    def __init__(self, host: str, port: int, user: str, password: str, base: str, device_id: str = "watermeter",
                 discovery_prefix: str = "homeassistant", discovery: bool = True):
        import paho.mqtt.client as mqtt
        self.base = base.strip("/")
        # Praefix muss zu "Discovery-Praefix" der MQTT-Integration in Home Assistant passen (Standard: homeassistant)
        self.prefix = (discovery_prefix or "homeassistant").strip("/")
        self.discovery = discovery  # False: nur Werte senden, Entitaeten legt der Nutzer per YAML an
        self.device_id = device_id
        try:  # paho >= 2
            self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{device_id}_reader")
        except AttributeError:
            self.c = mqtt.Client(client_id=f"{device_id}_reader")
        if user:
            self.c.username_pw_set(user, password or None)
        self.c.will_set(f"{self.base}/status", "offline", retain=True)
        self.c.on_connect = self._on_connect
        self.c.reconnect_delay_set(2, 60)
        self.c.connect_async(host, port, keepalive=60)
        self.c.loop_start()
        self.connected = False
        self._cache: dict = {}

    def _on_connect(self, client, userdata, *a):
        self.connected = True
        client.publish(f"{self.base}/status", "online", retain=True)
        if self.discovery:
            self._discovery()
        for t, v in self._cache.items():  # nach Wiederverbindung zuletzt bekannte Werte erneut senden
            client.publish(t, v, retain=True)
        log.info("MQTT verbunden")

    def _discovery(self) -> None:
        dev = {"identifiers": [self.device_id], "name": "Wasserzaehler", "manufacturer": "Heitland",
               "model": "Qalcosonic W1 (Kamera-Auswertung)"}
        avail = {"availability_topic": f"{self.base}/status"}
        ents = {
            "sensor/total": {"name": "Wasserzaehler Stand", "state_topic": f"{self.base}/value",
                             "unit_of_measurement": "m³", "device_class": "water", "state_class": "total_increasing",
                             "suggested_display_precision": 3, "icon": "mdi:water"},
            # Momentanwert der zweiten Anzeigezeile: steht nur, solange Wasser fliesst, und wird bei Abruf alle 20 s
            # und Wechsel der Anzeige meist verpasst. Deshalb Diagnose-Entitaet, standardmaessig deaktiviert.
            # Eine zuverlaessige Rate bildet man aus dem Zaehlerstand (Helfer "Ableitung", siehe README).
            "sensor/flow": {"name": "Momentan-Durchfluss (Anzeige)", "state_topic": f"{self.base}/flow",
                            "unit_of_measurement": "m³/h", "device_class": "volume_flow_rate",
                            "state_class": "measurement", "suggested_display_precision": 3,
                            "entity_category": "diagnostic", "enabled_by_default": False},
            "sensor/confidence": {"name": "Ablesesicherheit", "state_topic": f"{self.base}/confidence",
                                  "unit_of_measurement": "%", "state_class": "measurement",
                                  "entity_category": "diagnostic"},
            "sensor/last_update": {"name": "Letzte Ablesung", "state_topic": f"{self.base}/last_update",
                                   "device_class": "timestamp", "entity_category": "diagnostic"},
            "sensor/state": {"name": "Status Auswertung", "state_topic": f"{self.base}/state",
                             "entity_category": "diagnostic"},
        }
        for key, cfg in ents.items():
            comp, name = key.split("/")
            cfg = dict(cfg, unique_id=f"{self.device_id}_{name}", device=dev, **avail)
            self.c.publish(f"{self.prefix}/{comp}/{self.device_id}/{name}/config", json.dumps(cfg), retain=True)

    def publish(self, sub: str, payload) -> None:
        topic = f"{self.base}/{sub}"
        self._cache[topic] = str(payload)
        if self.connected:
            self.c.publish(topic, str(payload), retain=True)

    def close(self) -> None:
        try:
            self.c.publish(f"{self.base}/status", "offline", retain=True)
            self.c.loop_stop()
            self.c.disconnect()
        except Exception:
            pass
