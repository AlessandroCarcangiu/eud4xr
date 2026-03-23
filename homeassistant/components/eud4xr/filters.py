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
    if only_objects:
        return [device.name if device.name and device.name.lower() != "unknown" else device.name_by_user for device in devices]
    else:
        # for each device, get its info (properties, entities, ecc.)
        for device in devices:
            device_name = device.name if device.name and device.name.lower() != "unknown" else device.name_by_user
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
        return objects
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
                if sensor:
                    new_group["components"] += [sensor.eca_script]
                    new_group["description"][sensor.eca_script] = sensor.get_description()
                    new_group["properties"] += sensor.get_properties()
                    new_group["services"] += sensor.get_services()
            objects_all.append(new_group)
            if not names or new_group["name"].lower() in names:
                 objects.append(new_group)
    return {"virtual_objects": objects if objects else objects_all}
