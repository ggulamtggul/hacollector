from __future__ import annotations

import asyncio
from queue import Queue
from struct import calcsize, pack, unpack
import time
from typing import Callable

import logging
import config as cfg
from classes.aircon import Aircon
from classes.appconf import MainConfig
from classes.comm import TCPComm
from classes.utils import Color
from consts import (DEVICE_AIRCON, MQTT_FAN_MODE, MQTT_MODE, MQTT_SWING_MODE,
                    MQTT_TARGET_TEMP, PAYLOAD_AUTO, PAYLOAD_COOL, PAYLOAD_DRY,
                    PAYLOAD_FAN_ONLY, PAYLOAD_FIXED, PAYLOAD_HEAT,
                    PAYLOAD_HIGH, PAYLOAD_LOCKOFF, PAYLOAD_LOCKON, PAYLOAD_LOW,
                    PAYLOAD_MEDIUM, PAYLOAD_OFF, PAYLOAD_ON, PAYLOAD_POWER,
                    PAYLOAD_SCAN, PAYLOAD_SILENT, PAYLOAD_STATUS,
                    PAYLOAD_SWING, PAYLOAD_ONLINE, DeviceType)



MAX_READ_ERROR_RETRY = 3


class LGACPacket:
    _WRITER_HEADER_MAGIC    = b'\x80\x00\xa3'
    _RESPONSE_PACKET_SIZE   = 16
    FMT_body_read           = '>BBBBBBBBBBBBBBBB'
    FMT_body_write          = '>BBBB'

    LGAC_ACTION = {
        0x00: PAYLOAD_SCAN,
        0x01: PAYLOAD_STATUS,
        0x02: PAYLOAD_OFF,
        0x03: PAYLOAD_ON,
        0x06: PAYLOAD_LOCKON,
        0x07: PAYLOAD_LOCKOFF
    }
    LGAC_MODE = {
        0: PAYLOAD_COOL,
        1: PAYLOAD_DRY,
        2: PAYLOAD_FAN_ONLY,
        3: PAYLOAD_AUTO,      # PAYLOAD_AUTO, HA do not support auto
        4: PAYLOAD_HEAT
    }
    LGAC_FAN_SPEED = {
        1: PAYLOAD_LOW,
        2: PAYLOAD_MEDIUM,
        3: PAYLOAD_HIGH,
        4: PAYLOAD_AUTO,
        5: PAYLOAD_SILENT,
        6: PAYLOAD_POWER
    }
    LGAC_ACTION_REV        = {v: k for k, v in LGAC_ACTION.items()}
    LGAC_MODE_REV          = {v: k for k, v in LGAC_MODE.items()}
    LGAC_FAN_SPEED_REV     = {v: k for k, v in LGAC_FAN_SPEED.items()}

    def __init__(self, rawdata: bytes | None = None) -> None:
        self.fill_return_head    = 0
        self.action              = 0
        self.fill_unknown1       = 0
        self.fill_unknown2       = 0
        self.groupandid          = 0
        self.fill_unknown3       = 0
        self.current_mode        = 0
        self.set_temp            = 0
        self.current_temp        = 0
        self.pipe1_temp          = 0
        self.pipe2_temp          = 0
        self.fill_outer_sensor   = 0
        self.fill_unknown4       = 0
        self.fill_model          = 0
        self.fill_fixedvalue     = 0
        self.checksum            = 0
        self.str_action: str = ''
        self.str_opmode: str = ''
        self.str_fanmove: str = ''
        self.str_fanmode: str = ''
        if rawdata is not None:
            self.set_packet_data(rawdata)

    @property
    def _body_size(self) -> int:
        return calcsize(LGACPacket.FMT_body_read)

    def set_packet_data(self, rawdata: bytes) -> bool:
        logger = logging.getLogger("LGACPacket")
        try:
            if len(rawdata) != self._body_size:
                logger.debug(
                    f"Error: LGAC Packet size mismatch {len(rawdata)} != {self._body_size}"
                )
                return False
            res = unpack(LGACPacket.FMT_body_read, rawdata)
            (
                self.fill_return_head,
                self.action,
                self.fill_unknown1,
                self.fill_unknown2,
                self.groupandid,
                self.fill_unknown3,
                self.current_mode,
                self.set_temp,
                self.current_temp,
                self.pipe1_temp,
                self.pipe2_temp,
                self.fill_outer_sensor,
                self.fill_unknown4,
                self.fill_model,
                self.fill_fixedvalue,
                self.checksum
            ) = res
            self.set_temp = (self.set_temp & 0x0f) + 0x0f
            self.current_temp = cfg.TEMPERATURE_ADJUST + self.calc_temp(self.current_temp)

            self.pipe1_temp = self.calc_temp(self.pipe1_temp)
            self.pipe2_temp = self.calc_temp(self.pipe2_temp)
            self.get_detail_mode()
            logger.debug(f"LGAC Packet Body = [ {rawdata.hex()} ]")
            return True
        except Exception as e:
            logger.debug(f"Error: LGAC unpack data = [{e}]")
            return False

    def get_lgac_action_data(self, id: str) -> int:
        ret_int = self.LGAC_ACTION_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_lgac_action(self, inbyte: int) -> str:
        ret_enum = self.LGAC_ACTION.get(inbyte)
        return ret_enum if ret_enum is not None else ''

    def get_lgac_mode_data(self, id: str) -> int:
        ret_int = self.LGAC_MODE_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_lgac_mode(self, inbyte: int) -> str:
        ret_enum = self.LGAC_MODE.get(inbyte)
        return ret_enum if ret_enum is not None else ''

    def get_lgac_fanspeed_data(self, id: str) -> int:
        ret_int = self.LGAC_FAN_SPEED_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_lgac_fanspeed(self, inbyte: int) -> str:
        ret_enum = self.LGAC_FAN_SPEED.get(inbyte)
        return ret_enum if ret_enum is not None else ''

    def make_new_packet(self, group, id, action, operation, fanmove, fanspeed, temp) -> None:
        self.groupandid = (group << 4) + id
        self.str_action = action
        self.str_opmode = operation
        self.str_fanmove = fanmove
        self.str_fanmode = fanspeed
        self.set_temp = temp - 0x0f if 18 <= temp <= 30 else 10
        self.set_detail_mode()

    def calc_temp(self, num: int) -> float:
        # maybe value was made from (36 - x) * 4 + 18 * 4.
        return round(54.0 - num / 4, 2)

    def get_detail_mode(self) -> None:
        self.str_action = self.parse_lgac_action(self.action)
        if self.str_action == '':
            self.str_action = PAYLOAD_STATUS

        self.str_opmode = self.parse_lgac_mode(self.current_mode & 0x07)

        if self.current_mode & 0x08:
            self.str_fanmove = PAYLOAD_SWING
        else:
            self.str_fanmove = PAYLOAD_FIXED

        self.str_fanmode = self.parse_lgac_fanspeed((self.current_mode >> 4) & 0x07)
        if self.str_fanmode == '':
            self.str_fanmode = PAYLOAD_LOW

        logger = logging.getLogger("LGACPacket")
        logger.debug(f"LGAC new_packet = [{self}]")

    def set_detail_mode(self) -> None:
        self.action = self.get_lgac_action_data(self.str_action)

        opmode = self.get_lgac_mode_data(self.str_opmode)

        if self.str_fanmove == PAYLOAD_SWING:
            opmode |= 0x08
        mode = opmode

        fan_speed = self.get_lgac_fanspeed_data(self.str_fanmode)

        self.current_mode = (mode & 0x0F) | ((fan_speed << 4) & 0xF0)

    def __repr__(self) -> str:
        return (
            f"GroupandID:{self.groupandid}, action:{self.str_action}, "
            f"operation:{self.str_opmode}, fanmove:{self.str_fanmove}, "
            f"fanmode:{self.str_fanmode}, temp:{self.set_temp}, "
            f"currenttemp:{self.current_temp}, actemp1:{self.pipe1_temp}, actemp2:{self.pipe2_temp}"
        )

    def make_send_packet(self) -> bytes:
        def calc_checksum(body: bytes) -> int:
            checksum = sum(body)
            return (checksum & 0xff) ^ 0x55

        packet = bytes()
        packet += LGACPacket._WRITER_HEADER_MAGIC
        packet += pack(
            LGACPacket.FMT_body_write,
            self.groupandid,
            self.action,
            self.current_mode,
            self.set_temp
        )
        chksum = calc_checksum(packet)
        packet += chksum.to_bytes(1, 'big')
        return packet


class LGACPacketHandler:
    def __init__(self, config: MainConfig | None = None, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.name                       = config.aircon_devicename if config is not None else 'TestAircon'
        self.enabled_device_list: list  = []
        self.aircon: list               = []
        self.type                       = None
        # Initialize reverse mapping here to capture runtime config updates
        if config and config.rooms:
            self.system_room_aircon_rev = {v: k for k, v in config.rooms.items()}
            self.rooms = config.rooms
        else:
            self.system_room_aircon_rev = {v: k for k, v in cfg.SYSTEM_ROOM_AIRCON.items()}
            self.rooms = cfg.SYSTEM_ROOM_AIRCON
        
        if config:
            self.comm: TCPComm              = TCPComm(
                config.aircon_server,
                int(config.aircon_port),
                cfg.MAX_SOCKET_BUFFER,
                cfg.PACKET_RESEND_INTERVAL_SEC,
                read_timeout=config.rs485_timeout
            )
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self.loop: asyncio.AbstractEventLoop = loop if loop else asyncio.get_running_loop()
        self.read_error_count           = 0
        self._lock                      = asyncio.Lock() # Use Lock instead of boolean flag
        self.log                        = logging.getLogger(f"LGAC:{self.name}")
        self.scan_interval              = config.scan_interval if config else cfg.WALLPAD_SCAN_INTERVAL_TIME
        self._recv_buffer: bytearray    = bytearray()
        self.config = config
        self.notify_availability: Callable[[str, str], None] | None = None
        self.prepare_enabled()

    def sync_close_socket(self, loop):
        pass

    def set_notify_function(self, change_aircon_status):
        self.notify_to_homeassistant: Callable[[str, str, Aircon.Info], None] = change_aircon_status

    def set_availability_function(self, publish_availability):
        self.notify_availability: Callable[[str, str], None] = publish_availability

    def prepare_enabled(self):
        for r_id, r_name in self.rooms.items():
            aircon = Aircon(r_name)
            try:
                aircon.id = int(r_id, 16)
            except ValueError:
                self.log.error(f"Invalid ID {r_id} for room {r_name}, defaulting to 0")
            aircon.set_initial_state()
            self.aircon.append(aircon)
        self.enabled_device_list.append((DeviceType.AIRCON, self.aircon))

    def get_room_aircon_number(self, instr: str) -> str:
        ret_str = self.system_room_aircon_rev.get(instr)
        return ret_str if ret_str is not None else ''

    def get_aircon(self, room_name: str) -> Aircon:
        if self.aircon is not None and len(self.aircon) >= 1:
            for item in self.aircon:
                assert isinstance(item, Aircon)
                # Match exact name or name with spaces replaced by underscores (for MQTT compatibility)
                if item.room_name == room_name or item.room_name.replace(' ', '_') == room_name:
                    return item
        assert False, "get_aircon error!"

    def is_checksum_ok(self, body: bytes) -> bool:
        checksum = sum(body[:-1])

        if body[-1] == (checksum & 0xff) ^ 0x55:
            return True
        else:
            return False

    def handle_aircon_mqtt_message(self, topic: list[str], payload: str):
        self.log.debug(f"LGAircon Action From MQTT.{topic}, = {payload}")
        device_str = DEVICE_AIRCON
        room_str = topic[2]
        cmd_str = topic[3]
        try:
            aircon = self.get_aircon(room_str)
            assert isinstance(aircon, Aircon)
            action_str = aircon.action # Default to current action
            opmode_str = aircon.opmode # Default to current opmode

            if cmd_str == MQTT_MODE:
                if payload == PAYLOAD_OFF:
                    action_str = PAYLOAD_OFF
                else:
                    action_str = PAYLOAD_ON
                    opmode_str = payload
            elif cmd_str == MQTT_SWING_MODE:
                if payload == PAYLOAD_ON:
                    aircon.fanmove = PAYLOAD_SWING
                else:
                    aircon.fanmove = PAYLOAD_FIXED
            elif cmd_str == MQTT_FAN_MODE:
                if payload in [PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH, PAYLOAD_SILENT, PAYLOAD_AUTO, PAYLOAD_POWER]:
                    aircon.fanmode = payload
                else:
                    aircon.fanmode = PAYLOAD_OFF
            elif cmd_str == MQTT_TARGET_TEMP:
                aircon.target_temp = int(float(payload))

            # Update aircon object with new action and opmode for consistency
            aircon.action = action_str
            aircon.opmode = opmode_str

            self.log.debug(
                f"act={aircon.action}, opmode={aircon.opmode}, fanmove={aircon.fanmove}, fanspeed={aircon.fanmode}, "
                f"taregt_temp={aircon.target_temp}"
            )
            
            room_no_str = self.get_room_aircon_number(room_str)
            if not room_no_str:
                self.log.error(f"Unknown room: {room_str}")
                return
            aircon_no = int(room_no_str, 16)
            aircon_cmd = Aircon.Info(action_str, opmode_str, aircon.fanmove, aircon.fanmode, 0.0, aircon.target_temp)

            self.loop.call_soon_threadsafe(self.command_queue.put_nowait, (aircon_no, room_str, aircon_cmd))
            
            self.log.debug(
                f"[From HA]{device_str}/{room_str}/set = [mode={aircon.action}, target_temp={aircon.target_temp}]"
            )
        except Exception as e:
            self.log.error(f"[From HA]Error [{e}] {topic} = {payload}")

    async def async_read_packet(self, timeout: float = 2.0) -> bytes | None:
        """
        Reads from the stream and hunts for a valid packet properly.
        Handles fragmentation (split packets) and coalescing (merged packets).
        """
        start_time = time.monotonic()
        
        while (time.monotonic() - start_time) < timeout:
            # 1. Read available data and append to buffer
            new_data = await self.comm.async_read_stream(2048)
            if new_data:
                # self.log.log(f"RX Raw: {new_data.hex()}", Color.Magenta, ColorLog.Level.INFO)
                self._recv_buffer.extend(new_data)
                
                # [Fix] Prevent Buffer Overflow (Memory Leak Protection)
                if len(self._recv_buffer) > LGACPacket._RESPONSE_PACKET_SIZE * 50: # Cap at ~800 bytes
                    self.log.warning(f"Buffer overflow ({len(self._recv_buffer)}b). Clearing garbage.")
                    self._recv_buffer.clear()

            # 2. Packet Hunting Loop
            while len(self._recv_buffer) > 0:
                # Find Header (0x10) - Response header is 0x10, Send header is 0x80
                try:
                    header_idx = self._recv_buffer.index(0x10)
                except ValueError:
                    # No header(0x10) in buffer: trash everything to clear garbage
                    # self.log.log(f"No header(0x10) in buffer: {self._recv_buffer.hex()}", Color.Yellow, ColorLog.Level.DEBUG)
                    self._recv_buffer.clear()
                    # Wait for more data
                    break

                # Discard garbage before the header
                if header_idx > 0:
                    del self._recv_buffer[:header_idx]
                
                # Check if we have enough data for a full packet
                if len(self._recv_buffer) < LGACPacket._RESPONSE_PACKET_SIZE:
                    # Not enough data yet, break inner loop to read more
                    break
                
                # We have at least 16 bytes starting with 0x10. Check Checksum.
                possible_packet = self._recv_buffer[:LGACPacket._RESPONSE_PACKET_SIZE]
                if self.is_checksum_ok(possible_packet):
                    # Valid Packet Found!
                    # Consume the packet from buffer
                    del self._recv_buffer[:LGACPacket._RESPONSE_PACKET_SIZE]
                    return bytes(possible_packet)
                else:
                    # Invalid Checksum. This 0x10 was a false positive or corrupted.
                    # Discard just this one byte (0x10) and continue searching from the next byte
                    del self._recv_buffer[0:1]
                    continue
            
            # Small sleep to prevent tight loop if no data
            await asyncio.sleep(0.05)
            
        return None

    async def async_send_and_get_result(self, group_no: int, id: int, airconset: Aircon.Info, count_error: bool = True) -> Aircon.Info | None:
        async def handle_max_read_error():
            self.log.warning("Too many read errors. Closing socket to force reconnection...")
            await self.comm.close_async_socket()
            # Do not exit, just let the next loop try to reconnect
            # await asyncio.sleep(5) # Optional delay

        self.send_and_get_state: bool = True # Not used anymore but kept for safety if accessed externally, though unlikely.

        packet = LGACPacket(None)
        packet.make_new_packet(
            group_no, id,
            airconset.action, airconset.opmode, airconset.fanmove, airconset.fanmode, airconset.target_temp
        )

        send_packet = packet.make_send_packet()

        ret: Aircon.Info | None = None
        # need some wait
        try:
            await self.comm.connect_async_socket()
            # 재연결 후 버퍼 오염 방지
            if self.comm.connection_reset:
                self._recv_buffer.clear()
                self.comm.connection_reset = False
            ok: bool = await self.comm.async_write_one_chunk(send_packet)
            if ok:
                await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC)
                
                # Use new Packet Hunting method
                read_packet = await self.async_read_packet(timeout=1.5)
                
                if read_packet:
                    self.log.debug(f"Read From LGAC ==> {read_packet.hex()}")

                    new_packet = LGACPacket(read_packet)
                    self.log.debug(f'{new_packet}')

                    ret = Aircon.Info(
                        new_packet.str_action,
                        new_packet.str_opmode,
                        new_packet.str_fanmove,
                        new_packet.str_fanmode,
                        new_packet.current_temp,
                        new_packet.set_temp
                    )
                    self.read_error_count = 0
                else:
                    if count_error:
                        self.log.warning("Read From LGAC FAIL! (Timeout or No valid packet)")
                    else:
                        self.log.debug("Read From LGAC FAIL! (Scanning empty slot)")
                        
                    if count_error:
                        self.read_error_count += 1
                        if self.read_error_count > MAX_READ_ERROR_RETRY:
                            self.read_error_count = 0
                            await handle_max_read_error()
            else:
                self.log.warning(f"Write to LGAC FAIL!{send_packet.hex()}")
                if count_error:
                    await handle_max_read_error()
        except Exception as e:
            self.log.critical(f"Something wrong in Write and read Aircon({e})")
            if count_error:
                await handle_max_read_error()
        finally:
            pass

        return ret

    async def async_get_current_status(self, aircon_no: int, count_error: bool = True) -> Aircon.Info | None:
        aircon_cmd = Aircon.Info(PAYLOAD_STATUS, '', '', '', 25.0, 25)
        self.log.debug(f"Get Aircon Status : {aircon_no}")

        try:
             # Wait for lock with timeout to prevent infinite blocking
            async with asyncio.timeout(5.0): # 5 seconds wait max
                async with self._lock:
                    aircon_info: Aircon.Info | None = await self.async_send_and_get_result(0, aircon_no, aircon_cmd, count_error)
                    if aircon_info:
                        self.log.debug(f"Returned Get Aircon Status : {aircon_info.opmode})")
                        if aircon_info.opmode == PAYLOAD_AUTO:
                            aircon_info.action = PAYLOAD_ON
                        return aircon_info
        except asyncio.TimeoutError:
             self.log.debug(f"Timeout waiting for lock in get_status({aircon_no})")
        return None

    async def async_set_current_mode(self, aircon_no: int, aircon_cmd: Aircon.Info) -> Aircon.Info | None:
        aircon_info: Aircon.Info | None = None

        try:
            # Wait for lock with timeout
            async with asyncio.timeout(5.0):
                async with self._lock:
                    aircon_info = await self.async_send_and_get_result(0, aircon_no, aircon_cmd)
        except asyncio.TimeoutError:
             self.log.debug(f"Timeout waiting for lock in set_mode({aircon_no})")
             
        return aircon_info

    def _is_valid_info(self, info: Aircon.Info | None, id: int, verbose: bool = True) -> bool:
        if not info:
            return False
        
        if info.opmode == '':
            if verbose: self.log.warning(f"Ignored device at ID: 0x{id:02x} (Invalid Opmode)")
            return False
            
        # Stricter temperature check (0 is technically possible but rare for indoor temp, 50 is too high)
        # Assuming indoor unit, reasonable range might be 0-40.
        if not (0 <= info.cur_temp <= 40):
            if verbose: self.log.warning(f"Ignored device at ID: 0x{id:02x} (Invalid Temp: {info.cur_temp})")
            return False
            
        return True

    async def async_scan_all_devices(self):
        """Targeted scan: 이미 rooms에 등록된 기기만 스캔하여 상태를 발행합니다."""
        target_ids = sorted([int(x, 16) for x in self.rooms.keys()])
        if not target_ids:
            self.log.info("No rooms configured. Skipping targeted scan.")
            return

        self.log.info(f"Starting Targeted Discovery Scan: {[f'0x{i:02x}' for i in target_ids]}")
        
        for id in target_ids:
            info = await self.async_get_current_status(id, count_error=False)
            if self._is_valid_info(info, id):
                self.log.info(f"FOUND DEVICE at ID: 0x{id:02x}")
                self._publish_device_state(id, info)
            await asyncio.sleep(1.0)

    async def async_auto_discover_devices(self):
        """
        자동 기기 검색: RS485 주소 범위를 전수 스캔하여
        유효한 기기를 Double-Check 후 자동 등록합니다.
        """
        scan_range = self.config.auto_scan_range if self.config else 16
        self.log.info(f"=== AUTO DISCOVERY START (Range: 0x00 ~ 0x{scan_range - 1:02x}) ===")

        # Phase 1: 1차 스캔 — 응답하는 ID 수집
        self.log.info("[Phase 1] Scanning for responsive devices...")
        candidates = []
        for id in range(scan_range):
            info = await self.async_get_current_status(id, count_error=False)
            if self._is_valid_info(info, id, verbose=False):
                self.log.info(f"  [Phase 1] Candidate found at 0x{id:02x} (temp={info.cur_temp}°C, mode={info.opmode})")
                candidates.append((id, info))
            await asyncio.sleep(0.8)

        if not candidates:
            self.log.warning("=== AUTO DISCOVERY COMPLETE: No devices found ===")
            return

        self.log.info(f"[Phase 1] {len(candidates)} candidate(s) found. Starting verification...")

        # Phase 2: 2차 검증 스캔 — Ghost Device 방지 (Double-Check)
        self.log.info("[Phase 2] Verifying candidates (Double-Check)...")
        verified = []
        for id, first_info in candidates:
            await asyncio.sleep(1.0)
            second_info = await self.async_get_current_status(id, count_error=False)
            if self._is_valid_info(second_info, id, verbose=False):
                self.log.info(f"  [Phase 2] VERIFIED device at 0x{id:02x}")
                verified.append((id, second_info))
            else:
                self.log.warning(f"  [Phase 2] REJECTED device at 0x{id:02x} (failed verification)")

        if not verified:
            self.log.warning("=== AUTO DISCOVERY COMPLETE: All candidates failed verification ===")
            return

        # Phase 3: 미등록 기기 자동 추가
        new_count = 0
        for id, info in verified:
            hex_id = f'{id:02x}'
            if hex_id not in self.rooms:
                auto_name = f'auto_room_0x{id:02x}'
                self.rooms[hex_id] = auto_name
                cfg.SYSTEM_ROOM_AIRCON[hex_id] = auto_name
                self.system_room_aircon_rev[auto_name] = hex_id

                new_aircon = Aircon(auto_name)
                new_aircon.id = id
                new_aircon.set_initial_state()
                self.aircon.append(new_aircon)
                new_count += 1
                self.log.info(f"  AUTO-REGISTERED: 0x{id:02x} -> '{auto_name}'")
            else:
                self.log.debug(f"  Device 0x{id:02x} already configured as '{self.rooms[hex_id]}'")

        # Phase 4: 발견된 전체 기기의 상태 및 availability 발행
        for id, info in verified:
            self._publish_device_state(id, info)

        # enabled_device_list 재구성 (새 기기 포함)
        self.enabled_device_list.clear()
        self.enabled_device_list.append((DeviceType.AIRCON, self.aircon))

        self.log.info(f"=== AUTO DISCOVERY COMPLETE: {len(verified)} device(s) verified, {new_count} newly registered ===")

    def _publish_device_state(self, id: int, info: 'Aircon.Info'):
        """발견된 기기의 상태와 availability를 즉시 발행합니다."""
        for device in self.aircon:
            if device.id == id:
                if hasattr(self, 'notify_to_homeassistant') and self.notify_to_homeassistant:
                    self.notify_to_homeassistant(device.name, device.room_name, info)
                if self.notify_availability:
                    self.notify_availability(device.room_name, PAYLOAD_ONLINE)
                    device.last_availability_status = PAYLOAD_ONLINE
                break

    async def async_scan_aircon_status(self, device_obj: Aircon):
        room_no_str = self.get_room_aircon_number(device_obj.room_name)
        no = int(room_no_str)
        self.log.debug(f"Aircorn Room name = {device_obj.room_name}, Number = {no}")

        aircon_info: Aircon.Info | None  = await self.async_get_current_status(no)
        
        if self.notify_availability:
             status = PAYLOAD_ONLINE if aircon_info else PAYLOAD_OFFLINE
             # Only publish if status changed or periodically?
             # For now, simplistic approach: publish every scan is safe (MQTT deduplicates usually, or we trust Paho)
             # Better: Track last status in Aircon object to reduce traffic.
             if device_obj.last_availability_status != status:
                 self.notify_availability(device_obj.room_name, status)
                 device_obj.last_availability_status = status

        if aircon_info:
            self.notify_to_homeassistant(device_obj.name, device_obj.room_name, aircon_info)

    async def async_scan_aircons(self, now: float):
        for aircon in self.aircon:
            assert isinstance(aircon, Aircon)
            if (now - aircon.scan.tick) > self.scan_interval:
                aircon.scan.tick = now
                self.log.debug(f">>>>>Rescan {aircon} Check Sending!!!!")
                await self.async_scan_aircon_status(aircon)
                await asyncio.sleep(cfg.PACKET_RESEND_INTERVAL_SEC)

    async def async_lgac_main_write_loop(self) -> None:
        while True:
            # await asyncio.sleep(0.01) # Asyncio Queue get handles waiting efficiently
            (aircon_no, room_str, aircon_cmd) = await self.command_queue.get()
            
            assert isinstance(aircon_cmd, Aircon.Info)
            aircon_info = await self.async_set_current_mode(aircon_no, aircon_cmd)
            if aircon_info:
                self.notify_to_homeassistant(DEVICE_AIRCON, room_str, aircon_info)
            self.command_queue.task_done()
