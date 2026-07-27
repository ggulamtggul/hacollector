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
        self.outdoor_temp        = 0.0
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
            self.outdoor_temp = self.calc_temp(self.fill_outer_sensor)
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
        # LGAP protocol formula: (192 - raw) / 3.0 for precise temperature
        if 0 < num < 192:
            return round((192.0 - num) / 3.0, 1)
        return round(54.0 - num / 4, 2)

    def get_detail_mode(self) -> None:
        self.str_action = self.parse_lgac_action(self.action)
        if self.str_action == '':
            self.str_action = PAYLOAD_STATUS

        opmode = (self.current_mode & 0x07)
        self.str_opmode = self.parse_lgac_mode(opmode)

        self.str_fanmove = PAYLOAD_SWING if (self.current_mode & 0x08) else PAYLOAD_FIXED

        parsed_speed = self.parse_lgac_fanspeed((self.current_mode >> 4) & 0x0f)
        if parsed_speed != '':
            self.str_fanmode = parsed_speed

    def set_detail_mode(self) -> None:
        self.action = self.get_lgac_action_data(self.str_action)
        opmode = self.get_lgac_mode_data(self.str_opmode)

        if self.str_fanmove == PAYLOAD_SWING:
            opmode |= 0x08
        mode = opmode

        fan_speed = self.get_lgac_fanspeed_data(self.str_fanmode)

        self.current_mode = mode | (fan_speed << 4) & 0xf0

    def __repr__(self) -> str:
        return (
            f"GroupandID:{self.groupandid}, action:{self.str_action}, "
            f"operation:{self.str_opmode}, fanmove:{self.str_fanmove}, "
            f"fanmode:{self.str_fanmode}, temp:{self.set_temp}, "
            f"currenttemp:{self.current_temp}, actemp1:{self.pipe1_temp}, actemp2:{self.pipe2_temp}, "
            f"outtemp:{self.outdoor_temp}"
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
                cfg.PACKET_RESEND_INTERVAL_SEC
            )
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self._cmd_event: asyncio.Event = asyncio.Event()
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

    def _update_device_state(self, device_obj: Aircon, id: int, info: Aircon.Info, is_intercepted: bool = False):
        if self.notify_availability:
            status = PAYLOAD_ONLINE
            if device_obj.last_availability_status != status:
                self.notify_availability(device_obj.room_name, status)
                device_obj.last_availability_status = status

        # Check for state changes (e.g. Remote Controller actions)
        changed = []
        if device_obj.action != info.action:
            changed.append(f"Power: {device_obj.action or 'off'} -> {info.action}")
        if device_obj.opmode != info.opmode:
            changed.append(f"Mode: {device_obj.opmode or 'none'} -> {info.opmode}")
        if device_obj.target_temp != info.target_temp:
            changed.append(f"TargetTemp: {device_obj.target_temp}C -> {info.target_temp}C")
        if abs(device_obj.current_temp - info.cur_temp) >= 0.5:
            changed.append(f"RoomTemp: {device_obj.current_temp}C -> {info.cur_temp}C")

        if changed and device_obj.action != '':
            tag = "[Status Changed (Intercepted)]" if is_intercepted else "[Status Changed]"
            self.log.info(f"{tag} '{device_obj.room_name}' (ID: 0x{id:02x}) updated: " + " | ".join(changed))

        # Update local device object state to prevent redundant logging
        device_obj.action = info.action
        device_obj.opmode = info.opmode
        device_obj.target_temp = info.target_temp
        device_obj.current_temp = info.cur_temp
        device_obj.pipe1_temp = info.pipe1_temp
        device_obj.pipe2_temp = info.pipe2_temp
        device_obj.outdoor_temp = info.outdoor_temp

        if self.notify_to_homeassistant:
            self.notify_to_homeassistant(device_obj.name, device_obj.room_name, info)

    async def async_safe_flush_buffers(self):
        """
        소켓 커널 버퍼와 수신 버퍼에 잔존하는 데이터를 읽어내고,
        그중 유효한 패킷들은 가로채 파싱하여 즉시 각 에어컨의 상태를 업데이트합니다.
        그 후 버퍼를 비워 찌꺼기 패킷 혼선을 막습니다.
        """
        # 1. 소켓 커널 버퍼의 모든 데이터를 빠르게 읽어와 _recv_buffer에 누적
        if self.comm.reader:
            while True:
                try:
                    data = await asyncio.wait_for(self.comm.reader.read(2048), timeout=0.01)
                    if not data:
                        break
                    self._recv_buffer.extend(data)
                except asyncio.TimeoutError:
                    break
                except Exception:
                    break

        # 2. 수집된 버퍼에서 유효 패킷(체크섬 통과)을 모두 추출하여 실시간 동기화 진행
        while len(self._recv_buffer) > 0:
            try:
                header_idx = self._recv_buffer.index(0x10)
            except ValueError:
                self._recv_buffer.clear()
                break

            if header_idx > 0:
                del self._recv_buffer[:header_idx]
            
            if len(self._recv_buffer) < LGACPacket._RESPONSE_PACKET_SIZE:
                break
            
            possible_packet = self._recv_buffer[:LGACPacket._RESPONSE_PACKET_SIZE]
            if self.is_checksum_ok(possible_packet):
                packet_id = possible_packet[4]
                
                # 타겟 외 패킷 가로채기 파싱 진행
                other_packet = LGACPacket(possible_packet)
                other_room = self.rooms.get(f"{packet_id:02x}")
                if not other_room:
                    other_room = self.rooms.get(f"{packet_id:d}")
                
                if other_room:
                    other_device = self.get_aircon(other_room)
                    other_info = Aircon.Info(
                        other_packet.str_action,
                        other_packet.str_opmode,
                        other_packet.str_fanmove,
                        other_packet.str_fanmode,
                        other_packet.current_temp,
                        other_packet.set_temp
                    )
                    self._update_device_state(other_device, packet_id, other_info, is_intercepted=True)
                
                # 추출된 유효 패킷 버퍼에서 삭제
                del self._recv_buffer[:LGACPacket._RESPONSE_PACKET_SIZE]
            else:
                del self._recv_buffer[0:1]

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
        try:
            self.log.debug(f"LGAircon Action From MQTT.{topic}, = {payload}")
            if len(topic) < 4:
                self.log.debug(f"Ignored short MQTT topic: {topic}")
                return

            device_str = DEVICE_AIRCON
            room_str = topic[2]
            cmd_str = topic[3]
            aircon = self.get_aircon(room_str)
            assert isinstance(aircon, Aircon)

            # [보정] 기존 에어컨의 최근 실제 상태값을 그대로 보존하고 요청된 항목만 갱신
            action_str = aircon.action if aircon.action else PAYLOAD_OFF
            opmode_str = aircon.opmode if aircon.opmode else PAYLOAD_COOL
            fanmove_str = aircon.fanmove if aircon.fanmove else PAYLOAD_FIXED
            fanmode_str = aircon.fanmode if aircon.fanmode else PAYLOAD_SILENT
            target_temp = aircon.target_temp if aircon.target_temp else 24

            if cmd_str == MQTT_MODE:
                if payload == PAYLOAD_OFF:
                    action_str = PAYLOAD_OFF
                else:
                    action_str = PAYLOAD_ON
                    opmode_str = payload
            elif cmd_str == MQTT_SWING_MODE:
                if payload == PAYLOAD_ON:
                    fanmove_str = PAYLOAD_SWING
                else:
                    fanmove_str = PAYLOAD_FIXED
            elif cmd_str == MQTT_FAN_MODE:
                if payload in [PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH, PAYLOAD_SILENT, PAYLOAD_AUTO, PAYLOAD_POWER]:
                    fanmode_str = payload
                else:
                    fanmode_str = PAYLOAD_LOW
            elif cmd_str == MQTT_TARGET_TEMP:
                target_temp = int(float(payload))

            # 객체 상태 동기화
            aircon.action = action_str
            aircon.opmode = opmode_str
            aircon.fanmove = fanmove_str
            aircon.fanmode = fanmode_str
            aircon.target_temp = target_temp

            self.log.debug(
                f"act={aircon.action}, opmode={aircon.opmode}, fanmove={aircon.fanmove}, fanspeed={aircon.fanmode}, "
                f"target_temp={aircon.target_temp}"
            )
            
            aircon_no = int(self.get_room_aircon_number(room_str))
            aircon_cmd = Aircon.Info(
                action_str, opmode_str, fanmove_str, fanmode_str, 0.0, target_temp,
                aircon.pipe1_temp, aircon.pipe2_temp, aircon.outdoor_temp
            )

            self.log.info(
                f"[MQTT Command] Received control request for '{room_str}' (ID: 0x{aircon_no:02x}) -> "
                f"Action: {action_str}, Mode: {opmode_str}, Temp: {target_temp}C, Fan: {fanmode_str}, Swing: {fanmove_str}"
            )

            self.loop.call_soon_threadsafe(self.command_queue.put_nowait, (aircon_no, room_str, aircon_cmd))
            self.loop.call_soon_threadsafe(self._cmd_event.set)
            
            self.log.debug(
                f"[From HA]{device_str}/{room_str}/set = [mode={aircon.action}, target_temp={aircon.target_temp}]"
            )
        except Exception as e:
            self.log.error(f"[From HA]Error [{e}] {topic} = {payload}")

    async def async_read_packet(self, target_groupandid: int | None = None, timeout: float = 2.0) -> bytes | None:
        """
        Reads from the stream and hunts for a valid packet properly.
        Handles fragmentation (split packets) and coalescing (merged packets).
        If target_groupandid is specified, other valid packets will be intercepted and parsed.
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
                    packet_id = possible_packet[4]
                    target_str = f"0x{target_groupandid:02x}" if target_groupandid is not None else "None"
                    self.log.debug(f"[Packet Hunter] Found valid packet. ID: 0x{packet_id:02x} (Target: {target_str})")
                    
                    if target_groupandid is not None and packet_id != target_groupandid:
                        # 체크섬은 맞지만 대기 중인 타겟 ID와 다를 때: 가로채서 즉시 상태 업데이트 진행!
                        other_packet = LGACPacket(possible_packet)
                        other_room = self.rooms.get(f"{packet_id:02x}")
                        if not other_room:
                            other_room = self.rooms.get(f"{packet_id:d}")
                            
                        if other_room:
                            other_device = self.get_aircon(other_room)
                            other_info = Aircon.Info(
                                other_packet.str_action,
                                other_packet.str_opmode,
                                other_packet.str_fanmove,
                                other_packet.str_fanmode,
                                other_packet.current_temp,
                                other_packet.set_temp,
                                other_packet.pipe1_temp,
                                other_packet.pipe2_temp,
                                other_packet.outdoor_temp
                            )
                            self.log.info(f"[Packet Hunter] ID Mismatch. Intercepting for room '{other_room}' (ID: 0x{packet_id:02x}) -> Power: {other_info.action}, Temp: {other_info.cur_temp}")
                            self._update_device_state(other_device, packet_id, other_info, is_intercepted=True)
                        else:
                            self.log.debug(f"[Packet Hunter] Intercepted unregistered ID 0x{packet_id:02x}")
                        
                        # 버퍼에서 이 패킷만 소모시키고 계속 헌팅 수행
                        del self._recv_buffer[:LGACPacket._RESPONSE_PACKET_SIZE]
                        continue
                    
                    # Target ID와 일치하거나 필터링 조건이 없을 때 정상 반환
                    if target_groupandid is not None:
                        self.log.debug(f"[Packet Hunter] ID Matches target 0x{target_groupandid:02x}. Returning packet.")
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
            
            # [Safe Flush 비활성화] 송신 전 소켓 버퍼 비우기가 유효 응답 패킷을 먼저 소모시켜 타임아웃을 유발하는 부작용을 방지하기 위해 제거합니다.
            # await self.async_safe_flush_buffers()
            
            ok: bool = await self.comm.async_write_one_chunk(send_packet)
            if ok:
                await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC)
                
                # 쿼리한 타겟 에어컨 ID 정보
                target_groupandid = (group_no << 4) + id
                read_packet = await self.async_read_packet(target_groupandid=target_groupandid, timeout=1.5)
                
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
                        new_packet.set_temp,
                        new_packet.pipe1_temp,
                        new_packet.pipe2_temp,
                        new_packet.outdoor_temp
                    )
                    self.read_error_count = 0
                    if airconset.action != PAYLOAD_STATUS:
                        self.log.info(f"[RS485 Success] 에어컨 #{id} (Group {group_no}) responded OK. State synced.")
                else:
                    self.log.warning(f"[RS485 Timeout] No response packet matching target ID 0x{target_groupandid:02x} within 1.5s")
                    if count_error:
                        if airconset.action != PAYLOAD_STATUS:
                            self.log.warning(f"[RS485 Fail] 에어컨 #{id} (Group {group_no}) write failed (Timeout/No Response).")
                        else:
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
        # 1. Targeted Scan (Fast Boot)
        target_ids = sorted([int(x, 16) for x in self.rooms.keys()])
        self.log.info(f"Starting Targeted Discovery Scan: {[f'0x{i:02x}' for i in target_ids]}")
        
        found_devices = []
        
        # Scan configured rooms first
        for id in target_ids:
            info = await self.async_get_current_status(id, count_error=False)
            if self._is_valid_info(info, id):
                self.log.info(f"FOUND DEVICE at ID: 0x{id:02x}")
                found_devices.append(id)

                # [FIX] Immediately publish found device state and availability
                for device in self.aircon:
                    if device.id == id:
                        # 1. Update State (Temp, Mode, etc.)
                        if self.notify_to_homeassistant:
                             self.notify_to_homeassistant(device.name, device.room_name, info)
                        
                        # 2. Update Availability (Online)
                        if self.notify_availability:
                             self.notify_availability(device.room_name, PAYLOAD_ONLINE)
                             device.last_availability_status = PAYLOAD_ONLINE
                        break

            # Scan delay
            await asyncio.sleep(1.0) # slightly faster for targeted

        # 2. Full Scan (Optional)
        if hasattr(self, 'config') and self.config.full_scan_on_boot:
             self.log.info("Starting Full Range Scan (0x00 - 0x0F) as requested...")
             for id in range(16):
                 if id in target_ids:
                     continue # Already scanned
                 
                 info = await self.async_get_current_status(id, count_error=False)
                 if self._is_valid_info(info, id):
                     self.log.info(f"FOUND DEVICE at ID: 0x{id:02x}")
                     found_devices.append(id)
                     
                     # [FIX] Immediately publish found device state and availability (Full Scan)
                     for device in self.aircon:
                        if device.id == id:
                             self._update_device_state(device, id, info, is_intercepted=False)
                             break

                 await asyncio.sleep(1.0)
        else:
            self.log.debug("Skipping full range scan (enabled 'full_scan_on_boot' to scan 0x00-0x0F)")

        if found_devices:
            self.log.info(f"Scan Complete. Found devices at IDs: {[f'0x{i:02x}' for i in found_devices]}")
            self.log.info("Please update your configuration with these IDs.")
        else:
            self.log.warning("Scan Complete. No devices found.")

    async def async_scan_aircon_status(self, device_obj: Aircon):
        room_no_str = self.get_room_aircon_number(device_obj.room_name)
        no = int(room_no_str)
        self.log.debug(f"Aircorn Room name = {device_obj.room_name}, Number = {no}")

        aircon_info: Aircon.Info | None  = await self.async_get_current_status(no)
        
        if self.notify_availability:
             if aircon_info:
                 device_obj.availability_fail_count = 0
                 status = PAYLOAD_ONLINE
             else:
                 device_obj.availability_fail_count += 1
                 # 3회 연속 실패하기 전까지는 기존 온라인 상태를 유지하여 간헐적 드랍 시 깜빡임 차단
                 if device_obj.availability_fail_count >= 3:
                     status = PAYLOAD_OFFLINE
                 else:
                     status = device_obj.last_availability_status or PAYLOAD_ONLINE

             if device_obj.last_availability_status != status:
                  self.notify_availability(device_obj.room_name, status)
                  device_obj.last_availability_status = status

        if aircon_info:
            self._update_device_state(device_obj, no, aircon_info, is_intercepted=False)

    async def async_scan_aircons(self, now: float):
        for aircon in self.aircon:
            assert isinstance(aircon, Aircon)
            if (now - aircon.scan.tick) > self.scan_interval:
                # 제어 명령이 대기 중이라면 폴링을 유예하고 즉시 제어 우선권 부여
                if self._cmd_event.is_set():
                    self.log.debug("[Priority Control] High priority MQTT command pending. Deferring scan for instant control response!")
                    break

                aircon.scan.tick = now
                self.log.debug(f">>>>>Rescan {aircon} Check Sending!!!!")
                await self.async_scan_aircon_status(aircon)
                
                # 인터벌 간격 단축 (0.8초 -> 0.2초) 및 명령 감지 시 즉시 중단
                try:
                    await asyncio.wait_for(self._cmd_event.wait(), timeout=0.2)
                    self.log.debug("[Priority Control] High priority MQTT command detected during scan interval! Interrupting scan for instant control execution.")
                    break
                except asyncio.TimeoutError:
                    pass

    async def async_lgac_main_write_loop(self) -> None:
        while True:
            (aircon_no, room_str, aircon_cmd) = await self.command_queue.get()
            self._cmd_event.clear()
            
            # [Queue Debounce] Skip if there is a newer command in the queue for the same aircon
            has_newer = False
            for item in self.command_queue._queue:
                if item[0] == aircon_no:
                    has_newer = True
                    break
            
            if has_newer:
                self.log.debug(f"[Queue Debounce] Discarding outdated command for {room_str} (aircon #{aircon_no})")
                self.command_queue.task_done()
                continue
            
            assert isinstance(aircon_cmd, Aircon.Info)
            self.log.info(
                f"[RS485 Priority Write] Immediate command execution for 에어컨 #{aircon_no} ({room_str}) -> "
                f"Set Temp: {aircon_cmd.target_temp}C, Action: {aircon_cmd.action}, Mode: {aircon_cmd.opmode}, Fan: {aircon_cmd.fanmode}, Swing: {aircon_cmd.fanmove}"
            )
            aircon_info = await self.async_set_current_mode(aircon_no, aircon_cmd)
            if aircon_info:
                self.notify_to_homeassistant(DEVICE_AIRCON, room_str, aircon_info)
            self.command_queue.task_done()
