#!/bin/sh
# End-to-End-Test des Add-ons im Docker: Kamera-Attrappe + Mosquitto + Add-on-Image
set -u
# Aufruf (z.B. im WSL): INTERVAL=25 FAIL=0.12 SECS=200 sh tools/e2e/run_e2e.sh
# Benoetigt Docker, die Entwicklungsbilder in dev_frames/set1 und das Image: docker build -t wm-test:0.2.1 watermeter_reader
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
FR=$ROOT/dev_frames/set1
E2E=$ROOT/tools/e2e
WORK=/tmp/wm_e2e
cleanup() { docker rm -f wm-cam wm-mosq wm-addon >/dev/null 2>&1; docker network rm wmnet >/dev/null 2>&1; }
cleanup
rm -rf $WORK && mkdir -p $WORK/data
cat > $WORK/mosq.conf <<EOF
listener 1883
allow_anonymous true
EOF
cat > $WORK/data/options.json <<EOF
{"camera_url":"http://wm-cam:8080","capture_path":"/capture_led","poll_interval_s":${INTERVAL:-18},
 "mqtt_host":"wm-mosq","mqtt_port":1883,"mqtt_user":"","mqtt_password":"","mqtt_topic":"wasserzaehler/reader",
 "max_rate_m3_per_min":0.1,"confirm_frames":2,"save_debug_frames":5,"phase_lock":true,"capture_offset_s":0.4,"retry_s":4}
EOF
cp $FR/f012_*.jpg $WORK/data/reference.jpg
docker network create wmnet >/dev/null
docker run -d --name wm-mosq --network wmnet -v $WORK/mosq.conf:/mosquitto/config/mosquitto.conf eclipse-mosquitto:2 >/dev/null 2>&1 \
  || { echo "MOSQUITTO-START FEHLGESCHLAGEN"; docker logs wm-mosq 2>&1 | tail -5; }
docker run -d --name wm-cam --network wmnet -v $FR:/frames:ro -v $E2E/fakecam.py:/fakecam.py:ro -e FAIL=${FAIL:-0} python:3.12-slim python -u /fakecam.py >/dev/null
sleep 3
docker run -d --name wm-addon --network wmnet -v $WORK/data:/data wm-test:0.2.1 >/dev/null
echo "gestartet (Intervall ${INTERVAL:-18} s, Ausfall ${FAIL:-0}), sammle ${SECS:-110} s ..."
( docker exec wm-mosq mosquitto_sub -h localhost -t 'wasserzaehler/#' -t 'homeassistant/#' -v -W ${SECS:-110} > $WORK/mqtt.txt 2>&1 ) &
sleep $((${SECS:-110}+2))
echo "=== Add-on-Protokoll ==="; docker logs wm-addon 2>&1 | head -30
echo "=== Kamera-Attrappe: Abrufe (erste 14) ==="; docker logs wm-cam 2>&1 | head -${HEADN:-14}
echo "=== Kamera-Attrappe: Anzahl Abrufe nach Anzeige ==="; docker logs wm-cam 2>&1 | grep -o 'Abruf [0-9]*: [A-Za-z0-9]*' | awk '{print $3}' | sort | uniq -c
echo "=== MQTT: Themen und letzte Werte ==="
grep -v '^homeassistant' $WORK/mqtt.txt | awk '{print $1}' | sort | uniq -c
echo "--- value-Verlauf ---"; grep 'wasserzaehler/reader/value ' $WORK/mqtt.txt
echo "--- flow ---"; grep 'wasserzaehler/reader/flow ' $WORK/mqtt.txt | head -5
echo "--- state (Folge) ---"; grep 'wasserzaehler/reader/state ' $WORK/mqtt.txt | awk '{$1="";print}' | uniq -c | head -12
echo "--- Discovery ---"; grep '^homeassistant' $WORK/mqtt.txt | awk '{print $1}'
echo "--- status ---"; grep 'wasserzaehler/reader/status' $WORK/mqtt.txt | head -3
echo "=== API-Status des Add-ons ==="
docker exec wm-addon python3 -c "import json,urllib.request;d=json.loads(urllib.request.urlopen('http://127.0.0.1:8099/api/status').read());print(json.dumps({k:d[k] for k in ('state','text','value','confidence','calibrated','phase','counters','stats')},indent=1,ensure_ascii=False))"
cleanup
