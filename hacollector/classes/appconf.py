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
        self.min_temp: int                  = 18
        self.max_temp: int                  = 30
        self.scan_interval: float           = cfg.WALLPAD_SCAN_INTERVAL_TIME
        self.rs485_timeout: float           = 2.0
        self.persistent_connection: bool    = True
        self.full_scan_on_boot: bool        = False
        self.rooms: dict[str, str]          = {}

    def read_config_file(self, config: ConfigParser) -> bool:
        color_log = ColorLog()
        try:
            # first, check RS485 Device
            rs485_devices = config[cfg.CONF_RS485_DEVICES] if cfg.CONF_RS485_DEVICES in config else None
            
            if rs485_devices is not None and len(rs485_devices) >= 1:
                aircon_section = None
                for top_device in rs485_devices:
                    color_log.log(f"device section = {top_device}", Color.Cyan, ColorLog.Level.DEBUG)
                    if top_device == cfg.CONF_AIRCON_DEVICE_NAME.lower():
                        aircon_section = rs485_devices[top_device]
                color_log.log(f"aircon section is {aircon_section}", Color.Blue, ColorLog.Level.DEBUG)
                if aircon_section is None:
                    # Legacy config missing is fine if we have options.json
                    color_log.log("Legacy aircon section not found (using options.json?)", Color.Yellow, ColorLog.Level.INFO)
                    
                # aircon section
                if aircon_section is not None:
                    aircon_info = config[aircon_section]
                    self.aircon_server      = aircon_info['server']
                    self.aircon_port        = aircon_info['port']
                    self.aircon_devicename  = aircon_info['device']
            
            # mqtt
            mqtt_section = config[cfg.CONF_MQTT] if cfg.CONF_MQTT in config else None
            if mqtt_section is None:
                 color_log.log("Legacy MQTT section not found (using options.json?)", Color.Yellow, ColorLog.Level.INFO)
            else:
                self.mqtt_anonymous = mqtt_section.get('anonymous', 'False')
                self.mqtt_server    = mqtt_section.get('server', '')
                self.mqtt_port      = mqtt_section.get('port', '1883')
                self.mqtt_id        = mqtt_section.get('username', '')
                self.mqtt_pw        = mqtt_section.get('password', '')
        except Exception as e:
            color_log.log(f"Error in reading config file.[{e}]", Color.Red, ColorLog.Level.CRITICAL)
            return False
        return True

    def validate(self) -> bool:
        color_log = ColorLog()
        if not self.mqtt_server:
            color_log.log("MQTT Server is not configured!", Color.Red)
            return False
        if not self.aircon_server:
            color_log.log("Aircon Server is not configured!", Color.Red)
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
            
        env_min_temp = os.getenv('MIN_TEMP')
        if env_min_temp:
            try:
                self.min_temp = int(env_min_temp)
            except ValueError:
                pass
                
        env_max_temp = os.getenv('MAX_TEMP')
        if env_max_temp:
            try:
                self.max_temp = int(env_max_temp)
            except ValueError:
                pass

        aircons         = os.getenv('ROOMS_AIRCONS')


        if aircons:
            try:
                # Try parsing as JSON (new format)
                # Expected JSON format: {"00": "livingroom", "01": "bedroom"}
                import json
                data = json.loads(aircons)
                if isinstance(data, dict):
                    self.rooms = data
                    # cfg.SYSTEM_ROOM_AIRCON = data # Legacy Global (Deprecated)
                elif isinstance(data, list):
                    new_dict = {}
                    for item in data:
                        if isinstance(item, dict) and 'name' in item and 'id' in item:
                            name = item['name']
                            uid = int(item['id'])
                            new_dict[f'{uid:02x}'] = name
                    if new_dict:
                        self.rooms = new_dict
                        # cfg.SYSTEM_ROOM_AIRCON = new_dict # Legacy Global (Deprecated)
                    else:
                        # Fallback for list of strings (simple json list)
                        if len(data) > 0 and isinstance(data[0], str):
                             self.rooms = {f'{num:02x}': name for num, name in enumerate(data)}
                             # cfg.SYSTEM_ROOM_AIRCON = self.rooms # Legacy Global
            except json.JSONDecodeError:
                # Fallback to old format (list of names separated by :)
                # This ensures backward compatibility if run.sh isn't updated simultaneously or for legacy envs
                aircon_list: list[str] = aircons.split(':')
                aircon_dict = {f'{num:02x}': name for num, name in enumerate(aircon_list)}
                self.rooms = aircon_dict
                # cfg.SYSTEM_ROOM_AIRCON = aircon_dict
        
        # Populate global for backward compatibility (if needed) but prefer object passing
        if self.rooms:
            cfg.SYSTEM_ROOM_AIRCON = self.rooms

        # Attempt to load from options.json (Direct HA Addon Support)
        self.load_options_json()
        
    def load_options_json(self):
        options_path = '/data/options.json'
        # For local testing, check if options.json exists in root or predictable path
        # In HA, it's always /data/options.json
        if not os.path.exists(options_path):
            return

        color_log = ColorLog()
        try:
            import json
            with open(options_path, 'r') as f:
                options = json.load(f)
            
            color_log.log(f"Loading configuration from {options_path}...", Color.Cyan)
            
            if 'lg_server_ip' in options: self.aircon_server = options['lg_server_ip']
            if 'lg_server_port' in options: self.aircon_port = str(options['lg_server_port'])
            if 'mqtt_server' in options: self.mqtt_server = options['mqtt_server']
            if 'mqtt_port' in options: self.mqtt_port = str(options['mqtt_port'])
            if 'mqtt_username' in options: self.mqtt_id = options['mqtt_username']
            if 'mqtt_password' in options: self.mqtt_pw = options['mqtt_password']
            if 'min_temp' in options: self.min_temp = int(options['min_temp'])
            if 'max_temp' in options: self.max_temp = int(options['max_temp'])
            if 'scan_interval' in options: self.scan_interval = float(options['scan_interval'])
            if 'rs485_timeout' in options: self.rs485_timeout = float(options['rs485_timeout'])
            if 'persistent_connection' in options: self.persistent_connection = bool(options['persistent_connection'])
            if 'full_scan_on_boot' in options: self.full_scan_on_boot = bool(options['full_scan_on_boot'])
            if 'log_level' in options: self.log_level = options['log_level']
            
            if 'rooms' in options:
                # HA Addon config "rooms" is a list of dicts: [{"name": "...", "id": ...}]
                rooms_data = options['rooms']
                new_rooms = {}
                for item in rooms_data:
                    if 'name' in item and 'id' in item:
                        new_rooms[f"{int(item['id']):02x}"] = item['name']
                if new_rooms:
                    self.rooms = new_rooms
                    cfg.SYSTEM_ROOM_AIRCON = new_rooms # Global sync
            
            color_log.log("Configuration loaded from options.json successfully.", Color.Green)

        except Exception as e:
            color_log.log(f"Failed to load options.json: {e}", Color.Yellow)
