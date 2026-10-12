# Home Assistant Add-on: Watermeter Reader

Liest einen Wasserzaehler mit 7-Segment-LCD (Heitland/Axioma Qalcosonic W1) aus den Bildern einer ESP32-CAM und
meldet Zaehlerstand und Status per MQTT an Home Assistant. Die Kamera-Firmware liegt im Schwesterprojekt
`esp32cam_meter` (liefert nur Bilder, `/capture_led`); die Auswertung laeuft hier auf dem Home-Assistant-Rechner.

## Stand

| Baustein | Stand |
|---|---|
| Repo, Add-on-Geruest (`config.yaml`, Dockerfile, `run.sh`) | angelegt, noch nicht in Home Assistant getestet |
| Bildabruf mit Wiederholung | Geruest |
| Ausrichtung an QR-Code/Datamatrix/SN-Schriftzug | offen |
| Anzeigenerkennung (`m3`-Symbol) | offen |
| Ziffernerkennung (9 Stellen) | offen |
| Plausibilitaet, Bestaetigung ueber mehrere Bilder | offen |
| MQTT (Discovery: Wasser, m3, total_increasing) | offen |
| Einrichtungsseite (Ingress): Anker, Zahlenbereich, Anlernen | offen |

Entwicklungsbilder liegen in `dev_frames/` (nicht im Repo, enthalten die Seriennummer).

## Installation (sobald lauffaehig)

1. Home Assistant -> Einstellungen -> Add-ons -> Add-on-Store -> Menue (drei Punkte) -> Repositories.
2. `https://github.com/ThomasKeller/HomeAssistant-Watermeter-Reader` hinzufuegen.
3. „Watermeter Reader" installieren, Optionen setzen (`camera_url`, MQTT), starten.

Add-ons lassen sich nicht ueber HACS verteilen; dafuer ist das Repository im Add-on-Store einzutragen.
