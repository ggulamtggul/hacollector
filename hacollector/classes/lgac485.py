from __future__ import annotations

import asyncio
from queue import Queue
from struct import calcsize, pack, unpack
import time
from typing import Callable

import config as cfg
from classes.aircon import Aircon
from classes.appconf import MainConfig
from classes.comm import TCPComm
from classes.utils import Color, ColorLog
from consts import (DEVICE_AIRCON, MQTT_FAN_MODE, MQTT_MODE, MQTT_SWING_MODE,
                    MQTT_TARGET_TEMP, PAYLOAD_AUTO, PAYLOAD_COOL, PAYLOAD_DRY,
                    PAYLOAD_FAN_ONLY, PAYLOAD_FIXED, PAYLOAD_HEAT,
                    PAYLOAD_HIGH, PAYLOAD_LOCKOFF, PAYLOAD_LOCKON, PAYLOAD_LOW,
                    PAYLOAD_MEDIUM, PAYLOAD_OFF, PAYLOAD_ON, PAYLOAD_POWER,
                    PAYLOAD_SCAN, PAYLOAD_SILENT, PAYLOAD_STATUS,
                    PAYLOAD_SWING, DeviceType)



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
        color_log = ColorLog()
        try:
            if len(rawdata) != self._body_size:
                color_log.log(
                    f"Error: LGAC Packet size mismatch {len(rawdata)} != {self._body_size}",
                    Color.Red,
                    ColorLog.Level.DEBUG
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
            color_log.log(f"LGAC Packet Body = [ {rawdata.hex()} ]", Color.White, ColorLog.Level.DEBUG)
            return True
        except Exception as e:
            color_log.log(f"Error: LGAC unpack data = [{e}]", Color.Red, ColorLog.Level.DEBUG)
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
        self.set_temp = temp - 0x0f if 18 < temp <= 30 else 10
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

        color_log = ColorLog()
        color_log.log(f"LGAC new_packet = [{self}]", Color.White, ColorLog.Level.DEBUG)

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
    def __init__(self, config: MainConfig | None = None) -> None:
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
        self.command_queue: Queue       = Queue()
        self.loop: asyncio.AbstractEventLoop
        self.read_error_count           = 0
        self._lock                      = asyncio.Lock() # Use Lock instead of boolean flag
        self.log                        = ColorLog()
        self.prepare_enabled()

    def sync_close_socket(self, loop):
        pass

    def set_notify_function(self, change_aircon_status):
        self.notify_to_homeassistant: Callable[[str, str, Aircon.Info], None] = change_aircon_status

    def prepare_enabled(self):
        for r_id, r_name in self.rooms.items():
            aircon = Aircon(r_name)
            try:
                aircon.id = int(r_id, 16)
            except ValueError:
                self.log.log(f"Invalid ID {r_id} for room {r_name}, defaulting to 0", Color.Red)
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
                if item.room_name == room_name:
                    return item
        assert False, "get_aircon error!"

    def is_checksum_ok(self, body: bytes) -> bool:
        checksum = sum(body[:-1])

        if body[-1] == (checksum & 0xff) ^ 0x55:
            return True
        else:
            return False

    def handle_aircon_mqtt_message(self, topic: list[str], payload: str):
        self.log.log(f"LGAircon Action From MQTT.{topic}, = {payload}", Color.Yellow, ColorLog.Level.DEBUG)
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

            self.log.log(
                f"act={aircon.action}, opmode={aircon.opmode}, fanmove={aircon.fanmove}, fanspeed={aircon.fanmode}, "
                f"taregt_temp={aircon.target_temp}",
                Color.White,
                ColorLog.Level.DEBUG
            )
            
            aircon_no = int(self.get_room_aircon_number(room_str))
            aircon_cmd = Aircon.Info(action_str, opmode_str, aircon.fanmove, aircon.fanmode, 0.0, aircon.target_temp)

            self.command_queue.put((aircon_no, room_str, aircon_cmd))

            self.log.log(
                f"[From HA]{device_str}/{room_str}/set = [mode={aircon.action}, target_temp={aircon.target_temp}]"
            )
        except Exception as e:
            self.log.log(f"[From HA]Error [{e}] {topic} = {payload}", Color.Red)

    async def async_read_until_tail(self) -> bytes:
        # Optimized reading: try to read the full body size at once
        res_packet = await self.comm.async_get_data_direct(LGACPacket._RESPONSE_PACKET_SIZE)
        return res_packet

    async def async_read_one_chunk(self) -> bytes | None:
        try:
            body = await self.async_read_until_tail()
            if len(body) != LGACPacket._RESPONSE_PACKET_SIZE:
                # self.log.log("Packet size is not MATCH! - retry!", Color.Blue, ColorLog.Level.DEBUG)
                return None

            if not self.is_checksum_ok(body):
                self.log.log(f"Unhappy CASE(Aircon) : Checksum Error![{body.hex()}]", Color.Red)
                self.log.log("trying to read again!! ******", Color.Blue, ColorLog.Level.DEBUG)
                return None

            return body

        except Exception as e:
            self.log.log(f"[Error LGAC rs485] : {e} : Cannot read From LGAC!", Color.Yellow, ColorLog.Level.WARN)
        return None

    async def async_send_and_get_result(self, group_no: int, id: int, airconset: Aircon.Info) -> Aircon.Info | None:
        async def handle_max_read_error():
            self.log.log("Too many read errors. Closing socket to force reconnection...", Color.Red, ColorLog.Level.WARN)
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
            ok: bool = await self.comm.async_write_one_chunk(send_packet)
            if ok:
                await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC)
                read_packet = await self.async_read_one_chunk()
                if read_packet:
                    self.log.log(f"Read From LGAC ==> {read_packet.hex()}", Color.Green, ColorLog.Level.DEBUG)

                    new_packet = LGACPacket(read_packet)
                    self.log.log(f'{new_packet}', Color.Green, ColorLog.Level.DEBUG)

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
                    self.log.log("Read From LGAC FAIL!", Color.Green, ColorLog.Level.WARN)
                    self.read_error_count += 1
                    if self.read_error_count > MAX_READ_ERROR_RETRY:
                        self.read_error_count = 0
                        await handle_max_read_error()
            else:
                self.log.log(f"Write to LGAC FAIL!{send_packet.hex()}", Color.Yellow, ColorLog.Level.WARN)
                await handle_max_read_error()
        except Exception as e:
            self.log.log(f"Something wrong in Write and read Aircon({e})", Color.Red, ColorLog.Level.CRITICAL)
            await handle_max_read_error()
        finally:
            # We don't necessarily need to close socket every time if we want persistent connection,
            # but the original logic seemed to prefer closing or maybe it was just for safety.
            # Let's keep close for now to match original behavior but async.
            # Actually, for RS485/TCP bridges, keeping connection might be better, but let's stick to safe close if that was the intent.
            # However, frequent open/close might be overhead.
            # The original code had `await self.comm.close_async_socket()` in finally.
            await self.comm.close_async_socket()
            # self.send_and_get_state = False

        return ret

    async def async_get_current_status(self, aircon_no: int) -> Aircon.Info | None:
        aircon_cmd = Aircon.Info(PAYLOAD_STATUS, '', '', '', 25.0, 25)
        self.log.log(f"Get Aircon Status : {aircon_no}", Color.Yellow, ColorLog.Level.DEBUG)

        try:
             # Wait for lock with timeout to prevent infinite blocking
            async with asyncio.timeout(5.0): # 5 seconds wait max
                async with self._lock:
                    aircon_info: Aircon.Info | None = await self.async_send_and_get_result(0, aircon_no, aircon_cmd)
                    if aircon_info:
                        self.log.log(f"Returned Get Aircon Status : {aircon_info.opmode})", Color.Yellow, ColorLog.Level.DEBUG)
                        if aircon_info.opmode == PAYLOAD_AUTO:
                            aircon_info.action = PAYLOAD_ON
                        return aircon_info
        except asyncio.TimeoutError:
             self.log.log(f"Timeout waiting for lock in get_status({aircon_no})", Color.Yellow, ColorLog.Level.DEBUG)
        return None

    async def async_set_current_mode(self, aircon_no: int, aircon_cmd: Aircon.Info) -> Aircon.Info | None:
        aircon_info: Aircon.Info | None = None

        try:
            # Wait for lock with timeout
            async with asyncio.timeout(5.0):
                async with self._lock:
                    aircon_info = await self.async_send_and_get_result(0, aircon_no, aircon_cmd)
        except asyncio.TimeoutError:
             self.log.log(f"Timeout waiting for lock in set_mode({aircon_no})", Color.Yellow, ColorLog.Level.DEBUG)
             
        return aircon_info

    def _is_valid_info(self, info: Aircon.Info | None, id: int, verbose: bool = True) -> bool:
        if not info:
            return False
        
        if info.opmode == '':
            if verbose: self.log.log(f"Ignored device at ID: 0x{id:02x} (Invalid Opmode)", Color.Yellow)
            return False
            
        # Stricter temperature check (0 is technically possible but rare for indoor temp, 50 is too high)
        # Assuming indoor unit, reasonable range might be 0-40.
        if not (0 <= info.cur_temp <= 40):
            if verbose: self.log.log(f"Ignored device at ID: 0x{id:02x} (Invalid Temp: {info.cur_temp})", Color.Yellow)
            return False
            
        return True

    async def async_scan_all_devices(self):
        self.log.log("Starting Auto Discovery Scan (0x00 - 0x0F)...", Color.Cyan)
        found_devices = []
        
        for id in range(16):  # 0x00 to 0x0F
            info = await self.async_get_current_status(id)
            if self._is_valid_info(info, id):
                self.log.log(f"FOUND DEVICE at ID: 0x{id:02x}", Color.Green, ColorLog.Level.INFO)
                found_devices.append(id)
            
            # Slow down scan to prevent timeouts (User Request)
            await asyncio.sleep(1.5)
        
        if found_devices:
            self.log.log(f"Scan Complete. Found devices at IDs: {[f'0x{i:02x}' for i in found_devices]}", Color.Cyan)
            self.log.log("Please update your configuration with these IDs.", Color.Cyan)
        else:
            self.log.log("Scan Complete. No devices found.", Color.Yellow)

    async def async_scan_aircon_status(self, device_obj: Aircon):
        room_no_str = self.get_room_aircon_number(device_obj.room_name)
        no = int(room_no_str)
        self.log.log(f"Aircorn Room name = {device_obj.room_name}, Number = {no}", Color.White, ColorLog.Level.DEBUG)

        aircon_info: Aircon.Info | None  = await self.async_get_current_status(no)
        if aircon_info:
            self.notify_to_homeassistant(device_obj.name, device_obj.room_name, aircon_info)

    async def async_scan_aircons(self, now: float):
        for aircon in self.aircon:
            assert isinstance(aircon, Aircon)
            if (now - aircon.scan.tick) > cfg.WALLPAD_SCAN_INTERVAL_TIME:
                aircon.scan.tick = now
                self.log.log(f">>>>>Rescan {aircon} Check Sending!!!!", Color.Blue, ColorLog.Level.DEBUG)
                await self.async_scan_aircon_status(aircon)
                await asyncio.sleep(cfg.PACKET_RESEND_INTERVAL_SEC)

    async def async_lgac_main_write_loop(self) -> None:
        while True:
            await asyncio.sleep(0.01)
            if not self.command_queue.empty():
                (aircon_no, room_str, aircon_cmd) = self.command_queue.get()
                assert isinstance(aircon_cmd, Aircon.Info)
                aircon_info = await self.async_set_current_mode(aircon_no, aircon_cmd)
                if aircon_info:
                    self.notify_to_homeassistant(DEVICE_AIRCON, room_str, aircon_info)
