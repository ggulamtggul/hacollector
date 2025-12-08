import asyncio
import configparser
import pathlib
import sys

from dotenv import load_dotenv

import config as cfg
from classes.appconf import MainConfig
from classes.hub import Hub
from classes.lgac485 import LGACPacketHandler
from classes.mqtt import MqttHandler
from classes.utils import Color, ColorLog
from consts import DEVICE_AIRCON, SW_VERSION_STRING


async def main(loop: asyncio.AbstractEventLoop, first_run: bool):
    root_dir = pathlib.Path.cwd()

    color_log: ColorLog

    # 로그 준비
    if first_run:
        color_log = ColorLog(cfg.CONF_LOGFILE)
        if not color_log.prepare_logs(root=root_dir, sub_path='log', file_name=cfg.CONF_LOGFILE):
            sys.exit(1)
        color_log.set_level(cfg.CONF_LOGLEVEL)
    else:
        color_log = ColorLog()

    color_log.log(f"Starting...{SW_VERSION_STRING}", Color.Yellow)

    # 설정 파일 읽기
    conf_path = root_dir / cfg.CONF_FILE
    config = configparser.ConfigParser()
    config.read(conf_path)

    app_config = MainConfig()
    if not app_config.read_config_file(config):
        color_log.log("haclooector Configuration is invalid!", Color.Red)
        sys.exit(1)

    # .env 로드 및 로그레벨 반영
    load_dotenv()
    app_config.load_env_values()
    color_log.set_level(app_config.log_level)

    # ✅ LG 에어컨만 사용
    aircon = LGACPacketHandler(app_config)
    mqtt = MqttHandler(app_config)

    def close_all_devices_sockets():
        aircon.sync_close_socket(loop)

    def prepare_reconnect():
        mqtt.set_ignore_handling()
        close_all_devices_sockets()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    color_log.log(
        f"{cfg.CONF_AIRCON_DEVICE_NAME} Configuration: "
        f"[{app_config.aircon_server}:{app_config.aircon_port}]"
    )

    # 콜백 연결 (Kocom 제거)
    aircon.set_notify_function(mqtt.change_aircon_status)
    mqtt.set_aircon_mqtt_handler(aircon.handle_aircon_mqtt_message)
    mqtt.set_reconnect_action(prepare_reconnect)

    # ✅ 허브 생성 (Kocom/Wallpad 없이)
    #   Hub 시그니처가 (aircon_handler, mqtt_handler) 형태
    hub = Hub(aircon, mqtt)

    # 사용 장치 등록: 에어컨만
    hub.add_devices([DEVICE_AIRCON])

    # HA Discovery용 enabled 리스트: 에어컨만
    enabled_list = []
    enabled_list.extend(aircon.enabled_device_list)
    mqtt.set_enabled_list(enabled_list)

    color_log.log("Now entering main loop!", Color.Green, ColorLog.Level.DEBUG)

    # MQTT 연결 + ✅ 강제 1회 디스커버리 킥 (on_connect 타이밍 이슈 대비)
    try:
        mqtt.connect_mqtt()
        await asyncio.sleep(1.0)
        mqtt.homeassistant_device_discovery(initial=True)
    except Exception as e:
        color_log.log(
            f"Error connecting MQTT Server. Check MQTT configuration!({e})",
            Color.Red,
            ColorLog.Level.CRITICAL
        )
        sys.exit(1)

    # 에어컨 쓰기 루프 + 주기 스캔만 동작
    tasks = asyncio.gather(
        aircon.async_lgac_main_write_loop(),
        hub.async_scan_thread()
    )
    try:
        await tasks
    except asyncio.CancelledError:
        color_log.log("Restart revoked by HomeAssistant Web Service.")
        pass

    color_log.log("========= END loop(Will not show!) ========", Color.Red, ColorLog.Level.DEBUG)
    color_log.log("End of Program.")
    loop.stop()


# entrypoint: 에러/재시작 루프
if __name__ == '__main__':
    loop: asyncio.AbstractEventLoop
    first_run: bool = True
    while True:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(main(loop, first_run))
            loop.close()
            first_run = False
            color_log = ColorLog()
            color_log.log("Exit from main loop. Restarting!", Color.Blue)
        except KeyboardInterrupt:
            print("User send Ctrl-C. so, Exiting...")
            sys.exit(1)
        print("* Maybe Called by HA for reconnect EW11 devices. so, Restarting.*")
