import logging
from aiohttp.web import Response
from homeassistant.components import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import State
from .automations import (
    async_list_automations,
    async_add_update_automation,
    async_get_automation,
    async_remove_automation
)
from .const import (
    API_GET_AUTOMATIONS,
    API_GET_VIRTUAL_DEVICES,
    API_GET_ECA_CAPABILITIES,
    API_GET_CONTEXT_OBJECTS,
    API_GET_VIRTUAL_OBJECTS
)
from .models import Automation
from .sensor import CURRENT_MODULE
from .utils import MappedClasses


_LOGGER = logging.getLogger(__name__)


class AutomationsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_AUTOMATIONS}"
    name = f"api:{API_GET_AUTOMATIONS}"
    methods = ["POST", "GET", "DELETE"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        # get the json defintion of an automation, convert it to yaml format and save it
        data = await request.json()
        print(f"RECEIVED DATA: {type(data)} \ndata:\n{data}")
        if isinstance(data, dict):
            yaml_code = [Automation.from_dict(data).to_yaml(self.hass)]
        else:
            yaml_code = [Automation.from_dict(d).to_yaml(self.hass) for d in data]

        await async_add_update_automation(self.hass, yaml_code)
        return Response(status=200)

    async def get(self, request):
        # type
        eca = request.query.get("eca", False)

        automation_id = request.match_info.get("id")
        # retrieve
        if automation_id:
            automation = await async_get_automation(self.hass, automation_id)
            automations = [Automation.from_yaml(self.hass, automation, eca).to_dict()]
        else:
            # list
            automations = [Automation.from_yaml(self.hass, a, eca).to_dict() for a in await async_list_automations(self.hass)]

        return self.json({"automations": automations})

    async def delete(self, request):
        automation_id = request.match_info.get("id")
        if automation_id:
            await async_remove_automation(self.hass, automation_id)
            return Response(status=200)
        _LOGGER.error(f"The request must specify an id in the url")


class ListFramedVirtualDevicesView(HomeAssistantView):
    """class State:

    entity_id   str      e.g.    "person.giagobox",

    state   str          e.g.    "unknown"
    domain  str          e.g.    "unknown"

    context homeassistant.core.Context        e.g.    <homeassistant.core.Context object at 0x7fc10ebe68d0>

    attributes  homeassistant.util.read_only_dict.ReadOnlyDict  e.g.    {'editable': True, 'id': 'giagobox', 'device_trackers': [], 'user_id': '5fa37f398b5648eb955ca701f38ab210', 'friendly_name': 'Giagobox'}

    last_changed    datetime.datetime   e.g.    "2024-11-14T15:51:47.761084+00:00"
    last_reported   datetime.datetime   e.g.    "2024-11-14T15:51:47.761084+00:00"
    last_updated    datetime.datetime   e.g.    "2024-11-14T15:51:47.761084+00:00"

    as_dict()    homeassistant.util.read_only_dict.ReadOnlyDict   e.g.   {'entity_id': 'person.giagobox', 'state': 'unknown', 'attributes': {'editable': True, 'id': 'giagobox', 'device_trackers': [], 'user_id': '5fa37f398b5648eb955ca701f38ab210', 'friendly_name': 'Giagobox'}, 'last_changed': '2024-11-14T15:59:51.742010+00:00', 'last_reported': '2024-11-14T15:59:53.029074+00:00', 'last_updated': '2024-11-14T15:59:53.029074+00:00', 'context': {'id': '01JCNPE265RWHYC4BXDVG69W88', 'parent_id': None, 'user_id': None}}
    as_dict_json    bytes   e.g.    b'{"entity_id":"person.giagobox","state":"unknown","attributes":{"editable":true,"id":"giagobox","device_trackers":[],"user_id":"5fa37f398b5648eb955ca701f38ab210","friendly_name":"Giagobox"},"last_changed":"2024-11-14T15:59:51.742010+00:00","last_reported":"2024-11-14T15:59:53.029074+00:00","last_updated":"2024-11-14T15:59:53.029074+00:00","context":{"id":"01JCNPE265RWHYC4BXDVG69W88","parent_id":null,"user_id":null}}'
    """

    url = f"/api/eud4xr/{API_GET_VIRTUAL_DEVICES}"
    name = f"api:{API_GET_VIRTUAL_DEVICES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        def filter_sensors(s: State):
            # Check if:
            # 0) The entity is a sensor and its state == "active"
            # 1) It has the attribute device_class == eca_entity
            # 2) @Type is equal to "ECAObject"
            # 3) The attribute "isInsideCamera" is "yes"
            # If all the conditions are met, return True. Otherwise, return False
            #print(f"\nsensor: {s}\n")

            # 0) The entity is not a sensor
            if s.domain != "sensor" or s.state != "active":
                return False

            # 1) It has the attribute "friendly_name"
            if not s.attributes or s.attributes.get("device_class") != "eca_entity":
                return False

            # 2) @Type is equal to "ECAObject"
            friendly_name = s.attributes["friendly_name"]
            ecatype = friendly_name.split("@")
            if len(ecatype) > 1 and ecatype[-1].lower() != "ECAObject".lower():
                return False

            # 3) The attribute "isInsideCamera" is "yes"
            if s.attributes["isInsideCamera"] != "yes":
                return False

            # If all the conditions are met, return True
            return True

        # Get the list of sensors in Home Assistant
        states = self.hass.states.async_all()

        states = list(filter(filter_sensors, states))

        # Filter sensors only ECAObject with isInsideCamera = true
        return self.json(states)


class ListECACapabilitiesView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_ECA_CAPABILITIES}"
    name = f"api:{API_GET_ECA_CAPABILITIES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        all = request.query.get("all", False)

        ECA_SCRIPTS = MappedClasses.mapping_classes(self.hass)
        data = {k: v.to_dict() for k,v in ECA_SCRIPTS.items()}

        if not all:
            filtered_data = dict()
            registered_groups = filter(lambda state: state.entity_id.startswith("group."), self.hass.states.async_all())
            for state in registered_groups:
                for sensor_id in state.attributes["entity_id"]:
                    sensor_class = self.hass.states.get(sensor_id).attributes.get("friendly_name").split("@")[-1]
                    if not sensor_class in filtered_data:
                        filtered_data[sensor_class] = data[sensor_class]
            data = filtered_data

        return self.json({"capabilities": data})


class ContextObjectsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_CONTEXT_OBJECTS}"
    name = f"api:{API_GET_CONTEXT_OBJECTS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        from .sensor import DEQUE_FRAMED_OBJECTS, DEQUE_POINTED_OBJECTS, DEQUE_INTERACTED_OBJECTS
        return self.json({
            "framed_objects": list(DEQUE_FRAMED_OBJECTS),
            "pointed_objects": list(DEQUE_POINTED_OBJECTS),
            "interacted_with_objects": list(DEQUE_INTERACTED_OBJECTS)
        })


class VirtualObjectsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_VIRTUAL_OBJECTS}"
    name = f"api:{API_GET_VIRTUAL_OBJECTS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        only_objects = request.query.get("only_objects", False)
        objects = list()
        registered_groups = filter(lambda state: state.entity_id.startswith("group."), self.hass.states.async_all())

        if only_objects:
           objects = [state.entity_id.split(".")[-1] for state in registered_groups]
        else:
            for state in registered_groups:
                new_group = dict()
                new_group["name"] = state.entity_id.split(".")[-1]
                if not only_objects:
                    components = list()
                    for i in state.attributes["entity_id"]:
                        components.append(self.hass.states.get(i))
                    new_group["components"] = components
                    objects.append(new_group)
        return self.json({
            "objects": objects
        })
