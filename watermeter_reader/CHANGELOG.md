# Aenderungen

## 0.2.3
- Zwei Takte: `poll_interval_s` (Ruhe, 180 s) und `active_interval_s` (36 s), solange Wasser laeuft oder sich der
  Stand in den letzten `active_window_s` (120 s) geaendert hat. Spart im Modell ca. 72 % der Abrufe gegenueber
  festen 36 s; bei langen Verbraeuchen bleibt fast die gleiche Aufloesung.
- Hinweis: Das Intervall rastet auf Vielfache des 18-s-Anzeigezyklus (20 s ergibt 36 s).
- Status-API zeigt `interval_s` und `aktiv`.
- Tools: Tagesvergleich in tools/simulate_schedule.py (`--day`).

## 0.2.2
- Phasenkopplung: Phase wird auch aus reinen Zaehlerstandsbeobachtungen geschaetzt (vorher blieb sie bei
  ausgerichtetem Intervall unbekannt) und greift schon ab 5 statt 8 Beobachtungen.
- Ende-zu-Ende-Test im Docker (tools/e2e): Kamera-Attrappe + Mosquitto + Add-on-Image.

## 0.2.1
- Image-Bau repariert: BUILD_FROM hat jetzt einen Standardwert (python:3.12-slim); der Supervisor uebergibt es
  ohne build.yaml nicht mehr. OpenCV/NumPy/paho kommen als pip-Wheels, run.sh braucht kein bashio mehr.

## 0.2.0
- Kern: Ausrichtung, Anzeigenerkennung, 7-Segment-Ziffernlesen (9 Stellen + Durchfluss).
- Plausibilitaet ueber Folgemessungen, Ratenbegrenzung, Ratschenschutz.
- MQTT mit Home-Assistant-Discovery, Weboberflaeche (Status, Referenzbild, Stand setzen).
- Werkzeuge: tools/evaluate.py, tools/replay.py; Tests fuer die Plausibilitaet.
- Momentan-Durchfluss der Anzeige ist eine Diagnose-Entitaet und in Home Assistant standardmaessig deaktiviert
  (wird meist verpasst); Rate besser per Ableitungshelfer aus dem Zaehlerstand.

## 0.1.0
- Geruest: Bildabruf im Intervall, Add-on-Konfiguration.
