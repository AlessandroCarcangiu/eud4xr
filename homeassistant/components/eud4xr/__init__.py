# ruff: noqa

import copy
from datetime import datetime
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.group import Group, expand_entity_ids
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .automation import Automation
from .automations import async_list_automations
from .const import *
from .hass_utils import find_group, find_sensor
from .sensor import (
    GAMEOBJECT_ECASCRIPT_SCHEMA,
    SERVICE_UPDATE_FROM_UNITY,
    UPDATES_FROM_UNITY_SCHEMA,
)
from .task_modelling import (
    MARK_DONE_SERVICE_SCHEMA,
    TaskExpression,
)
from .views import (
    AutomationsView,
    ContextObjectsView,
    FindCloseObjectsView,
    UpdateIotDeviceIsFramedView,
    ListECACapabilitiesView,
    MultimediaFilesView,
    ObjectsView,
    TaskExpressionView,
    VirtualObjectsView,
    AvailableECAScripts,
    TestUnityServer_ExistingEndpointView,
    TestUnityServer_NonExistingEndPointView,
    RealObjectsCapabilitiesView
)

_LOGGER = logging.getLogger(__name__)

group_locks = {}

SERVICE_SEND_REQUEST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_SUBJECT): cv.string,
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_VERB): cv.string,
        vol.Optional("obj"): object,
        vol.Optional("variable"): cv.string,
        vol.Optional("modifier"): cv.string,
        vol.Optional("value"): object,
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
    # init
    conf = config[DOMAIN]
    server_unity_url = conf.get(CONF_SERVER_UNITY_URL)
    server_unity_token = conf.get(CONF_SERVER_UNITY_TOKEN)
    sensors = conf.get(CONF_UNITY_ENTITIES)
    failed_updates = list()

    # load eca objects defined within configuration.yaml file
    hass.data[DOMAIN] = {}
    if sensors:
        for game_object_config in sensors:
            hass.async_create_task(
                hass.helpers.discovery.async_load_platform(
                    "sensor", DOMAIN, game_object_config, config
                )
            )

    # load order independence counters from db
    task_modelling_store = Store(
        hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
    )
    if task_modelling_store:
        task_modelling_store_data = await task_modelling_store.async_load() or {}
        if (
            CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY
            not in task_modelling_store_data
        ):
            task_modelling_store_data[
                CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY
            ] = []

        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(
                "sensor",
                DOMAIN,
                {
                    CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY: task_modelling_store_data.get(
                        CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY
                    ),
                },
                {},
            )
        )

        async def on_hass_started(event):
            t_expr = TaskExpression(hass)
            await t_expr.restore_expressions()

    hass.bus.async_listen_once("homeassistant_started", on_hass_started)

    # t_expr = TaskExpression(hass)
    # await t_expr.restore_expressions()

    ## Send update to Unity
    async def handle_send_update_to_server_unity(call: ServiceCall) -> None:
        await send_update_to_server_unity(call.data)

    async def send_update_to_server_unity(payload: dict) -> None:
        # await refresh_token()
        headers = {}  # {"Authorization": f"Bearer {server_unity_token}"}
        # send request
        async with aiohttp.ClientSession() as session:
            _LOGGER.info(f"Sending an update to {server_unity_url}{API_UNITY_NOTIFY_UPDATE}")
            try:
                data={
                    "url":API_UNITY_NOTIFY_UPDATE,
                    "data": payload
                }
                async with session.post(
                    #f"{server_unity_url}{API_UNITY_NOTIFY_UPDATE}",
                    #json=payload
                    server_unity_url,
                    json=data
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
            hass.bus.async_fire("event_sensor_registered")
            _LOGGER.info(f"Registered a new sensor - {new_entity_name}")

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
                hass.async_add_job(async_update_group)
                # try:
                #     hass.async_add_job(async_update_group)
                # except Exception as e:
                #     print(f"ERROR NELLA HASS.ADD_JOB(ASYNC_UPDATE_GROUP: {current_entities} - {new_sensors_to_append}")

        _LOGGER.info("Registered a new object - {entity_name}")

    ## Update from Unity
    async def handle_update_from_unity(call) -> None:
        await async_update_from_unity(hass, call.data)

    async def async_update_from_unity(hass, update, is_retry: bool = False):
        message = f"Received a new update from unity: {update}" if not is_retry else f"Received an old update from unity: {update}"
        _LOGGER.info(message)
        # update state #
        data = copy.deepcopy(update.get(CONF_SERVICE_UPDATE_FROM_UNITY_UPDATE))
        group_id = data.pop("unity_id").split("@")[0].lower()
        group = find_group(hass, group_id)
        sensor = None
        entity = None
        if group:
            sensors_ids = group.attributes.get("entity_id", [])
            attribute = data.get("attribute")
            for sensor_id in sensors_ids:
                sensor, entity = find_sensor(hass, sensor_id)
                if sensor and entity:
                    # on action #
                    if CONF_SERVICE_UPDATE_FROM_UNITY_ATTRIBUTE not in data:
                        sensor.on_action(**data)
                        return True
                    # update a sensor's attribute
                    attributes = dict(entity.attributes)
                    if attribute and attribute in attributes:
                        if (
                            attribute not in sensor.last_updates
                            or sensor.last_updates[attribute]
                            < update[CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP]
                        ):
                            # update value
                            new_value = data.get("new_value")
                            attributes[attribute] = new_value
                            hass.states.async_set(sensor_id, entity.state, attributes)
                            sensor.last_updates[attribute] = update[
                                CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP
                            ]

                            # if sensor defines a setter for this property -> update deque list
                            attr = getattr(sensor.__class__, attribute)
                            if isinstance(attr, property) and attr.fset is not None:
                                attr.fset(sensor, new_value)

                            _LOGGER.info(
                                f"Attribute {attribute} of Entity {sensor} updated!"
                            )

                        else:
                            _LOGGER.warning(
                                f"Received an old {update} for the Entity {sensor}. Delta timestamp: {sensor.last_updates[attribute]
                            - update[CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP]} - Package's timestamp: {sensor.last_updates[attribute]}, latest timestamp: {update[CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP]}"
                            )
                        return True
                else:
                    _LOGGER.warning(
                        f"Sensor {sensor} or entity {entity} not found - Sensor_id: {sensor_id}"
                    )
        elif not is_retry:
            ts = int(datetime.now().timestamp() * 1000)
            failed_updates.append((ts, update))
            _LOGGER.error(
                f"Received a new update from unity - Error on handling update {update}\n"
                + f"Possibly causes: group: {group} or sensor {sensor} or entity {entity} not found"
            )
        else:
            _LOGGER.error(f"Failing - {group} - {group_id}")
        return False

    # the system registered a new sensor -> check on the failed update list
    async def handle_failed_update_list(event):
        _LOGGER.info("HANDLE FAILED UPDATE LIST")
        for ts, update in failed_updates.copy():
            now = int(datetime.now().timestamp() * 1000)
            _LOGGER.info(
                f"{now} / {ts} / {now-ts} / {now-ts > TIMESTAMP_MIN_UPDATE} - {update} - num_elements: {len(failed_updates)}"
            )
            if now - ts > TIMESTAMP_MIN_UPDATE:
                _LOGGER.info(f"Deleted an old update {update}")
                failed_updates.remove((ts, update))
            else:
                res = await async_update_from_unity(hass, update, is_retry=True)
                if res:
                    _LOGGER.info(f"Handled an old update {update}")
                    failed_updates.remove((ts, update))

    # listener update automation file
    @callback
    async def handle_automation_updated(event):
        _LOGGER.info("Automation update detected. Calling external service...")
        await notify_automations(hass)

    async def notify_automations(hass: HomeAssistant):
        try:
            async with aiohttp.ClientSession() as session:
                automations = list()
                for a in await async_list_automations(hass):
                    try:
                        automations.append(Automation.from_yaml(hass, a).to_dict())
                    except Exception as e:
                        _LOGGER.exception(f"Error on decoding automation {a} \nError throwed: {e}")
                try:
                    data={
                        "url":API_UNITY_NOTIFY_AUTOMATIONS,
                        "data": automations
                    }
                    async with session.post(
                        #f"{server_unity_url}{API_UNITY_NOTIFY_AUTOMATIONS}",
                        #json=automations,
                        server_unity_url,
                        json=data
                    ) as response:
                        if response.status == 200:
                            _LOGGER.info("Update successfully sent")
                        else:
                            _LOGGER.error(
                                f"Error on notifying automations to Unity: {response.status}"
                            )

                except Exception as e:
                    _LOGGER.error(
                        f"Error on conctating Unity while notifying automations: {e}"
                    )
        except Exception as e:
            _LOGGER.error(f"Error on converting automations to json structure: {e}")

    # listener update expression store
    @callback
    async def handle_expression_updated(event):
        _LOGGER.info("Expression update detected. Calling external service...")
        await notify_expressions(hass)

    async def notify_expressions(hass: HomeAssistant):
        try:
            expressions = await TaskExpression(hass).get_expressions_from_store()
            async with aiohttp.ClientSession() as session:
                try:
                    data={
                        "url":API_UNITY_NOTIFY_AUTOMATIONS,
                        "data": {"expressions": expressions}
                    }
                    async with session.post(
                        # f"{server_unity_url}{API_UNITY_NOTIFY_EXPRESSIONS}",
                        # json={"expressions": expressions},
                        server_unity_url,
                        json=data
                    ) as response:
                        if response.status == 200:
                            _LOGGER.info("Update successfully sent")
                        else:
                            _LOGGER.error(
                                f"Error on notifying expressions to Unity: {response.status}"
                            )

                except Exception as e:
                    _LOGGER.error(
                        f"Error on sending data to Unity while notifying expressions: {e}"
                    )
        except Exception as e:
            _LOGGER.error(f"Error on converting expressions to json structure: {e}")

    # Task modelling Handlers #
    async def handle_increment_counter(call):
        entity_id = call.data.get("entity_id")
        _LOGGER.info(f"Incrementing counter for entity_id: {entity_id}")
        if not entity_id:
            _LOGGER.error("Missing entity_id in increment_counter service call")
            return

        counter = hass.data[CONF_TASK_MODELLING_ENTITIES].get(entity_id)
        if not counter:
            _LOGGER.error(f"Counter with entity_id {entity_id} not found")
            return

        await counter.increment()

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
        service=SERVICE_INCREMENT_COUNTER,
        service_func=handle_increment_counter,
    )
    hass.bus.async_listen("event_automation_updated", handle_automation_updated)
    hass.bus.async_listen("event_expression_updated", handle_expression_updated)
    hass.bus.async_listen("event_sensor_registered", handle_failed_update_list)

    # views
    hass.http.register_view(ListECACapabilitiesView(hass))

    hass.http.register_view(ContextObjectsView(hass))
    hass.http.register_view(MultimediaFilesView(hass))
    hass.http.register_view(FindCloseObjectsView(hass))

    hass.http.register_view(AutomationsView(hass))
    hass.http.register_view(TaskExpressionView(hass))

    hass.http.register_view(VirtualObjectsView(hass))
    hass.http.register_view(ObjectsView(hass))
    hass.http.register_view(UpdateIotDeviceIsFramedView(hass))
    hass.http.register_view(AvailableECAScripts())
    # testing
    hass.http.register_view(RealObjectsCapabilitiesView(hass))
    hass.http.register_view(TestUnityServer_ExistingEndpointView(hass))
    hass.http.register_view(TestUnityServer_NonExistingEndPointView(hass))

    async def handle_task_expression_mark_done(call):
        task_expression = TaskExpression(hass)
        await task_expression.mark_done(
            call.data["entity_id"],
            call.data["name"],
            call.data["type"],
            call.data.get("part_of", None),
        )

    hass.services.async_register(
        DOMAIN,
        service="mark_done",
        service_func=handle_task_expression_mark_done,
        schema=MARK_DONE_SERVICE_SCHEMA,
    )

    return True
