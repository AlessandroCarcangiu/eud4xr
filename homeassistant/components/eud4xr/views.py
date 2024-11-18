import logging

from homeassistant.components import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import State

from .automations import async_list_automations
from .const import SERVICE_GET_AUTOMATIONS, SERVICE_GET_VIRTUAL_DEVICES

_LOGGER = logging.getLogger(__name__)


class ListAutomationsView(HomeAssistantView):
    url = f"/api/eud4xr/{SERVICE_GET_AUTOMATIONS}"
    name = f"api:{SERVICE_GET_AUTOMATIONS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        result = await async_list_automations(self.hass)
        return self.json({"automations": result})


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

    url = f"/api/eud4xr/{SERVICE_GET_VIRTUAL_DEVICES}"
    name = f"api:{SERVICE_GET_VIRTUAL_DEVICES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        def filter_sensors(s: State):
            # Check if:
            # 0) The entity is a sensor and its state == "active"
            # 1) It has the attribute device_class == eca_entity
            # - potentially removable 1) It has the attribute "friendly_name"
            # - potentially removable 2) The attribute "friendly_name" is a string
            # - potentially removable 3) The attribute "friendly_name" is something like Name@Type
            # 4) @Type is equal to "ECAObject"
            # 5) The attribute "isInsideCamera" is "yes"
            # If all the conditions are met, return True. Otherwise, return False
            #print(f"\nsensor: {s}\n")

            # 0) The entity is not a sensor
            if s.domain != "sensor" or s.state != "active":
                return False

            # 1) It has the attribute "friendly_name"
            if not s.attributes or s.attributes.get("device_class") != "eca_entity":
                return False

            # # 1) It has the attribute "friendly_name"
            # if "friendly_name" not in s.attributes:
            #     return False

            # # 2) The attribute "friendly_name" is a string
            # ecatype_value = s.attributes["friendly_name"]
            # ecatype_value__type = type(ecatype_value)
            # if ecatype_value__type is not str:
            #     msg = (f"Error with {s.entity_id}! Attribute 'friendly_name' (value={ecatype_value}) "
            #            f"should be a string and not {ecatype_value__type}!")
            #     _LOGGER.warning(msg)
            #     return False

            # # 3) The attribute "friendly_name" is something like Name@Type
            # ecatype_value__split = ecatype_value.split("@")
            # if len(ecatype_value__split) != 2:
            #     msg = (f"Error with {s.entity_id}! Attribute 'friendly_name' (value={ecatype_value}) "
            #            f"should be a string with the format Name@Type!")
            #     _LOGGER.warning(msg)
            #     return False

            # 4) @Type is equal to "ECAObject"
            friendly_name = s.attributes["friendly_name"]
            ecatype = friendly_name.split("@")
            if len(ecatype) > 1 and ecatype[-1].lower() != "ECAObject".lower():
                return False

            print(s.attributes)

            # 5) The attribute "isInsideCamera" is "yes"
            if s.attributes["isInsideCamera"] != "yes":
                return False

            # If all the conditions are met, return True
            # print(f"Sensor {s.entity_id} is an ECA Object")
            return True

        # Get the list of sensors in Home Assistant
        states = self.hass.states.async_all()

        if DO_PRINT := False:
            print(f"AAAAAA STATES {states!s}")
            print(f"BBBBBB STATES[0] {states[0]!s}")
            print(f"CCCCCC TYPE STATES {type(states)!s}")
            print(f"DDDDDD TYPES STATES[0] {type(states[0])!s}")
            state: State = states[0]
            print(f"{type(state.attributes)} | {state.attributes}")
            print(f"{type(state.context)} | {state.context}")
            print(f"{type(state.domain)} | {state.domain}")
            print(f"{type(state.state)} | {state.state}")
            print(f"{type(state.as_dict())} | {state.as_dict()}")
            print(f"{type(state.as_dict_json)} | {state.as_dict_json}")
            print(f"{type(state.entity_id)} | {state.entity_id}")
            print(f"{type(state.last_changed)} | {state.last_changed}")
            print("EEEEEE")

        states = list(filter(filter_sensors, states))

        # Filter sensors only ECAObject with isInsideCamera = true
        return self.json(states)
