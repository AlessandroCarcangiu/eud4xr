# ruff: noqa

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr
from .const import CONF_UNUSEFUL_KEYS
from .hass_utils import get_entity_instance_by_entity_id, find_sensor


def get_entities_for_device(hass: HomeAssistant, device_id: str) -> list:
    entity_registry = er.async_get(hass)
    return [
        entry
        for entry in entity_registry.entities.values()
        if entry.device_id == device_id
    ]

def get_entity_attributes_by_state(state: any) -> dict:
    attributes = dict()
    if state:
        attributes = state.attributes.copy()
        # remove unuseful data
        for k in CONF_UNUSEFUL_KEYS:
            if k in attributes:
                attributes.pop(k)
    return attributes


def get_entity_data(hass: HomeAssistant, service_map: list, entity: any) -> dict:
	entity_id = entity.entity_id
	state = hass.states.get(entity_id)
	domain = entity_id.split(".")[0]
	services = list(service_map.get(domain, {}).keys())
	entity_id_value = None
	if "netatmo" not in entity_id:
		entity_id_value = entity_id
	elif services:
		entity_id = services.pop("device_class")
	return {
		"entity_id": entity_id_value,
		#"domain": domain,
		"state": state.state if state else None,
		"attributes": get_entity_attributes_by_state(state),
		"services": services,
	}


async def get_devices_data(
    hass: HomeAssistant,
    suffix: str = "_real",
    names: list = None,
    only_objects: bool = False,
) -> dict:
    # devices_data = dict()
    # service_map = hass.services.async_services()
    # # retrieve labelled devices
    # devices = [
    #     d
    #     for d in dr.async_get(hass).devices.values()
    #     if d.name_by_user and suffix in d.name_by_user
    # ]
    # # for each device, get its info (properties, entities, ecc.)
    # for device in devices:
    #     device_name = device.name or device.name_by_user
    #     device_data = {
    #         "device_id": device.id,
    #         "name": device_name,
    #         #"manufacturer": device.manufacturer,
    #         #"model": device.model,
    #         # aggiungere description
    #     }
    #     entities = get_entities_for_device(hass, device.id)
    #     device_data["entities"] = [
    #         get_entity_data(hass, service_map, e) for e in entities
    #     ]
    #     devices_data[device_name] = device_data

    # return {"real_objects": devices_data}
    return {
        "real_objects": {"NetatmoEUD4XR": {
			"device_id": "815b818f3d8801826c8108175bbce5b4",
			"name": "NetatmoEUD4XR",
			"entities": [
				{
					"entity_id": "binary_sensor.netatmoeud4xr_connectivity",
					"state": "off",
					"attributes": {
						"latitude": 43.719089,
						"longitude": 10.4206967,
						"device_class": "connectivity",
						"friendly_name": "NetatmoEUD4XR_real Connectivity"
					},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_temperature",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "°C",
						"device_class": "temperature",
						"friendly_name": "NetatmoEUD4XR_real Temperature"
					},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_temperature_trend",
					"state": None,
					"attributes": {},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_carbon_dioxide",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "ppm",
						"device_class": "carbon_dioxide",
						"friendly_name": "NetatmoEUD4XR_real Carbon dioxide"
					},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_atmospheric_pressure",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "hPa",
						"device_class": "atmospheric_pressure",
						"friendly_name": "NetatmoEUD4XR_real Atmospheric pressure"
					},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_pressure_trend",
					"state": None,
					"attributes": {},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_noise",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "dB",
						"device_class": "sound_pressure",
						"friendly_name": "NetatmoEUD4XR_real Noise"
					},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_humidity",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "%",
						"device_class": "humidity",
						"friendly_name": "NetatmoEUD4XR_real Humidity"
					},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_reachability",
					"state": None,
					"attributes": {},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_wi_fi",
					"state": None,
					"attributes": {},
					"services": []
				},
				{
					"entity_id": "sensor.netatmoeud4xr_health_index",
					"state": "unavailable",
					"attributes": {
						"options": [
							"healthy",
							"fine",
							"fair",
							"poor",
							"unhealthy"
						],
						"device_class": "enum",
						"friendly_name": "NetatmoEUD4XR_real Health index"
					},
					"services": []
				}
			]
		},
		"shellydw2-402822": {
			"device_id": "e368bbc2fb5b12814c839319395584e6",
			"name": "shellydw2-402822",
			"entities": [
				{
					"entity_id": "binary_sensor.shellydw2_402822_door",
					"state": "unavailable",
					"attributes": {
						"device_class": "opening",
						"friendly_name": "shellydw2_real door"
					},
					"services": []
				},
				{
					"entity_id": "binary_sensor.shellydw2_402822_vibration",
					"state": "unavailable",
					"attributes": {
						"device_class": "vibration",
						"friendly_name": "shellydw2_real vibration"
					},
					"services": []
				},
				{
					"entity_id": "sensor.shellydw2_402822_tilt",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "°",
						"friendly_name": "shellydw2_real tilt"
					},
					"services": []
				},
				{
					"entity_id": "sensor.shellydw2_402822_luminosity",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "lx",
						"device_class": "illuminance",
						"friendly_name": "shellydw2_real luminosity"
					},
					"services": []
				},
				{
					"entity_id": "sensor.shellydw2_402822_temperature",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "°C",
						"device_class": "temperature",
						"friendly_name": "shellydw2_real temperature"
					},
					"services": []
				},
				{
					"entity_id": "sensor.shellydw2_402822_battery",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"unit_of_measurement": "%",
						"device_class": "battery",
						"friendly_name": "shellydw2_real battery"
					},
					"services": []
				}
			]
		},
		"Xiaomi Smart Air Purifier 4 Compact": {
			"device_id": "bf9ff76aff20e046b358eedd371ad5ba",
			"name": "Xiaomi Smart Air Purifier 4 Compact",
			"entities": [
				{
					"entity_id": "sensor.xiaomi_cpa4_e35d_filter_life_level",
					"state": "unavailable",
					"attributes": {
						"icon": "mdi:percent",
						"friendly_name": "Filter Life Level",
						"unit_of_measurement": "%"
					},
					"services": []
				},
				{
					"entity_id": "sensor.xiaomi_cpa4_e35d_filter_left_time",
					"state": "unavailable",
					"attributes": {
						"friendly_name": "Filter Left Time",
						"unit_of_measurement": "days"
					},
					"services": []
				},
				{
					"entity_id": "sensor.xiaomi_cpa4_e35d_filter_used_time",
					"state": "unavailable",
					"attributes": {
						"icon": "mdi:clock",
						"friendly_name": "Filter Used Time",
						"unit_of_measurement": "hours"
					},
					"services": []
				},
				{
					"entity_id": "sensor.xiaomi_cpa4_e35d_pm25_density",
					"state": "unavailable",
					"attributes": {
						"state_class": "measurement",
						"device_class": "pm25",
						"icon": "mdi:air-filter",
						"friendly_name": "PM2.5",
						"unit_of_measurement": "µg/m³"
					},
					"services": []
				},
				{
					"entity_id": "switch.xiaomi_cpa4_e35d_alarm",
					"state": "unavailable",
					"attributes": {
						"friendly_name": "Alarm"
					},
					"services": [
						"turn_off",
						"turn_on",
						"toggle"
					]
				},
				{
					"entity_id": "switch.xiaomi_cpa4_e35d_physical_control_locked",
					"state": "unavailable",
					"attributes": {
						"friendly_name": "Physical Control Locked"
					},
					"services": [
						"turn_off",
						"turn_on",
						"toggle"
					]
				},
				{
					"entity_id": "number.xiaomi_cpa4_e35d_favorite_level",
					"state": "unavailable",
					"attributes": {
						"min": 0,
						"max": 14,
						"step": 1,
						"mode": "auto",
						"friendly_name": "custom-service favorite_level"
					},
					"services": [
						"set_value"
					]
				},
				{
					"entity_id": "select.xiaomi_cpa4_e35d_brightness",
					"state": "unavailable",
					"attributes": {
						"options": [
							"Close",
							"Bright",
							"Brightness"
						],
						"friendly_name": "Screen brightness"
					},
					"services": [
						"select_first",
						"select_last",
						"select_next",
						"select_option",
						"select_previous"
					]
				},
				{
					"entity_id": "select.xiaomi_cpa4_e35d_aqi_updata_heartbeat",
					"state": "unavailable",
					"attributes": {
						"options": [
							"0",
							"1",
							"2",
							"3",
							"4",
							"5",
							"6",
							"7",
							"8",
							"9",
							"10",
							"11",
							"12",
							"13",
							"14",
							"15",
							"16",
							"17",
							"18",
							"19",
							"20",
							"21",
							"22",
							"23",
							"24",
							"25",
							"26",
							"27",
							"28",
							"29",
							"30",
							"31",
							"32",
							"33",
							"34",
							"35",
							"36",
							"37",
							"38",
							"39",
							"40",
							"41",
							"42",
							"43",
							"44",
							"45",
							"46",
							"47",
							"48",
							"49",
							"50",
							"51",
							"52",
							"53",
							"54",
							"55",
							"56",
							"57",
							"58",
							"59",
							"60",
							"61",
							"62",
							"63",
							"64",
							"65",
							"66",
							"67",
							"68",
							"69",
							"70",
							"71",
							"72",
							"73",
							"74",
							"75",
							"76",
							"77",
							"78",
							"79",
							"80",
							"81",
							"82",
							"83",
							"84",
							"85",
							"86",
							"87",
							"88",
							"89",
							"90",
							"91",
							"92",
							"93",
							"94",
							"95",
							"96",
							"97",
							"98",
							"99",
							"100",
							"101",
							"102",
							"103",
							"104",
							"105",
							"106",
							"107",
							"108",
							"109",
							"110",
							"111",
							"112",
							"113",
							"114",
							"115",
							"116",
							"117",
							"118",
							"119",
							"120",
							"121",
							"122",
							"123",
							"124",
							"125",
							"126",
							"127",
							"128",
							"129",
							"130",
							"131",
							"132",
							"133",
							"134",
							"135",
							"136",
							"137",
							"138",
							"139",
							"140",
							"141",
							"142",
							"143",
							"144",
							"145",
							"146",
							"147",
							"148",
							"149",
							"150",
							"151",
							"152",
							"153",
							"154",
							"155",
							"156",
							"157",
							"158",
							"159",
							"160",
							"161",
							"162",
							"163",
							"164",
							"165",
							"166",
							"167",
							"168",
							"169",
							"170",
							"171",
							"172",
							"173",
							"174",
							"175",
							"176",
							"177",
							"178",
							"179",
							"180",
							"181",
							"182",
							"183",
							"184",
							"185",
							"186",
							"187",
							"188",
							"189",
							"190",
							"191",
							"192",
							"193",
							"194",
							"195",
							"196",
							"197",
							"198",
							"199",
							"65535"
						],
						"friendly_name": "aqi aqi_updata_heartbeat"
					},
					"services": [
						"select_first",
						"select_last",
						"select_next",
						"select_option",
						"select_previous"
					]
				},
				{
					"entity_id": "button.xiaomi_cpa4_e35d_info",
					"state": "unavailable",
					"attributes": {
						"device_class": "update",
						"icon": "mdi:information",
						"friendly_name": "Info"
					},
					"services": [
						"press"
					]
				},
				{
					"entity_id": "button.xiaomi_cpa4_e35d_toggle",
					"state": "unavailable",
					"attributes": {
						"friendly_name": "Toggle"
					},
					"services": [
						"press"
					]
				},
				{
					"entity_id": "button.xiaomi_cpa4_e35d_reset_filter_life",
					"state": "unavailable",
					"attributes": {
						"friendly_name": "Reset Filter Life"
					},
					"services": [
						"press"
					]
				},
				{
					"entity_id": "fan.xiaomi_cpa4_e35d_air_purifier",
					"state": "unavailable",
					"attributes": {
						"preset_modes": [
							"Auto",
							"Sleep",
							"Favorite"
						],
						"friendly_name": "Air Purifier"
					},
					"services": [
						"turn_on",
						"turn_off",
						"toggle",
						"increase_speed",
						"decrease_speed",
						"oscillate",
						"set_direction",
						"set_percentage",
						"set_preset_mode"
					]
				}
			]
		}
    }}


async def get_virtual_entities(
    hass: HomeAssistant, names: list = None, only_objects: bool = False
) -> dict:
    objects = list()
    objects_all = list()
    registered_groups = filter(
        lambda state: state.entity_id.startswith("group."),
        hass.states.async_all(),
    )

    if only_objects:
        objects = [state.entity_id.split(".")[-1] for state in registered_groups]
    else:
        # names
        names = [n.lower() for n in names] if names else []

        for state in registered_groups:
            new_group = dict()
            new_group["name"] = state.entity_id.split(".")[-1]
            new_group["components"] = list()
            new_group["description"] = dict()
            new_group["services"] = list()
            new_group["properties"] = list()

            for i in state.attributes["entity_id"]:
                sensor, entity = find_sensor(hass, i)
                new_group["components"] += [sensor.eca_script]
                new_group["description"][sensor.eca_script] = sensor.get_description()
                new_group["properties"] += sensor.get_properties()
                new_group["services"] += sensor.get_services()

            objects_all.append(new_group)
            if not names or new_group["name"].lower() in names:
                objects.append(new_group)
    return {"virtual_objects": objects if objects else objects_all}
