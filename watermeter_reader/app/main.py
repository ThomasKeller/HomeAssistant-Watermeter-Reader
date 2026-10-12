"""Watermeter Reader - Einstiegspunkt des Add-ons."""
import json
import logging
import os

import mqtt_out
import web
from service import Service

OPTIONS_FILE = os.environ.get("OPTIONS_FILE", "/data/options.json")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
log = logging.getLogger("watermeter")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    with open(OPTIONS_FILE, encoding="utf-8") as f:
        opt = json.load(f)

    # MQTT: eigene Zugangsdaten aus den Optionen, sonst der MQTT-Dienst des Supervisors
    host, port, user, pw = opt.get("mqtt_host", ""), int(opt.get("mqtt_port", 1883)), opt.get("mqtt_user", ""), \
        opt.get("mqtt_password", "")
    if not host:
        sv = mqtt_out.supervisor_mqtt()
        if sv:
            host, port, user, pw = sv["host"], sv["port"], sv["user"], sv["password"]
    pub = None
    if host:
        prefix = opt.get("mqtt_discovery_prefix", "homeassistant")
        pub = mqtt_out.Publisher(host, port, user, pw, opt.get("mqtt_topic", "wasserzaehler"),
                                 discovery_prefix=prefix, discovery=bool(opt.get("mqtt_discovery", True)))
        log.info("MQTT: %s:%d, Topic %s, Discovery %s (Praefix %s)", host, port, opt.get("mqtt_topic", "wasserzaehler"),
                 "an" if opt.get("mqtt_discovery", True) else "aus", prefix)
    else:
        log.warning("Kein MQTT-Broker konfiguriert: es wird nichts veroeffentlicht")

    svc = Service(opt, DATA_DIR, pub=pub)
    web.start(svc, 8099)
    log.info("Kamera %s%s, Intervall %s s, kalibriert: %s", opt["camera_url"], opt.get("capture_path", ""),
             opt.get("poll_interval_s"), svc.reader is not None)
    svc.run_forever()


if __name__ == "__main__":
    main()
