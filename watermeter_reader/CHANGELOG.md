# Aenderungen

## 0.2.0
- Kern: Ausrichtung, Anzeigenerkennung, 7-Segment-Ziffernlesen (9 Stellen + Durchfluss).
- Plausibilitaet ueber Folgemessungen, Ratenbegrenzung, Ratschenschutz.
- MQTT mit Home-Assistant-Discovery, Weboberflaeche (Status, Referenzbild, Stand setzen).
- Werkzeuge: tools/evaluate.py, tools/replay.py; Tests fuer die Plausibilitaet.
- Momentan-Durchfluss der Anzeige ist eine Diagnose-Entitaet und in Home Assistant standardmaessig deaktiviert
  (wird meist verpasst); Rate besser per Ableitungshelfer aus dem Zaehlerstand.

## 0.1.0
- Geruest: Bildabruf im Intervall, Add-on-Konfiguration.
