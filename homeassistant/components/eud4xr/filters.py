from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .hass_utils import get_entity_instance_by_entity_id, find_sensor


async def get_real_smart_entities(hass: HomeAssistant, suffix: str = "_real", names: list = None, only_objects: bool = False) -> dict:
    entity_registry = er.async_get(hass)
    entities = []
    all_services = hass.services.async_services()

    for entity in entity_registry.entities.values():
        value = None
        if entity.unique_id and entity.unique_id.endswith(suffix):
            state = hass.states.get(entity.entity_id)
            friendly_name = state.attributes.get("friendly_name") if state else None
            if only_objects:
                value = friendly_name
            else:
                domain = entity.domain
                domain_services = all_services.get(domain, {})
                services_list = [f"{domain}.{service}" for service in domain_services]
                value = {
                    'entity_id': entity.entity_id,
                    'unique_id': entity.unique_id,
                    'name': friendly_name,
                    'domain': domain,
                    'services': services_list
                }

            if not names or friendly_name in names:
                entities.append(value)

    return {"real_objects": entities}


async def get_virtual_entities(hass: HomeAssistant, names: list = None, only_objects: bool = False) -> dict:
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

            components = list()
            for i in state.attributes["entity_id"]:
                sensor, entity = find_sensor(hass, i)
                components.append({
                    "sensor name": i,
                    **sensor.to_dict(hass)
                })

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
                new_group["components"] = components

            objects_all.append(new_group)
            if not names or new_group["name"].lower() in names:
                objects.append(new_group)

    return {"virtual_objects": objects if objects else objects_all}

