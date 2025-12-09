from enum import Enum
from typing import NamedTuple

# string constants

# Version
SW_VERSION          = "0.9.15"  # 버전 업데이트
SW_VERSION_STRING   = f"RS485 Data Collector for Home Assistant. v{SW_VERSION} - by Bongdang"

# main service name
SERVICE_NAME        = 'hacollector' 

# DEVICE naming
DEVICE_AIRCON       = 'aircon'

# payload values
PAYLOAD_ON          = 'on'
PAYLOAD_OFF         = 'off'
PAYLOAD_ONLINE      = 'online'  # [추가]
PAYLOAD_OFFLINE     = 'offline' # [추가]
PAYLOAD_SET         = 'set'
PAYLOAD_CHECK       = 'check'
PAYLOAD_STATE       = 'state'
PAYLOAD_LOW         = 'low'
PAYLOAD_MEDIUM      = 'medium'
PAYLOAD_HIGH        = 'high'
PAYLOAD_SILENT      = 'silent'
PAYLOAD_HEAT        = 'heat'
PAYLOAD_FAN_ONLY    = 'fan_only'
PAYLOAD_COOL        = 'cool'
PAYLOAD_DRY         = 'dry'
PAYLOAD_AUTO        = 'auto'
PAYLOAD_SWING       = 'swing'
PAYLOAD_FIXED       = 'fixed'
PAYLOAD_POWER       = 'power'
PAYLOAD_STATUS      = 'status'
PAYLOAD_SCAN        = 'scan'
PAYLOAD_LOCKON      = 'lockon'
PAYLOAD_LOCKOFF     = 'lockoff'

# mqtt strings
MQTT_CONFIG         = 'config'
MQTT_MODE           = 'mode'
MQTT_SET            = 'set'
MQTT_SWING_MODE     = 'swing_mode'
MQTT_FAN_MODE       = 'fan_mode'
MQTT_PRESET_MODE    = 'preset_mode'
MQTT_CURRENT_TEMP   = 'current_temp'
MQTT_TARGET_TEMP    = 'target_temp'
MQTT_STATE          = 'state'
MQTT_STAT           = 'stat'
MQTT_TEMP           = 'temp'
MQTT_VAL            = 'val'
MQTT_PAYLOAD        = 'pl'
MQTT_CMD_T          = 'cmd_t'
MQTT_FAN_SPEED      = 'fan_speed'
MQTT_AVAILABILITY   = 'availability' # [추가]

MQTT_ICON_AIRCON    = 'mdi:air-conditioner' # 아이콘 기본값 설정

PRIORITY_LOW        = 9
PRIORITY_HIGH       = 0


class CommType(Enum):
    SOCKET = 'socket'


class CommStatus(Enum):
    WAIT_HEAD = 1
    WAIT_BODY = 2
    WAIT_TAIL = 3


class PacketType(Enum):
    SEND = 1
    ACK  = 2


class HeaderType(Enum):
    Normal      = 0xaa55
    Alter1      = 0xd555
    Undefined   = 0x0000
    Error       = 0xffff


class RS485Device(Enum):
    AIRCON  = DEVICE_AIRCON


class DeviceType(Enum):
    AIRCON      = DEVICE_AIRCON


class Command(Enum):
    CHECK   = PAYLOAD_CHECK
    STATUS  = PAYLOAD_STATUS
    ON      = PAYLOAD_ON
    OFF     = PAYLOAD_OFF
    SET     = PAYLOAD_SET


class FanSpeed(Enum):
    LOW     = PAYLOAD_LOW
    MEDIUM  = PAYLOAD_MEDIUM
    HIGH    = PAYLOAD_HIGH
    AUTO    = PAYLOAD_AUTO
    SILENT  = PAYLOAD_SILENT
    POWER   = PAYLOAD_POWER
    OFF     = PAYLOAD_OFF


class State(Enum):
    ON      = PAYLOAD_ON
    OFF     = PAYLOAD_OFF
    STATE   = PAYLOAD_STATE
    SET     = PAYLOAD_SET


class HeatMode(Enum):
    OFF         = PAYLOAD_OFF
    HEAT        = PAYLOAD_HEAT
    COOL        = PAYLOAD_COOL
    FAN_ONLY    = PAYLOAD_FAN_ONLY
