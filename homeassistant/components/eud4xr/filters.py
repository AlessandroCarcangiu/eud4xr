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
    return {
        "entity_id": entity_id,
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
    devices_data = dict()
    service_map = hass.services.async_services()

    # retrieve labelled devices
    devices = [
        d
        for d in dr.async_get(hass).devices.values()
        if d.name_by_user and suffix in d.name_by_user
    ]

    # for each device, get its info (properties, entities, ecc.)
    for device in devices:
        device_name = device.name or device.name_by_user
        device_data = {
            "device_id": device.id,
            "name": device_name,
            #"manufacturer": device.manufacturer,
            #"model": device.model,
            # aggiungere description
        }
        entities = get_entities_for_device(hass, device.id)
        device_data["entities"] = [
            get_entity_data(hass, service_map, e) for e in entities
        ]
        devices_data[device_name] = device_data

    entities2 = {
        "NetAtmo": {
            "description": " Questo dispositivo è un sensore che rileva vari dati ambientali. Le sue entità sono: - binary_sensor.netatmoeud4xr_connectivity: rileva se il dispositivo è connesso o meno. - sensor.netatmoeud4xr_temperature: misura la temperatura in °C. - sensor.netatmoeud4xr_carbon_dioxide: misura il livello di CO₂ in ppm. - sensor.netatmoeud4xr_atmospheric_pressure: misura la pressione atmosferica in hPa. - sensor.netatmoeud4xr_noise: misura il rumore in dB. - sensor.netatmoeud4xr_humidity: misura l'umidità in %.- sensor.netatmoeud4xr_health_index: indica la qualità dell’aria con valori come 'healthy', 'fine', 'fair', 'poor', 'unhealthy'.",
            "entity_id": "binary_sensor.netatmoeud4xr_connectivity",
            "state": "off",
            "attributes": {
                "latitude": 43.719089,
                "longitude": 10.4206967,
                "attribution": "Data provided by Netatmo",
                "device_class": "connectivity",
                "friendly_name": "NetatmoEUD4XR Connectivity",
            },
            "last_changed": "2025-07-11T15:26:29.958730+00:00",
            "last_reported": "2025-07-14T09:43:11.518832+00:00",
            "last_updated": "2025-07-11T15:26:29.958730+00:00",
            "context": {
                "id": "01JZX1GQ26Y7YQ637GFCRSMZ3Q",
                "parent_id": None,
                "user_id": None,
            },
            "entity_id": "sensor.netatmoeud4xr_temperature",
            "state": "unavailable",
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "°C",
                "attribution": "Data provided by Netatmo",
                "device_class": "temperature",
                "friendly_name": "NetatmoEUD4XR Temperature",
            },
            "last_changed": "2025-07-11T15:26:29.959536+00:00",
            "last_reported": "2025-07-14T09:43:11.519354+00:00",
            "last_updated": "2025-07-11T15:26:29.959536+00:00",
            "context": {
                "id": "01JZX1GQ27CTFTQ475SNJ90TSC",
                "parent_id": None,
                "user_id": None,
            },
            "entity_id": "sensor.netatmoeud4xr_carbon_dioxide",
            "state": "unavailable",
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "ppm",
                "attribution": "Data provided by Netatmo",
                "device_class": "carbon_dioxide",
                "friendly_name": "NetatmoEUD4XR Carbon dioxide",
            },
            "last_changed": "2025-07-11T15:26:29.959813+00:00",
            "last_reported": "2025-07-14T09:43:11.519624+00:00",
            "last_updated": "2025-07-11T15:26:29.959813+00:00",
            "context": {
                "id": "01JZX1GQ272CEWY6WRAZJM5Q7Y",
                "parent_id": None,
                "user_id": None,
            },
            "entity_id": "sensor.netatmoeud4xr_atmospheric_pressure",
            "state": "unavailable",
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "hPa",
                "attribution": "Data provided by Netatmo",
                "device_class": "atmospheric_pressure",
                "friendly_name": "NetatmoEUD4XR Atmospheric pressure",
            },
            "last_changed": "2025-07-11T15:26:29.960043+00:00",
            "last_reported": "2025-07-14T09:43:11.519881+00:00",
            "last_updated": "2025-07-11T15:26:29.960043+00:00",
            "context": {
                "id": "01JZX1GQ28CWEVX4WQ56R8XHB8",
                "parent_id": None,
                "user_id": None,
            },
            "entity_id": "sensor.netatmoeud4xr_noise",
            "state": "unavailable",
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "dB",
                "attribution": "Data provided by Netatmo",
                "device_class": "sound_pressure",
                "friendly_name": "NetatmoEUD4XR Noise",
            },
            "last_changed": "2025-07-11T15:26:29.960278+00:00",
            "last_reported": "2025-07-14T09:43:11.520133+00:00",
            "last_updated": "2025-07-11T15:26:29.960278+00:00",
            "context": {
                "id": "01JZX1GQ28VBE4PYG547ZFMQ0P",
                "parent_id": None,
                "user_id": None,
            },
            "entity_id": "sensor.netatmoeud4xr_humidity",
            "state": "unavailable",
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "%",
                "attribution": "Data provided by Netatmo",
                "device_class": "humidity",
                "friendly_name": "NetatmoEUD4XR Humidity",
            },
            "last_changed": "2025-07-11T15:26:29.960442+00:00",
            "last_reported": "2025-07-14T09:43:11.520382+00:00",
            "last_updated": "2025-07-11T15:26:29.960442+00:00",
            "context": {
                "id": "01JZX1GQ28E5EYFXHFVMB5KEBQ",
                "parent_id": None,
                "user_id": None,
            },
            "entity_id": "sensor.netatmoeud4xr_health_index",
            "state": "unavailable",
            "attributes": {
                "options": ["healthy", "fine", "fair", "poor", "unhealthy"],
                "attribution": "Data provided by Netatmo",
                "device_class": "enum",
                "friendly_name": "NetatmoEUD4XR Health index",
            },
            "last_changed": "2025-07-11T15:26:29.960726+00:00",
            "last_reported": "2025-07-14T09:43:11.520639+00:00",
            "last_updated": "2025-07-11T15:26:29.960726+00:00",
            "context": {
                "id": "01JZX1GQ284TSYYPPG8WK1GM41",
                "parent_id": None,
                "user_id": None,
            },
        },
        "Xiaomi": {
            "description": "Questo dispositivo purifica l'aria e può essere controllato da remoto. Le sue funzionalità principali sono: - Accensione e spegnimento del purificatore. - Impostazione di una modalità predefinita tra: Auto, Sleep, Favorite.- Impostazione della velocità della ventola in percentuale (da 0 a 100%).",
            "entity_id": "fan.xiaomi_cpa4_e35d_air_purifier",
            "state": "unavailable",
            "attributes": {
                "preset_modes": ["Auto", "Sleep", "Favorite"],
                "friendly_name": "Xiaomi Smart Air Purifier 4 Compact Air Purifier",
                "supported_features": 57,
            },
            "last_changed": "2025-07-11T15:26:54.303589+00:00",
            "last_reported": "2025-07-11T15:26:54.303589+00:00",
            "last_updated": "2025-07-11T15:26:54.303589+00:00",
            "context": {
                "id": "01JZX1HETZVD8AD4WZEXYVTC2D",
                "parent_id": None,
                "user_id": None,
            },
            "components": {
                "domain": "fan",
                "services": {
                    "turn_on": {
                        "name": "Turn on",
                        "description": "Turns fan on.",
                        "fields": {
                            "percentage": {
                                "filter": {"supported_features": [1]},
                                "selector": {
                                    "number": {
                                        "min": 0,
                                        "max": 100,
                                        "unit_of_measurement": "%",
                                    }
                                },
                                "name": "Percentage",
                                "description": "Speed of the fan.",
                            },
                            "preset_mode": {
                                "example": "auto",
                                "filter": {"supported_features": [8]},
                                "selector": {"text": None},
                                "name": "Preset mode",
                                "description": "Preset fan mode.",
                            },
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [32]}]
                        },
                    },
                    "turn_off": {
                        "name": "Turn off",
                        "description": "Turns fan off.",
                        "fields": {},
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [16]}]
                        },
                    },
                    "toggle": {
                        "name": "Toggle",
                        "description": "Toggles a fan on/off.",
                        "fields": {},
                        "target": {"entity": [{"domain": ["fan"]}]},
                    },
                    "increase_speed": {
                        "name": "Increase speed",
                        "description": "Increases the speed of a fan.",
                        "fields": {
                            "percentage_step": {
                                "advanced": True,
                                "required": False,
                                "selector": {
                                    "number": {
                                        "min": 0,
                                        "max": 100,
                                        "unit_of_measurement": "%",
                                    }
                                },
                                "name": "Increment",
                                "description": "Percentage step by which the speed should be increased.",
                            }
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [1]}]
                        },
                    },
                    "decrease_speed": {
                        "name": "Decrease speed",
                        "description": "Decreases the speed of a fan.",
                        "fields": {
                            "percentage_step": {
                                "advanced": True,
                                "required": False,
                                "selector": {
                                    "number": {
                                        "min": 0,
                                        "max": 100,
                                        "unit_of_measurement": "%",
                                    }
                                },
                                "name": "Decrement",
                                "description": "Percentage step by which the speed should be decreased.",
                            }
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [1]}]
                        },
                    },
                    "oscillate": {
                        "name": "Oscillate",
                        "description": "Controls the oscillation of a fan.",
                        "fields": {
                            "oscillating": {
                                "required": True,
                                "selector": {"boolean": None},
                                "name": "Oscillating",
                                "description": "Turns oscillation on/off.",
                            }
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [2]}]
                        },
                    },
                    "set_direction": {
                        "name": "Set direction",
                        "description": "Sets a fan's rotation direction.",
                        "fields": {
                            "direction": {
                                "required": True,
                                "selector": {
                                    "select": {
                                        "options": ["forward", "reverse"],
                                        "translation_key": "direction",
                                    }
                                },
                                "name": "Direction",
                                "description": "Direction of the fan rotation.",
                            }
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [4]}]
                        },
                    },
                    "set_percentage": {
                        "name": "Set speed",
                        "description": "Sets the speed of a fan.",
                        "fields": {
                            "percentage": {
                                "required": True,
                                "selector": {
                                    "number": {
                                        "min": 0,
                                        "max": 100,
                                        "unit_of_measurement": "%",
                                    }
                                },
                                "name": "Percentage",
                                "description": "Speed of the fan.",
                            }
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [1]}]
                        },
                    },
                    "set_preset_mode": {
                        "name": "Set preset mode",
                        "description": "Sets preset fan mode.",
                        "fields": {
                            "preset_mode": {
                                "required": True,
                                "example": "auto",
                                "selector": {"text": None},
                                "name": "Preset mode",
                                "description": "Preset fan mode.",
                            }
                        },
                        "target": {
                            "entity": [{"domain": ["fan"], "supported_features": [8]}]
                        },
                    },
                },
            },
        },
    }

    return {"real_objects": devices_data}


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
        registry = er.async_get(hass)

        for state in registered_groups:
            new_group = dict()
            new_group["name"] = state.entity_id.split(".")[-1]
            new_group["components"] = list()
            new_group["services"] = list()
            new_group["properties"] = list()

            # components = list()
            for i in state.attributes["entity_id"]:
                sensor, entity = find_sensor(hass, i)
                # components.append({
                #     "sensor name": i,
                #     **sensor.to_dict(hass)
                # })
                # new_group["components"] = components

                new_group["components"] += [sensor.game_object]
                new_group["properties"] += sensor.get_properties()
                new_group["services"] += sensor.get_services()

                # c = hass.states.get(i)
                # if c:
                #     # get properties and services
                #     print(f"sensor: {type(sensor)}\n{sensor.to_dict(hass)}")

                #     component_state = c.as_dict().copy()
                #     # drop unuseful keys
                #     for k in [
                #         "last_changed",
                #         "last_reported",
                #         "last_updated",
                #         "context",
                #     ]:
                #         if k in component_state:
                #             component_state.pop(k)
                #     # add class name
                #     component_entity = get_entity_instance_by_entity_id(
                #         hass, i
                #     )
                #     component_state["class"] = component_entity.eca_script
                #     components.append(component_state)

            objects_all.append(new_group)
            if not names or new_group["name"].lower() in names:
                objects.append(new_group)

    return {"virtual_objects": objects if objects else objects_all}
