"""Watermeter Reader - Dienst (Geruest, Version 0.1.0).

Aktueller Stand: holt in einem festen Intervall ein Bild von der Kamera und legt das letzte Bild ab.
Ausrichtung, Ziffernerkennung, Plausibilitaet und MQTT folgen (siehe ../../README.md, "Stand").
"""
import json
import logging
import os
import time
import urllib.request

OPTIONS_FILE = os.environ.get("OPTIONS_FILE", "/data/options.json")
DATA_DIR = os.environ.get("DATA_DIR", "/data")

log = logging.getLogger("watermeter")


def load_options() -> dict:
    with open(OPTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def fetch(url: str, timeout: float = 60.0) -> bytes:
    data = urllib.request.urlopen(url, timeout=timeout).read()
    if len(data) < 3000 or data[:2] != b"\xff\xd8":
        raise ValueError(f"kein JPEG ({len(data)} Byte)")
    return data


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    opt = load_options()
    url = opt["camera_url"].rstrip("/") + opt["capture_path"]
    interval = int(opt["poll_interval_s"])
    log.info("Kamera %s, Intervall %d s", url, interval)
    os.makedirs(DATA_DIR, exist_ok=True)
    while True:
        t0 = time.time()
        try:
            jpg = fetch(url)
            with open(os.path.join(DATA_DIR, "last.jpg"), "wb") as f:
                f.write(jpg)
            log.info("Bild %d Byte in %.1f s", len(jpg), time.time() - t0)
        except Exception as e:  # Netz/Kamera: weiter versuchen
            log.warning("Abruf fehlgeschlagen: %s", e)
        time.sleep(max(1.0, interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
