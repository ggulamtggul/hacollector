import asyncio
import logging
import pathlib
import sys

from dotenv import load_dotenv
from aiohttp import web

import config as cfg
from classes.appconf import MainConfig
from classes.hub import Hub
from classes.lgac485 import LGACPacketHandler
from classes.mqtt import MqttHandler
from classes.utils import Color, setup_logging, in_memory_log_handler
from classes.aircon import Aircon
from consts import DEVICE_AIRCON, SW_VERSION_STRING


@web.middleware
async def ingress_middleware(request, handler):
    path = request.path
    if '/api/hassio_ingress/' in path:
        parts = path.split('/')
        if len(parts) > 4:
            new_path = '/' + '/'.join(parts[4:])
        else:
            new_path = '/'
        if request.query_string:
            new_path = f"{new_path}?{request.query_string}"
        
        cloned_request = request.clone(rel_url=new_path)
        return await handler(cloned_request)
    return await handler(request)


async def init_web_server(port, app_config, aircon, mqtt):
    logger = logging.getLogger("web")
    
    async def handle_index(request):
        html_path = pathlib.Path(__file__).parent / 'web' / 'index.html'
        if not html_path.exists():
            return web.Response(text="index.html not found", status=404)
        with open(html_path, 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')

    async def handle_js(request):
        js_path = pathlib.Path(__file__).parent / 'web' / 'main.js'
        if not js_path.exists():
            return web.Response(text="main.js not found", status=404)
        with open(js_path, 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='application/javascript')

    async def handle_status_api(request):
        aircons_data = []
        for ac in aircon.aircon:
            aircons_data.append({
                'id': ac.id,
                'room_name': ac.room_name,
                'action': ac.action,
                'opmode': ac.opmode,
                'fanmove': ac.fanmove,
                'fanmode': ac.fanmode,
                'current_temp': ac.current_temp,
                'target_temp': ac.target_temp,
                'available': ac.last_availability_status
            })
        
        config_data = {
            'lg_server_ip': app_config.aircon_server,
            'lg_server_port': app_config.aircon_port,
            'mqtt_server': app_config.mqtt_server,
            'mqtt_port': app_config.mqtt_port,
            'min_temp': app_config.min_temp,
            'max_temp': app_config.max_temp,
            'scan_interval': app_config.scan_interval,
            'log_level': app_config.log_level
        }
        
        return web.json_response({
            'status': 'success',
            'version': SW_VERSION_STRING,
            'aircons': aircons_data,
            'config': config_data
        })

    async def handle_control_api(request):
        try:
            data = await request.json()
            room_name = data.get('room_name')
            ac = aircon.get_aircon(room_name)
            
            action = data.get('action', ac.action)
            opmode = data.get('opmode', ac.opmode)
            fanmove = data.get('fanmove', ac.fanmove)
            fanmode = data.get('fanmode', ac.fanmode)
            target_temp = int(data.get('target_temp', ac.target_temp))
            
            if target_temp < app_config.min_temp:
                target_temp = app_config.min_temp
            elif target_temp > app_config.max_temp:
                target_temp = app_config.max_temp

            ac.action = action
            ac.opmode = opmode
            ac.fanmove = fanmove
            ac.fanmode = fanmode
            ac.target_temp = target_temp
            
            aircon_cmd = Aircon.Info(action, opmode, fanmove, fanmode, 0.0, target_temp)
            aircon.command_queue.put_nowait((ac.id, room_name, aircon_cmd))
            
            logger.info(f"[WebUI Control] Queued command for {room_name}: {action}, {opmode}, {target_temp}C")
            return web.json_response({'status': 'success', 'message': 'Command queued successfully'})
        except Exception as e:
            logger.error(f"Error in control API: {e}")
            return web.json_response({'status': 'error', 'message': str(e)}, status=400)

    async def handle_logs_api(request):
        logs = in_memory_log_handler.get_logs()
        return web.json_response({
            'status': 'success',
            'logs': logs
        })

    app = web.Application(middlewares=[ingress_middleware])
    app.router.add_get('/', handle_index)
    app.router.add_get('/main.js', handle_js)
    app.router.add_get('/api/status', handle_status_api)
    app.router.add_post('/api/control', handle_control_api)
    app.router.add_get('/api/logs', handle_logs_api)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Ingress Web Dashboard server started on port {port}")
    
    # Keep running
    while True:
        await asyncio.sleep(3600)


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
        asyncio.create_task(heartbeat()), # Add Heartbeat
        asyncio.create_task(init_web_server(8099, app_config, aircon, mqtt)) # Ingress Web Server
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
