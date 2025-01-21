import logging
import math
import numpy as np
from aiohttp.web import Response
from collections import OrderedDict
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
    API_GET_VIRTUAL_OBJECTS,
    API_GET_MULTIMEDIA_FILES,
    API_GET_CLOSE_OBJECTS,
    MIN_DISTANCE
)
from .models import Automation
from .hass_utils import get_entity_instance_by_entity_id
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
        # get id
        automation_id = request.match_info.get("id")

        # retrieve
        if automation_id:
            automation = await async_get_automation(self.hass, automation_id)
            automations = [Automation.from_yaml(self.hass, automation).to_dict()]
        else:
            # list
            automations = [Automation.from_yaml(self.hass, a).to_dict() for a in await async_list_automations(self.hass)]


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
    methods = ["POST"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        # get parameters #
        # only_objects
        only_objects = request.query.get("only_objects", False)
        objects = list()
        objects_all = list()
        registered_groups = filter(lambda state: state.entity_id.startswith("group."), self.hass.states.async_all())

        if only_objects:
           objects = [state.entity_id.split(".")[-1] for state in registered_groups]
        else:
            # names
            try:
                names = (await request.json())
            except Exception as e:
                names = dict()
            names = [n.lower() for n in names.get("names", [])]

            for state in registered_groups:
                new_group = dict()
                new_group["name"] = state.entity_id.split(".")[-1]

                components = list()
                for i in state.attributes["entity_id"]:
                    c = self.hass.states.get(i)
                    if c:
                        component_state = c.as_dict().copy()
                        # drop unuseful keys
                        for k in ["last_changed", "last_reported", "last_updated", "context"]:
                            if k in component_state:
                                component_state.pop(k)
                        # add class name
                        component_entity = get_entity_instance_by_entity_id(self.hass, i)
                        component_state["class"] = component_entity.eca_script
                        components.append(component_state)
                    new_group["components"] = components

                objects_all.append(new_group)
                if not names or new_group["name"].lower() in names:
                    objects.append(new_group)


        return self.json({
            "objects": objects if objects else objects_all
        })


class MultimediaFilesView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_MULTIMEDIA_FILES}"
    name = f"api:{API_GET_MULTIMEDIA_FILES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        # todo request to unity
        audio_list = ["nona_sinfonia_audio.mp3"]
        video_list = ["nona_sinfonia_video.mp4"]
        # return files
        return self.json({
            "file-audio": audio_list,
            "file-video": video_list,
        })


class FindCloseObjectsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_CLOSE_OBJECTS}"
    name = f"api:{API_GET_CLOSE_OBJECTS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @staticmethod
    def get_distance(a, b) -> float:
        p1 = np.array((a['x'],a['y'],a['z']))
        p2 = np.array((b['x'],b['y'],b['z']))
        d1 = np.linalg.norm(p1-p2)
        d2 = math.sqrt(
            (a['x'] - b['x'])**2 +
            (a['y'] - b['y'])**2 +
            (a['z'] - b['z'])**2
        )
        return d2

    def get_eca_object_instance(self, group_name: str) -> object:
        group_ecaobject = None
        try:
            group_ecaobject = get_entity_instance_by_entity_id(self.hass, f"sensor.{group_name}_ecaobject")
        except Exception as e:
            print(f"not found {group_name} + {e}")
        return group_ecaobject

    async def get(self, request):
        object_name = request.query.get("name", "")
        distances = dict()
        registered_groups = list(filter(lambda state: state.entity_id.startswith("group."), self.hass.states.async_all()))
        ref = self.get_eca_object_instance(object_name)

        if ref and hasattr(ref, "position"):
            # get object position
            for group in registered_groups:
                group_name = group.entity_id.split(".")[-1]
                if object_name != group_name:
                    group_ecaobject = self.get_eca_object_instance(group_name)
                    if group_ecaobject and hasattr(group_ecaobject, "position"):
                        distances[group_name] = self.get_distance(ref.position, group_ecaobject.position)

        # keep in distances: i) very close objects (distance < 1) + ii) framed/pointed/grabbed objects
        from .sensor import DEQUE_FRAMED_OBJECTS, DEQUE_POINTED_OBJECTS, DEQUE_INTERACTED_OBJECTS
        deques = [DEQUE_FRAMED_OBJECTS, DEQUE_POINTED_OBJECTS, DEQUE_INTERACTED_OBJECTS]
        distances = dict(
            filter(
                lambda x: x[1] < MIN_DISTANCE or any(x[0] in list(d) for d in deques),
                distances.items()
            )
        )
        return self.json(OrderedDict(sorted(distances.items(), key=lambda x: x[1])))
