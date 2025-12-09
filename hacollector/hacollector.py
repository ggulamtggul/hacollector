import asyncio
import logging
import pathlib
import sys

from dotenv import load_dotenv

import config as cfg
from classes.appconf import MainConfig
from classes.hub import Hub
from classes.lgac485 import LGACPacketHandler
from classes.mqtt import MqttHandler
from classes.utils import Color, setup_logging
from consts import DEVICE_AIRCON, SW_VERSION_STRING


async def heartbeat():
    """Touch /tmp/healthy every 30s to signal liveness to Docker."""
    while True:
        try:
            pathlib.Path('/tmp/healthy').touch()
        except Exception:
            pass
        await asyncio.sleep(30)

async def main():
    loop = asyncio.get_running_loop()
    root_dir = pathlib.Path.cwd()
    
    # 로그 설정 (1차)
    setup_logging(cfg.CONF_LOGLEVEL)
    logger = logging.getLogger("main")

    logger.info(f"Starting...{SW_VERSION_STRING}")

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
    # Validate Final Configuration
    if not app_config.validate():
        logger.error("Configuration is invalid! Missing Critical Fields.")
        sys.exit(1)
    # Re-setup logging with configured level
    setup_logging(app_config.log_level)

    # 핸들러 초기화
    aircon = LGACPacketHandler(app_config, loop)
    # Pass loop to MqttHandler for scheduling callbacks safely
    mqtt = MqttHandler(app_config, loop)

    def close_all_devices_sockets():
        aircon.sync_close_socket(loop)

    def prepare_reconnect():
        # Critical Error -> Exit to let Supervisor restart us
        logger.error("Critical Connection Failure. Exiting for restart...")
        mqtt.set_ignore_handling()
        close_all_devices_sockets()
        mqtt.cleanup()
        sys.exit(1)

    logger.info(
        f"{cfg.CONF_AIRCON_DEVICE_NAME} Configuration: "
        f"[{app_config.aircon_server}:{app_config.aircon_port}]"
    )

    # 콜백 연결
    aircon.set_notify_function(mqtt.change_aircon_status)
    aircon.set_availability_function(mqtt.publish_availability)
    mqtt.set_aircon_mqtt_handler(aircon.handle_aircon_mqtt_message)
    mqtt.set_reconnect_action(prepare_reconnect)

    # 허브 생성
    hub = Hub(aircon, mqtt)
    hub.add_devices([DEVICE_AIRCON])

    # HA Discovery용 리스트 설정
    enabled_list = []
    enabled_list.extend(aircon.enabled_device_list)
    mqtt.set_enabled_list(enabled_list)

    logger.debug("Now entering main loop!")

    try:
        mqtt.connect_mqtt()
        # 연결 대기 후 Discovery 수행
        await asyncio.sleep(1.0)
        await mqtt.homeassistant_device_discovery(initial=True)
    except Exception as e:
        logger.critical(f"Error connecting MQTT Server: {e}")
        sys.exit(1)

    # 메인 태스크 실행
    tasks = [
        asyncio.create_task(aircon.async_lgac_main_write_loop()),
        asyncio.create_task(hub.async_scan_thread()),
        asyncio.create_task(aircon.async_scan_all_devices()),
        asyncio.create_task(heartbeat()) # Add Heartbeat
    ]
    
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.warning("Tasks Cancelled.")
    except Exception as e:
        logger.error(f"Critical Error in Main Loop: {e}")
        sys.exit(1)

    logger.info("End of Program Session.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nUser Stopped Program.")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)
