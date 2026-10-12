#!/usr/bin/with-contenv bashio
# Startskript des Add-ons. Optionen liegen in /data/options.json, persistente Daten in /data.
bashio::log.info "Watermeter Reader startet"
exec python3 -u /app/main.py
