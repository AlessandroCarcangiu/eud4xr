import inspect
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from .const import IS_DEBUG
from .sensor import get_classes_subclassing


def find_group(hass: HomeAssistant, group_id: str) -> State:
    group = hass.states.get(f"group.{group_id}")
    if group:
        return group
    return None


def get_first_entity_by_group(hass: HomeAssistant, group_id: str) -> any:
    group = find_group(hass, group_id)
    entities = group.attributes.get("entity_id", [])
    return entities[0] if entities else None


def get_entity_state_by_id(hass: HomeAssistant, entity_id: str) -> State:
    entity_state = hass.states.get(entity_id)
    if entity_state:
        return entity_state
    raise Exception(f"Sensor {entity_id} does not exist")


def get_entity_id_by_game_object_and_property(hass: HomeAssistant, game_object_name: str, property: str) -> str:
    # get group
    group = find_group(hass, game_object_name)
    if not group:
        raise Exception(f"Group {game_object_name} does not exist")
    # search the entity that has property
    for entity_id in group.attributes.get("entity_id", []):
        entity_state = hass.states.get(entity_id)
        if hasattr(entity_state, 'attributes'):
            if property in entity_state.attributes:
                return entity_id
    raise Exception(f"Group {game_object_name} does not have an attribute {property}")


def get_entity_id_by_game_object_and_verb(hass: HomeAssistant, game_object_name: str, verb: str) -> str:
    group = find_group(hass, game_object_name)

    for entity_id in group.attributes.get("entity_id", []):
        entity_state = hass.states.get(entity_id)
        entity_instance = get_entity_instance_by_entity_id(hass, entity_id)
        methods = inspect.getmembers(entity_instance)
        for name, method in methods:
            decorator_args = getattr(method, "kwargs", {})
            if "verb" in decorator_args and decorator_args["verb"] == verb:
                return entity_id
    raise Exception(f"Group {game_object_name} does not have a verb {verb}")


def get_entity_instance_by_entity_id(hass: HomeAssistant, entity_id: str) -> any:
    entity_instance = hass.data['entity_components']['sensor'].get_entity(entity_id)
    if entity_instance:
        return entity_instance
    raise Exception(f"Entity {entity_id} does not exists")


def get_entity_id_by_game_object_and_eca_script(hass: HomeAssistant, game_object_name: str, eca_script: str) -> str:
    group = find_group(hass, game_object_name)

    for entity_id in group.attributes.get("entity_id", []):
        entity_instance = get_entity_instance_by_entity_id(hass, entity_id)
        if entity_instance.eca_script.lower() == eca_script:
            return entity_instance.unique_id
    raise Exception(f"Group {game_object_name} isnot associated to script {eca_script}")


def get_entity_instance_and_method_signature_by_structured_language(
        hass: HomeAssistant, game_object_name: str, verb: str, variable: str = None, modifier: str = None) -> str:
    verb = verb.replace("_", " ")

    # get group
    group = find_group(hass, game_object_name)
    if not group:
        raise Exception(f"Group {game_object_name} does not exist")
    # search the entity that has property
    for entity_id in group.attributes.get("entity_id", []):
        entity_instance = get_entity_instance_by_entity_id(hass, entity_id)
        async_methods = [
            (name, member)
            for name, member in inspect.getmembers(entity_instance)
            if name.startswith('async_')
        ]
        for name, method in async_methods:
            d_kwargs = getattr(method, "kwargs", {})
            if d_kwargs:
                v = d_kwargs["verb"]
                var = d_kwargs.get("variable", None)
                m = d_kwargs.get("modifier", None)
                if (not var and v == verb) or (v==verb and var==variable and m == modifier):
                    return entity_instance, name, method, inspect.signature(method)
    return None, None, None, None


def get_method_by_eca_script_name(eca_script: str, verb: str) -> any:
    clz = get_classes_subclassing(eca_script)
    return getattr(clz, verb, None)


def convert_subject_to_unity(hass: HomeAssistant, entity_id: str) -> str:
    entity_state = get_entity_state_by_id(hass, entity_id)
    return entity_state.attributes.get('friendly_name')


def get_sensor_state_by_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    group = find_group(hass, entity_id)

    entity = hass.states.get(entity_id)
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(entity_id)
    sensor_component = hass.data.get("sensor")

    if group:
        for entity_id in group.attributes.get("entity_id", []):
            pass



def find_sensor(hass, sensor_id: str):
    if not sensor_id.startswith("sensor."):
        sensor_id = f"sensor.{sensor_id.lower()}"

    entity = hass.states.get(sensor_id)
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(sensor_id)
    sensor_component = hass.data.get("sensor")

    sensor_entity = next(
        (
            entity
            for entity in sensor_component.entities
            if entity.entity_id == sensor_id
        ),
        None,
    )

    return (
        (
            sensor_entity,
            entity,
        )
        if entity and entity_entry and sensor_component
        else (None, None)
    )


def getattr_case_insensitive(obj, attr_name):
    attributes = dir(obj)
    # Trova un attributo con nome case-insensitive
    for attribute in attributes:
        if attribute.lower() == attr_name.lower():
            return getattr(obj, attribute)
    raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{attr_name}' (case-insensitive)")

# TODO (handling multiple results)
def find_sensor_and_service(hass, subject: str, verb: str) -> tuple:
    from .sensor import CURRENT_MODULE

    # retrieve group, and its sensors, from subject
    group = find_group(hass, subject)

    if not group:
        raise Exception(f"ERROR - Sensor {subject} does not exist")

    for sensor_id in group.attributes.get("entity_id", []):
        sensor_class_name = sensor_id.split("_")[-1]
        sensor = getattr_case_insensitive(CURRENT_MODULE, sensor_class_name)
        if sensor:
            service = getattr(sensor, f"async_{verb.replace(' ', '_')}", None)
            if service and inspect.isfunction(service):
                return sensor, service, inspect.signature(service)
    return None, None, None

def get_first_valid_parameter(signature) -> tuple:
    param = next(
        (param for name, param in signature.parameters.items() if name not in ('self', 'cls')),
        None
    )
    param_name = None
    param_type = None
    if param is not None:
        param_name = param.name
        param_type = param.annotation if param.annotation != inspect.Parameter.empty else None
    return param_name, param_type


def get_unity_sensor_name(hass, sensor_id) -> str:
    _, state  = find_sensor(hass, sensor_id)
    if state:
        return state.attributes.get('friendly_name')
    raise Exception(f"Sensor {sensor_id} not found")


# TODO (handling multiple results)
def find_sensor_and_property(hass, subject: str, property: str) -> tuple:
    from .sensor import CURRENT_MODULE

    # retrieve group, and its sensors, from subject
    group = find_group(hass, subject)

    if not group:
        raise Exception(f"ERROR - Sensor {subject} does not exist")

    for sensor_id in group.attributes.get("entity_id", []):
        sensor_class_name = sensor_id.split("_")[-1]
        sensor = getattr_case_insensitive(CURRENT_MODULE, sensor_class_name)
        if sensor:
            property = getattr(sensor, property, None)
            if property:
                return sensor, inspect.getmembers(property)
