from __future__ import annotations

from dataclasses import dataclass
from consts import DEVICE_AIRCON, DeviceType


class Aircon:
    @dataclass
    class ScanInfo:
        tick: float = 0.

        def reset(self) -> None:
            self.tick = 0.

    @dataclass
    class Info:
        action: str
        opmode: str
        fanmove: str
        fanmode: str
        cur_temp: float
        target_temp: int

    def __init__(self, room_name: str = '') -> None:
        self.scan = Aircon.ScanInfo()
        self.device: DeviceType = DeviceType.AIRCON
        self.name: str          = DEVICE_AIRCON
        self.room_name: str     = room_name
        self.action: str        = ''
        self.opmode: str        = ''
        self.fanmove: str       = ''
        self.fanmode: str       = ''
        self.current_temp: float = 27.0
        self.target_temp: int   = 27

    def set_initial_state(self) -> None:
        self.scan.reset()
