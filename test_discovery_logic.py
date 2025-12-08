
# Mock config
class Cfg:
    HA_PREFIX = "homeassistant"
    CONF_AIRCON_DEVICE_NAME = "LGAircon"
    HA_CLIMATE = "climate"

cfg = Cfg()
DEVICE_AIRCON = "aircon"
MQTT_ICON_AIRCON = "mdi:air-conditioner"
SW_VERSION_STRING = "v0.86"

# Mock Mqtt Discovery logic
def make_topic_and_payload_for_discovery(kind, room, device, icon_name):
    common_topic_str = f'{cfg.HA_PREFIX}/{kind}/{room}'
    topic = f'{common_topic_str}_{device}/config'

    # ... logic from mqtt.py ...
    aircon_common_id_str = f'{cfg.CONF_AIRCON_DEVICE_NAME}_{room}_{device}'
    payload = {}
    payload['name'] = aircon_common_id_str
    payload['uniq_id'] = aircon_common_id_str
    
    return topic, payload

# Mock AppConf logic
aircons = "livingroom:bedroom"
aircon_list = aircons.split(':')
aircon_dict = {f'{num:02x}': name for num, name in enumerate(aircon_list)}

print("Room Dict:", aircon_dict)

for room in aircon_dict.values():
    t, p = make_topic_and_payload_for_discovery("climate", room, "aircon", "mdi:foo")
    print(f"Room: {room}")
    print(f"Topic: {t}")
    print(f"Unique ID: {p['uniq_id']}")
    print("-" * 20)
