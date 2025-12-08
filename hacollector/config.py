# Default socker buffer size
MAX_SOCKET_BUFFER   = 2048

# Default Log Level
CONF_LOGLEVEL       = 'info'          # debug, info, warn

# HA MQTT Discovery
HA_PREFIX           = 'homeassistant'
HA_CLIMATE          = 'climate'
HA_CALLBACK_MAIN    = 'rs485'
HA_CALLBACK_BRIDGE  = 'bridge'


CONF_FILE               = 'hacollector.conf'
CONF_LOGFILE            = 'hacollector.log'
CONF_LOGNAME            = 'hacollector'
CONF_AIRCON_DEVICE_NAME = 'LGAircon'
CONF_RS485_DEVICES      = 'RS485Devices'
CONF_MQTT               = 'MQTT'
CONF_ADVANCED           = 'advanced'

INIT_TEMP = 22

SYSTEM_ROOM_AIRCON = {
    '00': 'livingroom',
    '01': 'anbang',
    '02': 'computer',
}

WALLPAD_SCAN_INTERVAL_TIME  = 20.
PACKET_RESEND_INTERVAL_SEC  = 0.8

RS485_WRITE_INTERVAL_SEC    = 0.1

DEFAULT_SPEED               = 'low'

ALTERNATIVE_HEADER_DEBUG    = False
TEMPERATURE_ADJUST          = 0.5
