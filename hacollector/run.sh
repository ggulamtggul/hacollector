#!/bin/bash

CONFIG_PATH=/data/options.json

echo "Starting HA Collector Add-on..."

echo "Reading configuration..."
LG_SERVER=$(jq --raw-output '.lg_server_ip' $CONFIG_PATH)
LG_PORT=$(jq --raw-output '.lg_server_port' $CONFIG_PATH)
MQTT_SERVER=$(jq --raw-output '.mqtt_server' $CONFIG_PATH)
MQTT_PORT=$(jq --raw-output '.mqtt_port' $CONFIG_PATH)
MQTT_USER=$(jq --raw-output '.mqtt_username' $CONFIG_PATH)
MQTT_PW=$(jq --raw-output '.mqtt_password' $CONFIG_PATH)
LOG_LEVEL=$(jq --raw-output '.log_level' $CONFIG_PATH)

# Join rooms with :
# Join rooms with : and replace spaces with underscores
ROOMS=$(jq --raw-output '.rooms | map(gsub(" "; "_")) | join(":")' $CONFIG_PATH)

echo "Generating hacollector.conf..."
cat <<EOF > /hacollector/hacollector.conf
[RS485Devices]
LGAircon = LGAircon

[LGAircon]
device = LGAircon
server = $LG_SERVER
port = $LG_PORT

[MQTT]
anonymous = False
server = $MQTT_SERVER
port = $MQTT_PORT
username = $MQTT_USER
password = $MQTT_PW
EOF

export ROOMS_AIRCONS="$ROOMS"
export CONF_LOGLEVEL="$LOG_LEVEL"

echo "Running hacollector.py..."
python3 hacollector.py
