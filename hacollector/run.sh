#!/usr/bin/with-contenv bashio

bashio::log.info "Starting HA Collector..."

cd /hacollector
exec python3 /hacollector/hacollector.py
