from __future__ import annotations

import asyncio
import time

import config as cfg
from classes.lgac485 import LGACPacketHandler
from classes.mqtt import MqttHandler
from classes.utils import Color, ColorLog


class Hub:
    def __init__(self, aircon_handler=None, mqtt_handler=None) -> None:
        self.mqtt_handler: MqttHandler | None         = mqtt_handler
        self.aircon_handler: LGACPacketHandler | None = aircon_handler
        self.devices: list                            = []

    def add_devices(self, enabled: list):
        self.devices.extend(enabled)

    async def async_scan_thread(self) -> None:
        color_log = ColorLog()
        while True:
            # MQTT Discovery 트리거
            if self.mqtt_handler and self.mqtt_handler.start_discovery:
                try:
                    self.mqtt_handler.homeassistant_device_discovery(initial=True)
                except Exception as e:
                    color_log.log(f"[Discovery]Error [{e}]", Color.Red, ColorLog.Level.DEBUG)

            # Kocom check removed, always scan aircon
            try:
                if self.aircon_handler:
                    self.aircon_handler.loop = asyncio.get_running_loop()
            except Exception as e:
                color_log.log(f"scan loop is not set. err:{e}", Color.Yellow, ColorLog.Level.WARN)
            try:
                now = time.monotonic()
                if self.aircon_handler:
                    await self.aircon_handler.async_scan_aircons(now)
            except Exception as e:
                color_log.log(f"[reScan]Error [{e}]", Color.Red, ColorLog.Level.DEBUG)

            await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC * 2)
