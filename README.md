# Home Assistant Add-on: Watermeter Reader

Liest einen Wasserzaehler mit 7-Segment-LCD (Heitland/Axioma Qalcosonic W1) aus den Bildern einer ESP32-CAM und
meldet Zaehlerstand und Status per MQTT an Home Assistant. Die Kamera-Firmware liegt im Schwesterprojekt
`esp32cam_meter` (liefert nur Bilder, `/capture_led`); die Auswertung laeuft hier auf dem Home-Assistant-Rechner.

## Stand (0.2.3)

| Baustein | Stand |
|---|---|
| Repo, Add-on-Geruest (`config.yaml`, Dockerfile, `run.sh`) | angelegt, **noch nicht in Home Assistant gebaut/getestet** |
| Bildabruf, Wiederholung bei Abbruechen | fertig (Kamera bricht ca. 5 % der Uebertragungen ab) |
| Ausrichtung an QR-Code/Datamatrix/SN-Schriftzug | fertig (Verschiebung per Template-Matching) |
| Anzeigenerkennung (`m3`/`m3h`-Symbol) | fertig, 43 von 43 Bildern richtig |
| Ziffernerkennung (9 Stellen + Durchfluss) | fertig, 21 von 21 Zaehlerbildern vollstaendig |
| Plausibilitaet (Ratsche, Rate, Bestaetigung ueber Folgemessungen) | fertig |
| Abrufplanung nach Anzeigezyklus (Phasenkopplung) und zwei Takte (Ruhe/aktiv) | fertig, im Docker geprueft |
| MQTT mit Discovery (Wasser, m3, total_increasing) | fertig, im Docker gegen Mosquitto geprueft; **noch nicht im Supervisor** |
| Weboberflaeche (Ingress): Status, Referenzbild setzen, Stand setzen | Geruest |
| Einrichtungsseite: Anker/Zahlenbereich per Maus, Anlernen | offen |

**Bekannte Grenzen:** Belegt sind durch Beispielbilder nur die Ziffern `0 1 2 5 6 9`; fuer `3 4 7 8` gilt die
Standard-Segmentzuordnung. Unbekannte Muster werden als `?` verworfen, nicht geraten. Die Zonen stammen aus einer
Aufnahmesitzung; andere Beleuchtung kann die Schwellen verschieben.

Entwicklungsbilder liegen in `dev_frames/` (nicht im Repo, enthalten die Seriennummer).

## Entwicklungswerkzeuge

```bash
python -m unittest discover -s tests                        # Plausibilitaet, Planung, Intervall
python tools/simulate_schedule.py                           # Abrufplanung (Modell, 60 min)
python tools/simulate_schedule.py --day                     # Tagesvergleich festes Intervall / zwei Takte
INTERVAL=180 FAIL=0.1 SECS=300 sh tools/e2e/run_e2e.sh      # Docker: Attrappe + Mosquitto + Add-on-Image
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

## Abrufintervall (zwei Takte)

Der Zaehler zeigt den Stand nur 10 s lang im festen 18-s-Zyklus (danach 4 s Version, 4 s Pruefsumme). Der Add-on
koppelt seine Abrufe an diese Phase (`phase_lock`), sodass jeder Abruf in der Mitte des Zaehlerstandsfensters liegt.
Das Intervall ist deshalb auf Vielfache von 18 s **gerastet**: `poll_interval_s: 20` ergibt 36 s, nicht 20 s.

| Option | Standard | Bedeutung |
|---|---|---|
| `poll_interval_s` | 180 | **Ruhe:** Mindestabstand zwischen zwei Abrufen, solange kein Wasser laeuft |
| `active_interval_s` | 36 | **aktiv:** Mindestabstand, solange Wasser laeuft oder sich der Stand kuerzlich geaendert hat |
| `active_window_s` | 120 | so lange nach der letzten Aktivitaet bleibt der aktive Takt |

Aktivitaet = Durchfluss > 0 in der zweiten Anzeigezeile oder ein uebernommener neuer Stand. Nach dem Start gilt der
aktive Takt zunaechst fuer `active_window_s`. Ein Verbrauch geht nie verloren (der Zaehlerstand ist kumulativ); nur der
Beginn eines Zapfens kann bis `poll_interval_s` spaeter bemerkt werden.

Modell (24 h, Abruf 8-15 s, Mittel ueber 20 Laeufe; `tools/simulate_schedule.py --day`):

| | Abrufe/Tag | Zapfen erkannt | Ablesungen im Lauf | Verzoegerung |
|---|---|---|---|---|
| **15 kurze Zapfen (30-180 s)** | | | | |
| fest 36 s | 1661 | 14,5 / 15 | 30 | 25 s |
| fest 180 s | 446 | 8,0 / 15 | 8 | 63 s |
| zwei Takte 180/36 | 467 | 7,8 / 15 | 14 | 56 s |
| **6 lange Verbraeuche (5-15 min)** | | | | |
| fest 36 s | 1664 | 6 / 6 | 64 | 24 s |
| fest 180 s | 447 | 6 / 6 | 17 | 99 s |
| zwei Takte 180/36 | 496 | 6 / 6 | 56 | 102 s |

Zwei Takte liefern bei langen Verbraeuchen fast die Aufloesung des festen 36-s-Takts mit knapp einem Drittel der
Abrufe. Bei kurzen Zapfen bringt der aktive Takt kaum mehr Erkennungen als ein festes 180-s-Intervall (ein kurzer
Zapfen faellt oft komplett zwischen zwei Ruhe-Abrufe). Das Gesamtvolumen ist in allen Faellen im Zaehlerstand enthalten.

## Plausibilitaet

Ein Stand wird nur uebernommen, wenn er nicht kleiner als der letzte ist, nicht schneller steigt als
`max_rate_m3_per_min` zulaesst und von `confirm_frames - 1` Folgemessungen gestuetzt wird. Uebernommen wird jeweils
die aelteste Messung des bestaetigten Blocks (Verzoegerung: ein Bild). Damit kann ein einzelner Fehlwert nie in
den Zaehlerstand gelangen, auch nicht, wenn er zur vorigen Messung passt (Ratsche bei `total_increasing`).
Nach einem Zaehlertausch den Stand ueber die Oberflaeche zuruecksetzen.

## Entitäten per YAML statt Discovery

Mit `mqtt_discovery: false` sendet der Add-on nur die Werte. Die Entitäten legst du dann in der `configuration.yaml` an
(Basis-Topic = Option `mqtt_topic`, Standard `wasserzaehler`):

```yaml
mqtt:
  sensor:
    - name: "Wasserzaehler Stand"
      unique_id: wasserzaehler_total_yaml
      state_topic: "wasserzaehler/value"
      availability_topic: "wasserzaehler/status"
      unit_of_measurement: "m³"
      device_class: water
      state_class: total_increasing
      suggested_display_precision: 3
    - name: "Wasserzaehler Ablesesicherheit"
      unique_id: wasserzaehler_confidence_yaml
      state_topic: "wasserzaehler/confidence"
      availability_topic: "wasserzaehler/status"
      unit_of_measurement: "%"
      entity_category: diagnostic
    - name: "Wasserzaehler Letzte Ablesung"
      unique_id: wasserzaehler_last_update_yaml
      state_topic: "wasserzaehler/last_update"
      availability_topic: "wasserzaehler/status"
      device_class: timestamp
      entity_category: diagnostic
    - name: "Wasserzaehler Status Auswertung"
      unique_id: wasserzaehler_state_yaml
      state_topic: "wasserzaehler/state"
      availability_topic: "wasserzaehler/status"
      entity_category: diagnostic
```

Bereits retained Discovery-Konfigurationen früherer Versionen bleiben auf dem Broker liegen und müssen dort gelöscht
werden (leere retained Nachricht auf `<Präfix>/sensor/watermeter/<name>/config`), sonst erscheinen die Entitäten doppelt.
