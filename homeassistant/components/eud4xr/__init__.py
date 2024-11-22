import logging
import aiohttp
import voluptuous as vol
from homeassistant.components.group import Group, expand_entity_ids
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from .automations import (
    RECEIVED_AUTOMATION_SCHEMA,
    REMOVE_AUTOMATION_SCHEMA,
    async_add_update_automation,
    async_remove_automation,
)
from .const import *
from .sensor import (
    GAMEOBJECT_ECASCRIPT_SCHEMA,
    SERVICE_UPDATE_FROM_UNITY,
    UPDATES_FROM_UNITY_SCHEMA,
)
from .views import ListAutomationsView, ListFramedVirtualDevicesView, ListECACapabilitiesView

_LOGGER = logging.getLogger(__name__)

group_locks = {}

SERVICE_SEND_REQUEST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_SUBJECT): cv.string,
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_VERB): cv.string,
        vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_VARIABLE): cv.string,
        vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_MODIFIER): cv.string,
        vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_PARAMETERS, default={}): dict,
    }
)

REGISTER_VIRTUAL_OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PAIRS, default=list()): vol.All(
            cv.ensure_list, [GAMEOBJECT_ECASCRIPT_SCHEMA]
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config[DOMAIN]
    server_unity_url = conf.get(CONF_SERVER_UNITY_URL)
    server_unity_token = conf.get(CONF_SERVER_UNITY_TOKEN)
    sensors = conf.get(CONF_UNITY_ENTITIES)

    # get data from configuration and create entities
    hass.data[DOMAIN] = {}
    if sensors:
        for game_object_config in sensors:
            hass.async_create_task(
                hass.helpers.discovery.async_load_platform(
                    "sensor", DOMAIN, game_object_config, config
                )
            )

    ## Send update to Unity
    async def handle_send_update_to_server_unity(call: ServiceCall) -> None:
        # # validate entity
        # ent_reg = entity_registry.async_get(hass)
        # entity = ent_reg.async_get(call.data[CONF_SUBJECT])
        # if not entity:
        #     _LOGGER.error("L'entit√† %s non √® valida", subject)
        #     return
        await send_update_to_server_unity(call.data)

    async def send_update_to_server_unity(payload: dict) -> None:
        # await refresh_token()
        headers = {}  # {"Authorization": f"Bearer {server_unity_token}"}
        # send request
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{server_unity_url}/api/external_updates/", json=payload
                ) as response:
                    if response.status == 200:
                        _LOGGER.info("Update successfully sent")
                    else:
                        _LOGGER.error(f"Error on updating Unity: {response.status}")
            except Exception as e:
                _LOGGER.error(f"Error on conctating Unity: {e}")

    async def refresh_token() -> None:
        nonlocal server_unity_token
        headers = {"Authorization": f"Bearer {server_unity_token}"}
        response_verify = None  # requests.post(f"{server_unity_url}/auth/token/verify", headers=headers)
        # if response_verify and response_verify.status_code != 200:
        # response_refresh = requests.post(
        #     f"{server_unity_url}/auth/token/refresh", headers=headers
        # )
        # if response_refresh.status_code == 200:
        #     token = response_refresh.json().get("refreshed_token")
        #     _LOGGER.info("Token successfully updated")
        # else:
        #     _LOGGER.error("Erronr on refreshing the token")

    ## Register eca sensor
    async def handle_add_virtual_object(call):
        virtual_object_data = call.data.get(CONF_PAIRS)
        _LOGGER.info(f"Received a new entry: {virtual_object_data}")
        await async_add_virtual_object(hass, virtual_object_data)

    async def async_add_virtual_object(hass, data: list):
        new_sensors = list()
        entity_name = None
        group_name = None
        # create new sensor for each pair game_object-eca_script
        for d in data:
            # if "attributes" in new_sensor_data and new_sensor_data.get("attributes"):
            #     new_sensor_data.pop("attributes")
            discovery.load_platform(hass, "sensor", DOMAIN, d.copy(), {})
            new_entity_name = d.get(GAME_OBJECT_NAME).lower()
            new_sensors.append(f"sensor.{new_entity_name.replace('@', '_')}")
            if entity_name is None:
                entity_name = new_entity_name.replace("@", "_")
                group_name = new_entity_name.split("@")[0]

        # create or update group: check if exists a group for this pair game_object_name@name_component
        # No -> create a new Group
        # Yes -> update group's list of entities
        if entity_name:
            group_state = find_group(hass, group_name)
            if not group_state:
                new_group = Group(
                    hass=hass,
                    name=group_name,
                    entity_ids=new_sensors,
                    created_by_service=None,
                    icon=None,
                    mode=None,
                    order=None,
                )
                component = EntityComponent(hass, "group", hass)
                await component.async_add_entities([new_group])
            else:
                current_entities = group_state.attributes.get("entity_id", [])
                new_sensors_to_append = [
                    s for s in new_sensors if s not in current_entities
                ]

                @callback
                def async_update_group():
                    hass.states.async_set(
                        group_state.entity_id,
                        "on",
                        {
                            "entity_id": list(current_entities) + new_sensors_to_append,
                            "friendly_name": group_name,
                        },
                    )
                await hass.add_job(async_update_group)
        _LOGGER.info("Registered a new object")

    ## Update from Unity
    async def handle_update_from_unity(call) -> None:
        await async_update_from_unity(hass, call.data)

    async def async_update_from_unity(hass, update):
        _LOGGER.info(f"Received a new update from unity: {update}")
        # update state #
        data = update.get(CONF_SERVICE_UPDATE_FROM_UNITY_UPDATE)
        group_id = data.pop("unity_id").split("@")[0]
        group = find_group(hass, group_id)
        if group:
            sensors_ids = group.attributes.get("entity_id", [])
            attribute = data.get("attribute")
            for sensor_id in sensors_ids:
                sensor, entity = find_sensor(hass, sensor_id)
                if sensor and entity:
                    # on action #
                    if CONF_SERVICE_UPDATE_FROM_UNITY_ATTRIBUTE not in data:
                        sensor.on_action(**data)
                        return
                    # update a sensor's attribute
                    attributes = dict(entity.attributes)
                    if attribute and attribute in attributes:
                        if (
                            attribute not in sensor.last_updates
                            or sensor.last_updates[attribute]
                            < update[CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP]
                        ):
                            new_value = data.get("new_value")
                            attributes[attribute] = new_value
                            hass.states.async_set(sensor_id, entity.state, attributes)
                            sensor.last_updates[attribute] = update[
                                CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP
                            ]
                            _LOGGER.info(
                                f"Attribute {attribute} of Entity {sensor} updated!"
                            )
                        else:
                            _LOGGER.warning(
                                f"Received an old {update} for the Entity {sensor} - {sensor.last_updates[attribute]}"
                            )
                        return
        _LOGGER.error(
            f"Received a new update from unity - Error on handling update {update} - group: {group}"
        )

    ## Add or update an automation
    async def handle_add_update_automation(call) -> None:
        data = call.data[CONF_SERVICE_ADD_UPDATE_AUTOMATION_DATA]
        await async_add_update_automation(hass, data)

    ## Remove an automation
    async def handle_remove_automation(call) -> None:
        automation_id = call.data[CONF_SERVICE_REMOVE_AUTOMATION_ID]
        await async_remove_automation(hass, automation_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_REQUEST,
        handle_send_update_to_server_unity,
        schema=SERVICE_SEND_REQUEST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_VIRTUAL_OBJECT,
        handle_add_virtual_object,
        schema=REGISTER_VIRTUAL_OBJECT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_FROM_UNITY,
        handle_update_from_unity,
        schema=UPDATES_FROM_UNITY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_UPDATE_AUTOMATION,
        handle_add_update_automation,
        schema=RECEIVED_AUTOMATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_AUTOMATION,
        handle_remove_automation,
        schema=REMOVE_AUTOMATION_SCHEMA,
    )

    # views
    hass.http.register_view(ListAutomationsView(hass))
    hass.http.register_view(ListFramedVirtualDevicesView(hass))
    hass.http.register_view(ListECACapabilitiesView(hass))
    return True


def find_group(hass, group_id: str):
    return hass.states.get(f"group.{group_id}")


def find_sensor(hass, sensor_id: str):
    entity = hass.states.get(sensor_id)
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(sensor_id)
    sensor_component = hass.data.get("sensor")

    return (
        (
            next(
                (
                    entity
                    for entity in sensor_component.entities
                    if entity.entity_id == sensor_id
                ),
                None,
            ),
            entity,
        )
        if entity and entity_entry and sensor_component
        else (None, None)
    )
