# Home Assistant Add-on: Watermeter Reader

Liest einen Wasserzaehler mit 7-Segment-LCD (Heitland/Axioma Qalcosonic W1) aus den Bildern einer ESP32-CAM und
meldet Zaehlerstand und Status per MQTT an Home Assistant. Die Kamera-Firmware liegt im Schwesterprojekt
`esp32cam_meter` (liefert nur Bilder, `/capture_led`); die Auswertung laeuft hier auf dem Home-Assistant-Rechner.

## Stand (0.2.0)

| Baustein | Stand |
|---|---|
| Repo, Add-on-Geruest (`config.yaml`, Dockerfile, `run.sh`) | angelegt, **noch nicht in Home Assistant gebaut/getestet** |
| Bildabruf, Wiederholung bei Abbruechen | fertig (Kamera bricht ca. 5 % der Uebertragungen ab) |
| Ausrichtung an QR-Code/Datamatrix/SN-Schriftzug | fertig (Verschiebung per Template-Matching) |
| Anzeigenerkennung (`m3`/`m3h`-Symbol) | fertig, 43 von 43 Bildern richtig |
| Ziffernerkennung (9 Stellen + Durchfluss) | fertig, 21 von 21 Zaehlerbildern vollstaendig |
| Plausibilitaet (Ratsche, Rate, Bestaetigung ueber Folgemessungen) | fertig, 10 Tests |
| MQTT mit Discovery (Wasser, m3, total_increasing) | fertig, **noch nicht gegen einen echten Broker getestet** |
| Weboberflaeche (Ingress): Status, Referenzbild setzen, Stand setzen | Geruest |
| Einrichtungsseite: Anker/Zahlenbereich per Maus, Anlernen | offen |

**Bekannte Grenzen:** Belegt sind durch Beispielbilder nur die Ziffern `0 1 2 5 6 9`; fuer `3 4 7 8` gilt die
Standard-Segmentzuordnung. Unbekannte Muster werden als `?` verworfen, nicht geraten. Die Zonen stammen aus einer
Aufnahmesitzung; andere Beleuchtung kann die Schwellen verschieben.

Entwicklungsbilder liegen in `dev_frames/` (nicht im Repo, enthalten die Seriennummer).

## Entwicklungswerkzeuge

```bash
python -m unittest discover -s tests                        # Plausibilitaet
python tools/evaluate.py --frames dev_frames/set1 --ref f012 --debug dev_frames/debug   # Ziffernlesen je Bild
python tools/replay.py   --frames dev_frames/set1 --ref f012                            # kompletter Dienst, ohne Broker
```

## Installation (sobald lauffaehig)

1. Home Assistant -> Einstellungen -> Add-ons -> Add-on-Store -> Menue (drei Punkte) -> Repositories.
2. `https://github.com/ThomasKeller/HomeAssistant-Watermeter-Reader` hinzufuegen.
3. „Watermeter Reader" installieren, Optionen setzen (`camera_url`, MQTT), starten.
4. In der Oberflaeche (Seitenleiste „Wasserzaehler") bei sichtbarer Zaehlerstandsanzeige
   „Aktuelles Bild als Referenz speichern" waehlen.

Add-ons lassen sich nicht ueber HACS verteilen; dafuer ist das Repository im Add-on-Store einzutragen.

## MQTT

Basis-Topic aus der Option `mqtt_topic` (Standard `wasserzaehler`). Zugang aus den Optionen, sonst vom
MQTT-Dienst des Supervisors. Veroeffentlicht wird retained:

| Topic | Inhalt |
|---|---|
| `<base>/value` | Zaehlerstand in m3 (3 Nachkommastellen) |
| `<base>/flow` | Momentan-Durchfluss der Anzeige in m3/h (bei Aenderung; Diagnose, in HA standardmaessig deaktiviert) |
| `<base>/confidence` | Sicherheit der letzten Ablesung in % |
| `<base>/last_update` | Zeitstempel der letzten Aenderung |
| `<base>/state` | `ok`, `wartet auf Bestaetigung`, `andere Anzeige`, `unplausibel: ...`, `Kamera nicht erreichbar`, `nicht kalibriert` |
| `<base>/status` | `online`/`offline` (Verfuegbarkeit) |

## Durchfluss

Die zweite Anzeigezeile (`m3/h`) ist ein **Momentanwert**: Sie zeigt etwas nur, solange gerade Wasser fliesst. Die
Anzeige wechselt alle 18 s (Zaehlerstand nur 10 s lang), der Abruf erfolgt alle 20 s. Ein kurzes Zapfen von 5 s wird
dadurch nur mit etwa 14 % Wahrscheinlichkeit gesehen. Die Entitaet „Momentan-Durchfluss (Anzeige)" ist deshalb eine
**Diagnose-Entitaet und in Home Assistant standardmaessig deaktiviert**; sie taugt als Hinweis „Wasser fliesst gerade",
nicht als Messreihe.

Eine zuverlaessige Durchflussrate ergibt sich aus dem **Zaehlerstand** (der kumulativ ist, kein Zapfen geht verloren):

1. Einstellungen -> Geraete & Dienste -> Helfer -> Helfer hinzufuegen -> **Ableitung** (Derivative).
2. Eingangssensor: „Wasserzaehler Stand". Genauigkeit 3, Zeitfenster **5 Minuten**, Zeiteinheit **Stunden**.
3. Das Ergebnis ist die mittlere Rate in m3/h; fuer eine Leckwarnung (Dauerverbrauch nachts) eignet sich diese Ableitung,
   nicht der Momentanwert.

Die Aufloesung ist durch die kleinste Stelle (1 l) begrenzt: bei einem Fenster von 5 min entspricht 1 l etwa
0,012 m3/h.

## Plausibilitaet

Ein Stand wird nur uebernommen, wenn er nicht kleiner als der letzte ist, nicht schneller steigt als
`max_rate_m3_per_min` zulaesst und von `confirm_frames - 1` Folgemessungen gestuetzt wird. Uebernommen wird jeweils
die aelteste Messung des bestaetigten Blocks (Verzoegerung: ein Bild). Damit kann ein einzelner Fehlwert nie in
den Zaehlerstand gelangen, auch nicht, wenn er zur vorigen Messung passt (Ratsche bei `total_increasing`).
Nach einem Zaehlertausch den Stand ueber die Oberflaeche zuruecksetzen.
