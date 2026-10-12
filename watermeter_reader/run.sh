#!/bin/sh
# Startskript des Add-ons. Optionen liegen in /data/options.json, persistente Daten in /data.
echo "Watermeter Reader startet"
exec python3 -u /app/main.py
