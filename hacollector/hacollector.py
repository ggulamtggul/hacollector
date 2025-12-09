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
    app_config = MainConfig()
    
    # .env 로드 및 로그레벨 반영 (Prioritize Options/Env)
    load_dotenv()
    app_config.load_env_values()

    # 설정 파일 읽기 (Legacy Support, Optional)
    conf_path = root_dir / cfg.CONF_FILE
    config = configparser.ConfigParser()
    config.read(conf_path)
    
    # Merge Legacy Config if exists
    app_config.read_config_file(config)

    # Validate Final Configuration
    if not app_config.validate():
        color_log.log("Configuration is invalid! Missing Critical Fields.", Color.Red)
        sys.exit(1)
    color_log.set_level(app_config.log_level)

    # 핸들러 초기화
    aircon = LGACPacketHandler(app_config, loop)
    # Pass loop to MqttHandler for scheduling callbacks safely
    mqtt = MqttHandler(app_config, loop)

    def close_all_devices_sockets():
        aircon.sync_close_socket(loop)

    def prepare_reconnect():
        mqtt.set_ignore_handling()
        close_all_devices_sockets()
        mqtt.cleanup()  # MQTT 종료 처리 추가
        for task in asyncio.all_tasks(loop):
            task.cancel()

    color_log.log(
        f"{cfg.CONF_AIRCON_DEVICE_NAME} Configuration: "
        f"[{app_config.aircon_server}:{app_config.aircon_port}]"
    )

    # 콜백 연결
    aircon.set_notify_function(mqtt.change_aircon_status)
    mqtt.set_aircon_mqtt_handler(aircon.handle_aircon_mqtt_message)
    mqtt.set_reconnect_action(prepare_reconnect)

    # 허브 생성
    hub = Hub(aircon, mqtt)
    hub.add_devices([DEVICE_AIRCON])

    # HA Discovery용 리스트 설정
    enabled_list = []
    enabled_list.extend(aircon.enabled_device_list)
    mqtt.set_enabled_list(enabled_list)

    # Device Scan will be performed in main task
    # await aircon.async_scan_all_devices()

    color_log.log("Now entering main loop!", Color.Green, ColorLog.Level.DEBUG)

    try:
        mqtt.connect_mqtt()
        # 연결 대기 후 Discovery 수행
        await asyncio.sleep(1.0)
        await mqtt.homeassistant_device_discovery(initial=True)
    except Exception as e:
        color_log.log(f"Error connecting MQTT Server: {e}", Color.Red, ColorLog.Level.CRITICAL)
        sys.exit(1)

    # 메인 태스크 실행
    tasks = asyncio.gather(
        aircon.async_lgac_main_write_loop(),
        hub.async_scan_thread(),
        aircon.async_scan_all_devices()  # Background Scan
    )
    try:
        await tasks
    except asyncio.CancelledError:
        color_log.log("Tasks Cancelled (Restarting or Stopping).", Color.Yellow)
        pass
    except Exception as e:
        color_log.log(f"Critical Error in Main Loop: {e}", Color.Red)

    color_log.log("End of Program Session.", Color.Blue)


if __name__ == '__main__':
    loop: asyncio.AbstractEventLoop
    first_run: bool = True
    while True:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(main(loop, first_run))
            loop.close()
            first_run = False
            
            # 재시작 전 대기
            import time
            time.sleep(2)
            
            color_log = ColorLog()
            color_log.log("Restarting main loop...", Color.Blue)
        except KeyboardInterrupt:
            print("\nUser Stopped Program.")
            sys.exit(0)
