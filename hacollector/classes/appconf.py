from __future__ import annotations

import os
import json
import logging
import pathlib
from configparser import ConfigParser

import config as cfg
from classes.utils import Color


class MainConfig:
    def __init__(self) -> None:
        self.aircon_server: str             = ''
        self.aircon_port: str               = '0'
        self.aircon_devicename: str         = ''
        self.mqtt_anonymous: str            = 'False'
        self.mqtt_server: str               = ''
        self.mqtt_port: str                 = '1883'
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
        logger = logging.getLogger("MainConfig")
        try:
            # first, check RS485 Device
            rs485_devices = config[cfg.CONF_RS485_DEVICES] if cfg.CONF_RS485_DEVICES in config else None
            
            if rs485_devices is not None and len(rs485_devices) >= 1:
                aircon_section = None
                for top_device in rs485_devices:
                    if top_device == cfg.CONF_AIRCON_DEVICE_NAME.lower():
                        aircon_section = rs485_devices[top_device]
                
                if aircon_section is not None:
                    aircon_info = config[aircon_section]
                    self.aircon_server      = aircon_info.get('server', '')
                    self.aircon_port        = aircon_info.get('port', '0')
                    self.aircon_devicename  = aircon_info.get('device', '')
            
            # mqtt
            mqtt_section = config[cfg.CONF_MQTT] if cfg.CONF_MQTT in config else None
            if mqtt_section is not None:
                self.mqtt_anonymous = mqtt_section.get('anonymous', 'False')
                self.mqtt_server    = mqtt_section.get('server', '')
                self.mqtt_port      = mqtt_section.get('port', '1883')
                self.mqtt_id        = mqtt_section.get('username', '')
                self.mqtt_pw        = mqtt_section.get('password', '')
        except Exception as e:
            logger.critical(f"Error in reading config file.[{e}]")
            return False
        return True

    def validate(self) -> bool:
        logger = logging.getLogger("MainConfig")
        if not self.mqtt_server:
            logger.error("MQTT Server is not configured! Check MQTT_SERVER_IP env or config file.")
            return False
        if not self.aircon_server:
            logger.error("Aircon Server is not configured! Check LGAIRCON_SERVER_IP env or config file.")
            return False
        return True

    def load_env_values(self):
        """Load configuration from Environment Variables."""
        mqtt_server         = os.getenv('MQTT_SERVER_IP')
        mqtt_port           = os.getenv('MQTT_SERVER_PORT')
        mqtt_user           = os.getenv('MQTT_USER')      # 추가된 필드
        mqtt_pass           = os.getenv('MQTT_PASS')      # 추가된 필드
        lgac_server         = os.getenv('LGAIRCON_SERVER_IP')
        lgac_port           = os.getenv('LGAIRCON_SERVER_PORT')
        log_level           = os.getenv('CONF_LOGLEVEL')
        temperature_adjust  = os.getenv('TEMPERATURE_ADJUST')

        logger = logging.getLogger("MainConfig")
        
        # MQTT 매핑
        if mqtt_server:
            self.mqtt_server = mqtt_server
        if mqtt_port:
            self.mqtt_port = mqtt_port
        if mqtt_user:
            self.mqtt_id = mqtt_user
        if mqtt_pass:
            self.mqtt_pw = mqtt_pass
            
        # 에어컨 매핑
        if lgac_server:
            self.aircon_server = lgac_server
        if lgac_port:
            self.aircon_port = lgac_port
            
        if log_level:
            self.log_level = log_level
        if temperature_adjust:
            cfg.TEMPERATURE_ADJUST = float(temperature_adjust)
            
        # 온도 설정
        env_min_temp = os.getenv('MIN_TEMP')
        if env_min_temp:
            try: self.min_temp = int(env_min_temp)
            except ValueError: pass
        env_max_temp = os.getenv('MAX_TEMP')
        if env_max_temp:
            try: self.max_temp = int(env_max_temp)
            except ValueError: pass

        # 방 설정 (ROOMS_AIRCONS=livingroom:bedroom:computer_room 형식)
        aircons = os.getenv('ROOMS_AIRCONS')
        if aircons:
            try:
                # JSON 형식 시도
                data = json.loads(aircons)
                if isinstance(data, dict):
                    self.rooms = data
                elif isinstance(data, list):
                    self.rooms = {f'{num:02x}': name for num, name in enumerate(data)}
            except json.JSONDecodeError:
                # 콜론(:) 구분 형식 시도 (Fallback)
                aircon_list = aircons.split(':')
                self.rooms = {f'{num:02x}': name for num, name in enumerate(aircon_list)}
        
        if self.rooms:
            cfg.SYSTEM_ROOM_AIRCON = self.rooms

        # HA options.json 로드 시도
        self.load_options_json()
        
    def load_options_json(self):
        options_path = '/data/options.json'
        if not os.path.exists(options_path):
            return

        try:
            with open(options_path, 'r') as f:
                options = json.load(f)
            
            logger = logging.getLogger("MainConfig")
            logger.info(f"Loading configuration from {options_path}...")
            
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
            if 'log_level' in options: self.log_level = options['log_level']
            
            if 'rooms' in options:
                new_rooms = {}
                for item in options['rooms']:
                    if 'name' in item and 'id' in item:
                        new_rooms[f"{int(item['id']):02x}"] = item['name']
                if new_rooms:
                    self.rooms = new_rooms
                    cfg.SYSTEM_ROOM_AIRCON = new_rooms
            
            logger.info("Configuration loaded from options.json successfully.")
        except Exception as e:
            logging.getLogger("MainConfig").warning(f"Failed to load options.json: {e}")
