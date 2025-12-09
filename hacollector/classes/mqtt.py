from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Callable

import paho.mqtt.client as pahomqtt

import config as cfg
from classes.appconf import MainConfig
from classes.utils import Color, ColorLog
from consts import (
                    DEVICE_AIRCON, MQTT_CMD_T, MQTT_CONFIG,
                    MQTT_CURRENT_TEMP, MQTT_FAN_MODE,
                    MQTT_ICON_AIRCON, MQTT_MODE, MQTT_PAYLOAD, MQTT_SET,
                    MQTT_STAT, MQTT_STATE, MQTT_SWING_MODE, MQTT_TARGET_TEMP,
                    MQTT_TEMP, PAYLOAD_AUTO, PAYLOAD_COOL, PAYLOAD_DRY,
                    PAYLOAD_FAN_ONLY, PAYLOAD_HIGH, MQTT_AVAILABILITY,
                    PAYLOAD_LOCKOFF, PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_OFF,
                    PAYLOAD_ON, PAYLOAD_POWER, PAYLOAD_SILENT, PAYLOAD_STATE, PAYLOAD_STATUS, PAYLOAD_SWING, SERVICE_NAME,
                    PAYLOAD_ONLINE, PAYLOAD_OFFLINE,
                    SW_VERSION_STRING, DeviceType
                    )

if TYPE_CHECKING:
    from classes.aircon import Aircon


class Discovery:
    def __init__(self, pub, sub, min_temp=18, max_temp=30) -> None:
        self.pub: list[dict] = pub
        self.sub: list[tuple[str, int]] = sub
        self.min_temp = min_temp
        self.max_temp = max_temp

    def make_topic_and_payload_for_discovery(
        self, kind: str, room: str, device: str, icon_name: str, uid: int | None = None
    ) -> tuple[str, dict]:
        # Sanitize room name for MQTT topics and IDs (No spaces allowed)
        room_safe = room.replace(' ', '_')
        
        common_topic_str = f'{cfg.HA_PREFIX}/{kind}/{room_safe}'
        
        # Availability Topic 설정 (LGAircon/status)
        availability_topic = f'{cfg.CONF_AIRCON_DEVICE_NAME}/{PAYLOAD_STATUS}'

        topic = f'{common_topic_str}_{device}/config'

        # 기본 Payload 구성
        payload = {
            'name': f'{SERVICE_NAME}_{room}_{device}', # Friendly Name can have spaces? uniq_id helps. Let's keep it safe.
            'uniq_id': f'{SERVICE_NAME}_{room_safe}_{device}',
            'device': {
                'name': f'LG System Aircon {room}', # Device entry friendly name
                'ids': f'lg_aircon_{room_safe}',
                'mf': 'LG Electronics',
                'mdl': 'System Aircon (RS485)',
                'sw': SW_VERSION_STRING,
                'configuration_url': 'https://github.com/ggulamtggul/hacollector'
            },
            # Availability 설정 추가
            'pl_not_avail': PAYLOAD_OFFLINE
        }
        if icon_name != '':
            payload['ic'] = icon_name

        # LG 에어컨 전용 설정
        if device == DEVICE_AIRCON:
            aircon_common_topic_str                 = f'{cfg.CONF_AIRCON_DEVICE_NAME}/{kind}/{room_safe}'
            aircon_common_id_str                    = f'{cfg.CONF_AIRCON_DEVICE_NAME}_{room_safe}_{device}'
            
            # device 정보 덮어쓰기 (기존 로직 유지하되 정리)
            # Use RS485 ID for identifiers if available to be robust against name changes
            if uid is not None:
                # Format: lg_aircon_rs485_01
                stable_id = f'lg_aircon_rs485_{uid:02x}'
                payload["device"]["identifiers"] = [stable_id]
                # Unique ID: lg_aircon_rs485_01
                payload['uniq_id'] = stable_id
            else:
                # Fallback to legacy room-based ID
                payload["device"]["identifiers"] = [aircon_common_id_str]
                payload['uniq_id'] = aircon_common_id_str
            
            payload['name']                         = f'LG Aircon {room}'
            
            
            payload[f'{MQTT_MODE}_stat_t']          = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_MODE}_stat_tpl']        = '{{ value_json.mode }}'
            payload[f'{MQTT_MODE}_{MQTT_CMD_T}']    = f'{aircon_common_topic_str}/{MQTT_MODE}'
            payload[f'{MQTT_MODE}s']                = [PAYLOAD_OFF, PAYLOAD_COOL, PAYLOAD_DRY, PAYLOAD_FAN_ONLY, PAYLOAD_AUTO]
            
            payload[f'{MQTT_TEMP}_stat_t']          = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_TEMP}_stat_tpl']        = '{{ value_json.target_temp }}'
            payload[f'{MQTT_TEMP}_step']            = 1
            payload[f'{MQTT_TEMP}_{MQTT_CMD_T}']    = f'{aircon_common_topic_str}/{MQTT_TARGET_TEMP}'
            payload[f'min_{MQTT_TEMP}']             = self.min_temp
            payload[f'max_{MQTT_TEMP}']             = self.max_temp
            
            payload[f'curr_{MQTT_TEMP}_t']          = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'curr_{MQTT_TEMP}_tpl']        = '{{ value_json.current_temp }}'
            # HA Statistics & Graph Support
            payload['device_class']                 = 'temperature'
            payload['state_class']                  = 'measurement'
            
            payload[f'{MQTT_FAN_MODE}_stat_t']      = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_FAN_MODE}_stat_tpl']    = '{{ value_json.fan_mode }}'
            payload[f'{MQTT_FAN_MODE}_{MQTT_CMD_T}'] = f'{aircon_common_topic_str}/{MQTT_FAN_MODE}'
            payload[f'{MQTT_FAN_MODE}s']            = [PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH, PAYLOAD_AUTO, PAYLOAD_SILENT, PAYLOAD_POWER, PAYLOAD_OFF]
            
            payload[f'{MQTT_SWING_MODE}_stat_t']    = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_SWING_MODE}_stat_tpl']  = '{{ value_json.swing_mode }}'
            payload[f'{MQTT_SWING_MODE}_{MQTT_CMD_T}'] = f'{aircon_common_topic_str}/{MQTT_SWING_MODE}'
            payload[f'{MQTT_SWING_MODE}s']          = [PAYLOAD_ON, PAYLOAD_OFF]
            
        return topic, payload

    def discovery_aircon(self, remove: bool, enabled_device: list | None = None) -> None:
        from classes.aircon import Aircon

        assert isinstance(enabled_device, list)
        for room_aircon in enabled_device:
            if isinstance(room_aircon, Aircon):
                room_name = room_aircon.room_name
                if room_name is not None:
                    ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
                        kind=cfg.HA_CLIMATE, room=room_name, device=DEVICE_AIRCON, icon_name=MQTT_ICON_AIRCON, uid=room_aircon.id
                    )
                    # 명령 수신 구독
                    self.sub.append((ha_payload[f'{MQTT_MODE}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_TEMP}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_FAN_MODE}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_SWING_MODE}_{MQTT_CMD_T}'], 0))
                    
                    if remove:
                        self.pub.append({ha_topic: ''})
                    else:
                        self.pub.append({ha_topic: json.dumps(ha_payload)})

    def make_discovery_list(self, dev_name: DeviceType, enabled_device: list, remove: bool) -> None:
        if dev_name == DeviceType.AIRCON:
            self.discovery_aircon(remove, enabled_device)


class MqttHandler:
    def __init__(self, config: MainConfig, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.loop                                   = loop if loop else asyncio.get_running_loop()
        self.server                                 = config.mqtt_server
        self.port                                   = int(config.mqtt_port)
        self.anonymous                              = config.mqtt_anonymous
        self.id                                     = config.mqtt_id
        self.pw                                     = config.mqtt_pw
        self.min_temp                               = config.min_temp
        self.max_temp                               = config.max_temp
        self.mqtt_client: pahomqtt.Client | None    = None
        self.start_discovery                        = False
        self.mqtt_connect_error                     = False
        self.subscribe_list: list[tuple[str, int]]  = []
        self.publish_list: list[dict]               = []
        self.ignore_handling: bool                  = False
        # Availability Topic
        self.availability_topic                     = f'{cfg.CONF_AIRCON_DEVICE_NAME}/{PAYLOAD_STATUS}'

    def set_enabled_list(self, enabled_list: list):
        self.enabled_list = enabled_list

    def set_aircon_mqtt_handler(self, handle_aircon_mqtt_message):
        self.aircon_mqtt_handler: Callable[[list[str], str], None] = handle_aircon_mqtt_message

    def set_reconnect_action(self, reconnect_action):
        self.reconnect_action: Callable[[], None] = reconnect_action

    def set_ignore_handling(self):
        self.ignore_handling = True

    def connect_mqtt(self) -> None:
        color_log = ColorLog()
        is_anonymous = True if self.anonymous == 'True' else False
        server = self.server
        port = self.port
        self.mqtt_client = pahomqtt.Client()
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_subscribe = self.on_subscribe
        self.mqtt_client.on_connect = self.on_connect

        # LWT (Last Will and Testament) 설정: 연결이 끊기면 자동으로 offline 메시지 전송
        self.mqtt_client.will_set(self.availability_topic, PAYLOAD_OFFLINE, qos=1, retain=True)

        if not is_anonymous:
            username = self.id
            password = self.pw
            if server == '' or username == '' or password == '':
                color_log.log(
                    f"{cfg.CONF_MQTT} Check Config! Server[{server}] ID[{username}] PW[{password}]",
                    Color.Red
                )
                return
            self.mqtt_client.username_pw_set(username=username, password=password)

        color_log.log(f"Connecting MQTT... {server}:{port}", Color.Yellow)
        try:
            self.mqtt_client.connect(server, port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            color_log.log(f"MQTT Connection Failed: {e}", Color.Red)

    def cleanup(self) -> None:
        if self.mqtt_client:
            # 종료 시 offline 메시지 전송
            self.mqtt_client.publish(self.availability_topic, PAYLOAD_OFFLINE, retain=True)
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.mqtt_connect_error = True

    def handle_message_from_mqtt(self, topic: list[str], payload: str) -> None:
        color_log = ColorLog()
        # debug logs...
        if topic[0] == cfg.CONF_AIRCON_DEVICE_NAME:
            self.aircon_mqtt_handler(topic, payload)

    async def homeassistant_device_discovery(self, initial: bool = False, remove: bool = False) -> None:
        self.subscribe_list = []
        # HA 제어용 토픽 구독
        self.subscribe_list.append((f'{cfg.HA_CALLBACK_MAIN}/{cfg.HA_CALLBACK_BRIDGE}/#', 0))
        self.publish_list = []

        color_log = ColorLog()
        color_log.log("** Starting Devices Discovery.", Color.Yellow)
        discovery = Discovery(self.publish_list, self.subscribe_list, self.min_temp, self.max_temp)

        for dev_name, enabled_device in self.enabled_list:
            discovery.make_discovery_list(DeviceType(dev_name), enabled_device, remove)

        if self.mqtt_client:
            if initial:
                self.mqtt_client.subscribe(self.subscribe_list)
            
            # Discovery 메시지 발행
            for ha in self.publish_list:
                for topic, payload in ha.items():
                    if payload: 
                        # 1. 좀비 엔티티 제거를 위해 빈 값 전송
                        self.mqtt_client.publish(topic, "", retain=True, qos=1)
                        # Switch to async sleep to prevent blocking event loop
                        await asyncio.sleep(0.1)
                        # 2. 새로운 설정 전송
                        self.mqtt_client.publish(topic, payload, retain=True, qos=1)
                        await asyncio.sleep(0.1)
                    else:
                        # 제거 모드
                        self.mqtt_client.publish(topic, "", retain=True, qos=1)

            # 모든 등록이 끝나면 Online 상태 전송
            if not remove:
                self.mqtt_client.publish(self.availability_topic, PAYLOAD_ONLINE, retain=True, qos=1)
                color_log.log(f"Sent Online Status to {self.availability_topic}", Color.Green)

        if self.start_discovery:
            self.start_discovery = False

    def send_state_to_homeassistant(self, device: str, room: str, value: dict) -> None:
        # 상태 업데이트 시에도 payload는 그대로 전송하되, availability는 별도 토픽으로 관리됨
        room_safe = room.replace(' ', '_')
        if self.mqtt_client:
            if device == DEVICE_AIRCON:
                prefix = cfg.CONF_AIRCON_DEVICE_NAME
                topic = f'{prefix}/{cfg.HA_CLIMATE}/{room_safe}/{PAYLOAD_STATE}'
                self.mqtt_client.publish(topic, json.dumps(value))
    
    def change_aircon_status(self, dev_str: str, room_str: str, aircon_info: Aircon.Info):
        # 기존 로직 유지
        color_log = ColorLog()
        if aircon_info.action in [PAYLOAD_OFF, PAYLOAD_LOCKOFF]:
            mode = PAYLOAD_OFF
        else:
            mode = aircon_info.opmode
            
        if aircon_info.fanmove == PAYLOAD_SWING:
            swing = PAYLOAD_ON
        else:
            swing = PAYLOAD_OFF
            
        value = {
            f'{MQTT_MODE}': f'{mode}',
            f'{MQTT_SWING_MODE}': f'{swing}',
            f'{MQTT_FAN_MODE}': f'{aircon_info.fanmode}',
            f'{MQTT_CURRENT_TEMP}': f'{aircon_info.cur_temp:.2f}',
            f'{MQTT_TARGET_TEMP}': f'{aircon_info.target_temp}'
        }
        self.send_state_to_homeassistant(dev_str, room_str, value)

    def on_connect(self, client, userdata, flags, rc):
        color_log = ColorLog()
        if int(rc) == 0:
            color_log.log("[MQTT] Connected OK", Color.Yellow)
            # 연결 즉시 온라인 상태 전송
            client.publish(self.availability_topic, PAYLOAD_ONLINE, retain=True)
            self.start_discovery = True
            
            # Schedule discovery safely on the main loop
            # This callback runs in a separate thread (paho loop), so we must use threadsafe scheduling
            asyncio.run_coroutine_threadsafe(self.homeassistant_device_discovery(initial=True), self.loop)
        else:
            color_log.log(f"[MQTT] Connection Failed: rc={rc}", Color.Red)
            self.mqtt_connect_error = True

    def on_message(self, client, obj, msg: pahomqtt.MQTTMessage):
        if not self.ignore_handling:
            rcv_topic = msg.topic.split('/')
            rcv_payload = msg.payload.decode()
            
            # HA 관리 명령 처리 (restart, remove 등)
            if 'config' in rcv_topic and rcv_topic[3] == 'restart':
                 # Schedule safe restart
                 asyncio.run_coroutine_threadsafe(self.homeassistant_device_discovery(), self.loop)
                 return
            
            if not self.start_discovery:
                self.handle_message_from_mqtt(rcv_topic, rcv_payload)

    def on_subscribe(self, client, obj, mid, granted_qos):
        pass
