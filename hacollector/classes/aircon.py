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
        raw_packet: str = ''

    def __init__(self, room_name: str = '') -> None:
        self.scan = Aircon.ScanInfo()
        self.device: DeviceType = DeviceType.AIRCON
        self.name: str          = DEVICE_AIRCON
        self.room_name: str     = room_name
        self.id: int            = 0
        self.action: str        = 'off'
        self.opmode: str        = 'cool'
        self.fanmove: str       = 'fixed'
        self.fanmode: str       = 'silent'
        self.current_temp: float = 27.0
        self.target_temp: int   = 27
        self.last_availability_status: str = ''
        self.availability_fail_count: int = 0
        self.pipe1_temp: float = 0.0
        self.pipe2_temp: float = 0.0
        self.outdoor_temp: float = 0.0
        self._temp_candidate: float | None = None
        self._temp_candidate_count: int = 0

    def filter_room_temp(self, new_temp: float, required_consecutive: int = 2) -> float:
        """
        Filters small temperature oscillations (e.g. 30.0C <-> 30.3C).
        - Changes >= 1.0C are applied immediately (Fast response).
        - Small changes (< 1.0C) must be received consecutively (default 2 times) to be confirmed.
        """
        if new_temp <= 0.0:
            return self.current_temp

        new_temp_rounded = round(new_temp, 1)
        current_temp_rounded = round(self.current_temp, 1)

        # Same temperature: reset candidate
        if new_temp_rounded == current_temp_rounded:
            self._temp_candidate = None
            self._temp_candidate_count = 0
            return current_temp_rounded

        # Large temperature jump: apply immediately
        if abs(new_temp_rounded - current_temp_rounded) >= 1.0:
            self._temp_candidate = None
            self._temp_candidate_count = 0
            return new_temp_rounded

        # Small temperature fluctuation: check consecutive count
        if self._temp_candidate == new_temp_rounded:
            self._temp_candidate_count += 1
            if self._temp_candidate_count >= required_consecutive:
                self._temp_candidate = None
                self._temp_candidate_count = 0
                return new_temp_rounded
        else:
            self._temp_candidate = new_temp_rounded
            self._temp_candidate_count = 1

        # Not yet confirmed: maintain previous stable temperature
        return current_temp_rounded

    def set_initial_state(self) -> None:
        self.scan.reset()
        self._temp_candidate = None
        self._temp_candidate_count = 0
