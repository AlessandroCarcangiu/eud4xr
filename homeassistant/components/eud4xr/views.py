# ruff: noqa
import inspect
import logging
import json
import math
import yaml
from aiohttp.web import Response
from collections import OrderedDict
from homeassistant.components import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import State
from .automation import Automation
from .automations import (
    async_add_update_automation,
    async_get_automation,
    async_list_automations,
    async_remove_automation,
)
from .const import (
    API_EXPRESSION,
    API_GET_AUTOMATIONS,
    API_GET_CLOSE_OBJECTS,
    API_GET_CONTEXT_OBJECTS,
    API_GET_ECA_CAPABILITIES,
    API_GET_MULTIMEDIA_FILES,
    API_GET_OBJECTS,
    API_GET_VIRTUAL_DEVICES,
    API_GET_VIRTUAL_OBJECTS,
    API_UPDATE_IOTDevice_VISIBILITY_FROM_UNITY,
    MIN_DISTANCE,
    IS_DEBUG,
    API_UNITY_TEST,
    META_UNITY_SERVER_IP,
    API_GET_RealObjects_Capabilities,
    API_AVAILABLE_ECA_SCRIPTS,
    AUTOMATION_PATH,
    ENTITY_REGISTRY,
    API_LIST_OBJECTS
)
from .eca_classes import ECAPosition
from .entity import ECAEntity, EUD4XRIOTDevice
from .filters import get_devices_data, get_virtual_entities
from .hass_utils import get_entity_instance_by_entity_id
from .task_modelling import TaskExpression
from .utils import MappedClasses, update_deque

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
        _LOGGER.info(f"RECEIVED DATA: {type(data)} \ndata:\n{data}")
        if isinstance(data, dict):
            yaml_code = [Automation.from_dict(data).to_yaml(self.hass)]
        else:
            yaml_code = [Automation.from_dict(d).to_yaml(self.hass) for d in data]

        await async_add_update_automation(self.hass, yaml_code)
        return Response(status=200)

    async def get(self, request):
        # get id
        automation_id = request.match_info.get("id")
        automations = list()

        # retrieve
        if automation_id:
            automation = await async_get_automation(self.hass, automation_id)
            if automation:
                automations = [Automation.from_yaml(self.hass, automation).to_dict()]
        else:
            # list
            for a in await async_list_automations(self.hass):
                try:
                    automations.append(Automation.from_yaml(self.hass, a).to_dict())
                except Exception as e:
                    _LOGGER.exception(f"Error on decoding automation {a} \nError throwed: {e}")

        return self.json({"automations": automations})

    async def delete(self, request):
        await self.hass.async_add_executor_job(self.__remove_automations_and_registry)
        return Response(status=200)

    def __remove_automations_and_registry(self) -> None:
        file_automations = self.hass.config.path(AUTOMATION_PATH)
        file_entity = self.hass.config.path(ENTITY_REGISTRY)
        # clear automations.yaml
        with open(file_automations, "w") as f:
            yaml.safe_dump([], f)
        # clear registry
        with open(file_entity, "r") as f:
            registry = json.load(f)
        registry["data"]["entities"] = [
            e for e in registry["data"]["entities"]
            if not e.get("entity_id", "").startswith("automation.")
        ]
        with open(file_entity, "w") as f:
            json.dump(registry, f, indent=2)


class ListECACapabilitiesView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_ECA_CAPABILITIES}"
    name = f"api:{API_GET_ECA_CAPABILITIES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        all = request.query.get("all", False)

        ECA_SCRIPTS = MappedClasses.mapping_classes(self.hass)
        data = {k: v.to_dict() for k, v in ECA_SCRIPTS.items()}

        if not all:
            filtered_data = dict()
            registered_groups = filter(
                lambda state: state.entity_id.startswith("group."),
                self.hass.states.async_all(),
            )
            for state in registered_groups:
                for sensor_id in state.attributes["entity_id"]:
                    sensor_class = (
                        self.hass.states.get(sensor_id)
                        .attributes.get("friendly_name")
                        .split("@")[-1]
                    )
                    if sensor_class not in filtered_data:
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
        from .sensor import (
            DEQUE_FRAMED_OBJECTS,
            DEQUE_INTERACTED_OBJECTS,
            DEQUE_POINTED_OBJECTS,
            DICT_IOT_DEVICES,
        )

        return self.json(
            {
                "framed_objects": list(DEQUE_FRAMED_OBJECTS),
                "pointed_objects": list(DEQUE_POINTED_OBJECTS),
                "interacted_with_objects": list(DEQUE_INTERACTED_OBJECTS)
            }
        )


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
        registered_groups = filter(
            lambda state: state.entity_id.startswith("group."),
            self.hass.states.async_all(),
        )

        if only_objects:
            objects = [state.entity_id.split(".")[-1] for state in registered_groups]
        else:
            # names
            try:
                names = await request.json()
            except Exception:
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
                        for k in [
                            "last_changed",
                            "last_reported",
                            "last_updated",
                            "context",
                        ]:
                            if k in component_state:
                                component_state.pop(k)
                        # add class name
                        component_entity = get_entity_instance_by_entity_id(
                            self.hass, i
                        )
                        component_state["class"] = component_entity.eca_script
                        components.append(component_state)
                    new_group["components"] = components

                objects_all.append(new_group)
                if not names or new_group["name"].lower() in names:
                    objects.append(new_group)

        return self.json({"objects": objects if objects else objects_all})


class ListObjectsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_LIST_OBJECTS}"
    name = f"api:{API_LIST_OBJECTS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        real_objects = await get_devices_data(self.hass, only_objects=True)
        virtual_objects = await get_virtual_entities(self.hass, only_objects=True)
        return self.json(real_objects+virtual_objects)


class ObjectsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_OBJECTS}"
    name = f"api:{API_GET_OBJECTS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        real_objects = await get_devices_data(self.hass)
        virtual_objects = await get_virtual_entities(self.hass)
        return self.json({**real_objects, **virtual_objects})


class MultimediaFilesView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_MULTIMEDIA_FILES}"
    name = f"api:{API_GET_MULTIMEDIA_FILES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        # todo request to unity
        audio_list = [
            "nona_sinfonia_audio.mp3",
            "la_regina_egizia.mp3",
            "barocco.mp3",
            "le_divinità_egizie.mp3",
        ]
        video_list = ["nona_sinfonia_video.mp4", "chi_era_ophelia.mp4"]
        # return files
        return self.json(
            {
                "file-audio": audio_list,
                "file-video": video_list,
            }
        )


class FindCloseObjectsView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_CLOSE_OBJECTS}"
    name = f"api:{API_GET_CLOSE_OBJECTS}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @staticmethod
    def get_distance(a, b) -> float:
        d2 = math.sqrt(
            (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2
        )
        return d2

    @staticmethod
    def get_direction(a, b) -> list:
        dx = b["x"] - a["x"]
        dy = b["y"] - a["y"]
        dz = b["z"] - a["z"]

        directions = list()
        if dz > 0:
            directions.append("sopra")
        elif dz < 0:
            directions.append("sotto")
        if dy > 0:
            directions.append("davanti")
        elif dy < 0:
            directions.append("dietro")
        if dx > 0.5 or dx < 0.5:
            directions.append("a fianco")
        return " e ".join(directions) if directions else "nella stessa posizione"

    def get_entity_position_from_name(self, name: str) -> any:
        def try_search_iotDevice(iot_name):
            from .sensor import DICT_IOT_DEVICES
            value = DICT_IOT_DEVICES.get(iot_name, None)
            return value

        def try_search_virtualobject(group_name):
            group_ecaobject = None
            try:
                group_ecaobject = get_entity_instance_by_entity_id(self.hass, f"sensor.{group_name}_ecaobject")
            except Exception as e:
                group_ecaobject = None
            return group_ecaobject

        output_entity_position = try_search_iotDevice(name)
        if output_entity_position is None:
            output_entity_position = try_search_virtualobject(name)
        if output_entity_position is None:
            raise ValueError(
                f"Object '{name}' not found neither as IoT device nor as virtual object."
                "Please check the name and try again."
            )
        return output_entity_position


    async def get(self, request):
        from .sensor import (DICT_IOT_DEVICES,DEQUE_FRAMED_OBJECTS,DEQUE_INTERACTED_OBJECTS,DEQUE_POINTED_OBJECTS)

        object_name = request.query.get("name", "").lower()
        ref = self.get_entity_position_from_name(object_name)
        if IS_DEBUG: print(f"Object name: {object_name}, ECAObject: {ref}, hasattr: {hasattr(ref, 'position')}")

        if not ref:
            raise ValueError("Object not found or has no position attribute.")

        distances = dict()

        # virtual objects
        registered_groups = list(
            filter(
                lambda state: state.entity_id.startswith("group."),
                self.hass.states.async_all(),
            )
        )
        if IS_DEBUG: print(f"Registered groups: {[g.entity_id for g in registered_groups]}")
        # Add groups and DICT_IOT_DEVICES.names
        common_list = []
        common_list.extend(g.entity_id.split(".")[-1] for g in registered_groups)
        common_list.extend(iot_device_name for iot_device_name in DICT_IOT_DEVICES.keys())

        for curr_entity_name in common_list:
            if IS_DEBUG: print(f"Entity: {curr_entity_name}")
            if object_name != curr_entity_name:
                group_ecaobject = self.get_entity_position_from_name(curr_entity_name)
                if IS_DEBUG: print(f"Group name: {curr_entity_name}, ECAObject: {group_ecaobject}")
                if group_ecaobject:
                    distances[curr_entity_name] = {
                        "distance": self.get_distance(
                            ref.position, group_ecaobject.position
                        ),
                        "directions": self.get_direction(
                            ref.position, group_ecaobject.position
                        ),
                    }

        # keep in distances: i) very close objects (distance < 1) + ii) framed/pointed/grabbed objects
        deques = [
            DEQUE_FRAMED_OBJECTS,
            DEQUE_POINTED_OBJECTS,
            DEQUE_INTERACTED_OBJECTS,
        ]
        distances = dict(
            filter(
                lambda x: x[1]["distance"] < MIN_DISTANCE
                or any(x[0] in list(d) for d in deques),
                distances.items(),
            )
        )
        return self.json(
            OrderedDict(sorted(distances.items(), key=lambda x: x[1]["distance"]))
        )


class AvailableECAScripts(HomeAssistantView):
    url = f"/api/eud4xr/{API_AVAILABLE_ECA_SCRIPTS}"
    name = f"api:{API_AVAILABLE_ECA_SCRIPTS}"
    methods = ["GET"]

    async def get(self, request):
        from .sensor import CURRENT_MODULE
        classes = inspect.getmembers(CURRENT_MODULE, inspect.isclass)
        subclasses = [
            name for name, cls in classes
            if issubclass(cls, ECAEntity) and cls is not ECAEntity
        ]
        return self.json(
            subclasses
        )


def is_valid_expression_element(element):
    if isinstance(element, str):
        return True

    if (
        isinstance(element, dict)
        and "name" in element
        and "choice" in element
        and len(element) == 2
    ):
        name = element["name"]
        choices = element["choice"]
        if isinstance(name, str) and isinstance(choices, list):
            return all(is_valid_expression_element(e) for e in choices)
        return False

    if (
        isinstance(element, dict)
        and "name" in element
        and "order" in element
        and len(element) == 2
    ):
        name = element["name"]
        orders = element["order"]
        if isinstance(name, str) and isinstance(orders, list):
            return all(is_valid_expression_element(e) for e in orders)
        return False

    if isinstance(element, dict) and len(element) == 1:
        key = next(iter(element))
        if key in ("sequence", "choice", "order"):
            sub_expr = element[key]
            return isinstance(sub_expr, list) and all(
                is_valid_expression_element(e) for e in sub_expr
            )

    return False


class TaskExpressionView(HomeAssistantView):
    url = f"/api/eud4xr/{API_EXPRESSION}"
    name = f"api:{API_EXPRESSION}"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.task_expression = TaskExpression(hass)

    def json_message(self, message: str, status_code: int = 200) -> dict:
        return self.json({"message": message}, status_code=status_code)

    async def get(self, request) -> dict:
        try:
            expressions = await self.task_expression.get_expressions_from_store()
            return self.json({"expressions": expressions}, status_code=200)
        except Exception as e:
            return self.json_message(f"Errore interno: {e!s}", 500)

    async def post(self, request):
        try:
            data = await request.json()
        except Exception:
            return self.json_message("Payload JSON non valido", 400)
        cmd = data.get("do")
        name = data.get("name")
        sequence = data.get("sequence")
        choice = data.get("choice")
        order = data.get("order")
        iteration = data.get("iteration")
        conditional = data.get("conditional")

        # Comandi di debug
        if cmd is not None:
            if "delete" in cmd:
                await self.task_expression.delete_store()
            elif "print" in cmd:
                await self.task_expression.print_store()
            elif "reload" in cmd:
                await self.task_expression.reload_automations()
            elif "validate" in cmd:
                automation = data.get("automation")
                try:
                    await self.task_expression.repair_automation_links(automation)
                except ValueError as e:
                    return self.json_message(str(e), 400)
                except Exception as e:
                    return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Comando '{cmd}' eseguito con successo", 200)

        if not isinstance(name, str):
            return self.json_message("Campo 'name' mancante o non valido", 400)

        if sequence is not None:
            if not isinstance(sequence, list) or not all(
                is_valid_expression_element(i) for i in sequence
            ):
                return self.json_message(
                    "Campo 'sequence' deve essere una lista di automazioni o scelte inline o espresse",
                    400,
                )
            try:
                await self.task_expression.create_sequence(name, sequence)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Sequenza '{name}' creata con successo", 200)

        if choice is not None:
            if not isinstance(choice, list) or not all(
                is_valid_expression_element(i) for i in choice
            ):
                return self.json_message(
                    "Campo 'choice' deve essere una lista di automazioni o espressioni annidate",
                    400,
                )
            try:
                await self.task_expression.create_choice(name, choice)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Scelta '{name}' creata con successo", 200)

        if order is not None:
            if not isinstance(order, list) or not all(
                is_valid_expression_element(i) for i in order
            ):
                return self.json_message(
                    "Campo 'order' deve essere una lista di automazioni o espressioni annidate",
                    400,
                )
            try:
                await self.task_expression.create_order(name, order)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Ordine '{name}' creato con successo", 200)

        if iteration is not None:
            if not isinstance(iteration, dict):
                return self.json_message(
                    "Campo 'iteration' deve essere un oggetto contenente 'n_steps' e 'expression'",
                    400,
                )
            n_steps = iteration.get("n_steps")
            expression = iteration.get("expression")

            if not (isinstance(n_steps, int) and n_steps > 0):
                return self.json_message(
                    "'n_steps' deve essere un intero positivo", 400
                )

            if not (isinstance(expression, str) or isinstance(expression, dict)):
                return self.json_message(
                    "'expression' deve essere una automazione (stringa) o una espressione (dict)",
                    400,
                )

            try:
                await self.task_expression.create_iteration(name, iteration)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Iterazione '{name}' creata con successo", 200)

        if conditional is not None:
            # Nessuna validazione, viene passato direttamente l'oggetto condition
            try:
                await self.task_expression.create_conditional(name, conditional)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(
                    f"Errore interno: {e!s}", 500
                )  # TODO J - What is !s ?
            return self.json_message(f"Condizione '{name}' creata con successo", 200)

        return self.json_message(
            "Fornire il campo 'sequence', 'choice', 'order', 'iteration' o 'conditional'",
            400,
        )

    async def delete(self, request):
        """Cancella una sequenza, una scelta, un ordine, una iterazione o una condizione"""
        try:
            data = await request.json()
        except Exception:
            return self.json_message(f"Payload JSON non valido for request:{request.body}", 400)

        sequence = data.get("sequence")
        choice = data.get("choice")
        order = data.get("order")
        iteration = data.get("iteration")
        conditional = data.get("conditional")

        if sequence is not None:
            try:
                await self.task_expression.delete_sequence(sequence)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(
                f"Sequenza '{sequence}' eliminata con successo", 200
            )

        if choice is not None:
            try:
                await self.task_expression.delete_choice(choice)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Scelta '{choice}' eliminata con successo", 200)

        if order is not None:
            try:
                await self.task_expression.delete_order(order)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(f"Ordine '{order}' eliminato con successo", 200)

        if iteration is not None:
            try:
                await self.task_expression.delete_iteration(iteration)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(
                f"Iterazione '{iteration}' eliminata con successo", 200
            )

        if conditional is not None:
            try:
                await self.task_expression.delete_conditional(conditional)
            except ValueError as e:
                return self.json_message(str(e), 400)
            except Exception as e:
                return self.json_message(f"Errore interno: {e!s}", 500)
            return self.json_message(
                f"Condizione '{conditional}' eliminata con successo", 200
            )

        return self.json_message(
            "Fornire il campo 'sequence', 'choice', 'order', 'iteration' o 'conditional'",
            400,
        )


class UpdateIotDeviceIsFramedView(HomeAssistantView):
    url = f"/api/eud4xr/{API_UPDATE_IOTDevice_VISIBILITY_FROM_UNITY}"
    name = f"api:{API_UPDATE_IOTDevice_VISIBILITY_FROM_UNITY}"
    methods = ["POST"]

    # Do a Request get to api/states
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        from .sensor import DEQUE_FRAMED_OBJECTS, DICT_IOT_DEVICES

        data = await request.json()
        try:
            iot_device = EUD4XRIOTDevice.from_dict(data)
        except Exception as e:
            raise self.json_message(e, 400)

        # update DICT_IOT_DEVICES and DEQUE_FRAMED_OBJECTS
        DICT_IOT_DEVICES[iot_device.sensor_name] = iot_device
        update_deque(DEQUE_FRAMED_OBJECTS, iot_device.sensor_name, iot_device.isInsideCamera)

        # Return all ok 200
        return self.json_message(
            f"Device '{data['sensor_name']}' updated successfully", 200
        )


#region test endpoints
class RealObjectsCapabilitiesView(HomeAssistantView):
    url = f"/api/eud4xr/{API_GET_RealObjects_Capabilities}"
    name = f"api:{API_GET_RealObjects_Capabilities}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        real_objects = await get_devices_data(self.hass)

        def map_real_devices(data: dict) -> dict:
            output = {}

            devices = data.get("real_objects", {})

            for device_name, device_info in devices.items():
                fullname = f"The {device_name}"

                variables = []
                actions = []

                for entity in device_info.get("entities", []):
                    # Collect friendly_name if present
                    friendly_name = entity.get("attributes", {}).get("friendly_name")
                    if friendly_name:
                        variables.append(friendly_name)

                    # Collect services if present
                    entity_services = entity.get("services", [])
                    actions.extend(entity_services)

                output[device_name] = {
                    "Fullname": fullname,
                    "Variables": variables,
                    "Actions": actions
                }

            return output
        return self.json({**map_real_devices(real_objects)})

class TestUnityServer_ExistingEndpointView(HomeAssistantView):
    API_GET_ECA_CAPABILITIES = "test"
    url = f"/api/eud4xr/{API_GET_ECA_CAPABILITIES}"
    name = f"api:{API_GET_ECA_CAPABILITIES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        import aiohttp
        # Do an HTTP GET Request to "http://192.168.1.18:8080/api/hello"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                META_UNITY_SERVER_IP + API_UNITY_TEST
            ) as response:
                # Raise exception if status >= 400
                response.raise_for_status()

                # Get response as text
                data = await response.text()
                print("Response:", data)

                # if code is 200, return the data
                if response.status == 200:
                    return self.json_message(data, 200)
                # Otherwise return bad request
                return self.json_message("Failed to retrieve capabilities", 500)
        print("BYE")


class TestUnityServer_NonExistingEndPointView(HomeAssistantView):
    API_GET_ECA_CAPABILITIES = "test-endpoint-non-existing"
    url = f"/api/eud4xr/{API_GET_ECA_CAPABILITIES}"
    name = f"api:{API_GET_ECA_CAPABILITIES}"
    methods = ["GET"]

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        print("WTF ARE THE LOGS?")
        import aiohttp

        # Do an HTTP GET Request to "http://192.168.1.18:8080/api/hello"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                META_UNITY_SERVER_IP + "/api/test-non-existing-point"
            ) as response:
                # Raise exception if status >= 400
                response.raise_for_status()

                # Get response as text
                data = await response.text()
                print("Response:", data)

                # if code is 200, return the data
                if response.status == 200:
                    return self.json_message(data, 200)
                # Otherwise return bad request
                return self.json_message("Failed to retrieve capabilities", 500)
        print("BYE")
#endregion