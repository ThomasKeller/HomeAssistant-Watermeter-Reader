# Watermeter Reader

Siehe das README im Repository (Installation, MQTT, Plausibilitaet, Abrufintervall).

## Optionen

| Option | Standard | Bedeutung |
|---|---|---|
| `camera_url` | `http://192.168.112.31` | Adresse der Kamera |
| `capture_path` | `/capture_led` | Bild mit Blitz |
| `poll_interval_s` | 180 | Abrufabstand in Ruhe (gerastet auf Vielfache von 18 s) |
| `active_interval_s` | 36 | Abrufabstand, solange Wasser laeuft |
| `active_window_s` | 120 | so lange nach der letzten Aktivitaet bleibt der aktive Takt |
| `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password` | leer | leer = MQTT-Dienst von Home Assistant |
| `mqtt_topic` | `wasserzaehler` | Basis-Topic |
| `mqtt_discovery_prefix` | `homeassistant` | Muss dem „Discovery-Präfix“ der MQTT-Integration in Home Assistant entsprechen (Einstellungen → Geräte & Dienste → MQTT → Konfigurieren). Bei abweichendem Präfix erscheinen sonst keine Entitäten. |
| `max_rate_m3_per_min` | 0,1 | groesster plausibler Anstieg |
| `confirm_frames` | 2 | Messungen zur Bestaetigung |
| `save_debug_frames` | 20 | abgelehnte Bilder behalten |
| `phase_lock` | true | Abrufe an den 18-s-Anzeigezyklus koppeln |
| `capture_offset_s` | 0.4 | Zeit zwischen Abruf und Aufnahme |
| `retry_s` | 4 | Wiederholung nach Abbruch |
