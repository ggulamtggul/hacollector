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
        pipe1_temp: float = 0.0
        pipe2_temp: float = 0.0
        outdoor_temp: float = 0.0
        plasma: str = 'off'
        error_code: int = 0
        load_estimate: float = 0.0

    def __init__(self, room_name: str = '') -> None:
        self.scan = Aircon.ScanInfo()
        self.device: DeviceType = DeviceType.AIRCON
        self.name: str          = DEVICE_AIRCON
        self.room_name: str     = room_name
        self.id: int            = 0
        self.action: str        = 'off'
        self.opmode: str        = 'cool'
        self.fanmove: str       = 'fixed'
        self.fanmode: str       = 'low'
        self.current_temp: float = 27.0
        self.target_temp: int   = 27
        self.last_availability_status: str = ''
        self.availability_fail_count: int = 0
        self.pipe1_temp: float = 0.0
        self.pipe2_temp: float = 0.0
        self.outdoor_temp: float = 0.0
        self.plasma: str       = 'off'
        self.error_code: int    = 0
        self.load_estimate: float = 0.0

    def set_initial_state(self) -> None:
        self.scan.reset()
