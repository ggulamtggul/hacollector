from __future__ import annotations

import os
from configparser import ConfigParser

import config as cfg
from classes.utils import Color, ColorLog


class MainConfig:
    def __init__(self) -> None:
        self.aircon_server: str             = ''
        self.aircon_port: str               = '0'
        self.aircon_devicename: str         = ''
        self.mqtt_anonymous: str            = ''
        self.mqtt_server: str               = ''
        self.mqtt_port: str                 = ''
        self.mqtt_id: str                   = ''
        self.mqtt_pw: str                   = ''
        self.log_level: str                 = cfg.CONF_LOGLEVEL

    def read_config_file(self, config: ConfigParser) -> bool:
        color_log = ColorLog()
        try:
            # first, check RS485 Device
            rs485_devices = config[cfg.CONF_RS485_DEVICES]
            if rs485_devices is not None and len(rs485_devices) >= 1:
                aircon_section = None
                for top_device in rs485_devices:
                    color_log.log(f"device section = {top_device}", Color.Cyan, ColorLog.Level.DEBUG)
                    if top_device == cfg.CONF_AIRCON_DEVICE_NAME.lower():
                        aircon_section = rs485_devices[top_device]
                color_log.log(f"aircon section is {aircon_section}", Color.Blue, ColorLog.Level.DEBUG)
                if aircon_section is None:
                    color_log.log("aircon section must be exist.", Color.Red, ColorLog.Level.CRITICAL)
                    return False
                
                # aircon section
                if aircon_section is not None:
                    aircon_info = config[aircon_section]
                    self.aircon_server      = aircon_info['server']
                    self.aircon_port        = aircon_info['port']
                    self.aircon_devicename  = aircon_info['device']
                # mqtt
                mqtt_section = config[cfg.CONF_MQTT]
                if mqtt_section is None:
                    color_log.log("This application need MQTT config.", Color.Red, ColorLog.Level.CRITICAL)
                    return False
                for item in mqtt_section:
                    self.mqtt_anonymous = mqtt_section['anonymous']
                    self.mqtt_server    = mqtt_section['server']
                    self.mqtt_port      = mqtt_section['port']
                    self.mqtt_id        = mqtt_section['username']
                    self.mqtt_pw        = mqtt_section['password']
        except Exception as e:
            color_log.log(f"Error in reading config file.[{e}]", Color.Red, ColorLog.Level.CRITICAL)
            return False
        return True

    def load_env_values(self):
        mqtt_server         = os.getenv('MQTT_SERVER_IP')
        mqtt_port           = os.getenv('MQTT_SERVER_PORT')
        lgac_server         = os.getenv('LGAIRCON_SERVER_IP')
        lgac_port           = os.getenv('LGAIRCON_SERVER_PORT')
        log_level           = os.getenv('CONF_LOGLEVEL')
        log_partial_debug   = os.getenv('PARTIAL_DEBUG')
        temperature_adjust  = os.getenv('TEMPERATURE_ADJUST')

        color_log = ColorLog()
        color_log.log(f"Environment variables Loaded, "
                      f"mqtt_server={mqtt_server}, "
                      f"mqtt_port={mqtt_port}, "
                      f"lgac_server={lgac_server}, "
                      f"lgac_port={lgac_port}, "
                      f"log_level={log_level}"
                      f"temperature_adjust={temperature_adjust}",
                      Color.Cyan,
                      ColorLog.Level.DEBUG)

        if mqtt_server:
            self.mqtt_server = mqtt_server
        if mqtt_port:
            self.mqtt_port = mqtt_port
        if lgac_server:
            self.aircon_server = lgac_server
        if lgac_port:
            self.aircon_port = lgac_port
        if log_level:
            self.log_level = log_level

        if temperature_adjust:
            cfg.TEMPERATURE_ADJUST = temperature_adjust

        if log_partial_debug and log_partial_debug != 'false':
            color_log.set_partial_debug()

        aircons         = os.getenv('ROOMS_AIRCONS')

        if aircons:
            aircon_list: list[str] = aircons.split(':')
            aircon_dict = {f'{num:02x}': name for num, name in enumerate(aircon_list)}
            cfg.SYSTEM_ROOM_AIRCON = aircon_dict
