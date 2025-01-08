import inspect
from homeassistant.core import HomeAssistant
from ..const import (
    DOMAIN,
    IS_DEBUG
)
from ..hass_utils import (
    find_group,
    find_sensor,
    get_entity_state_by_id,
    get_entity_instance_and_method_signature_by_structured_language,
    get_method_by_eca_script_name,
    get_entity_instance_by_entity_id,
    get_first_entity_by_group,
    convert_subject_to_unity,
    get_entity_id_by_game_object_and_verb,
    get_entity_id_by_game_object_and_eca_script
)
from ..sensor import ECAObject, get_classes_subclassing


class YAMLAction:

    def __init__(self, subject: str, verb: str, obj: str = None, variable: str = '', modifier: str='', value: str=None) -> None:
        self.verb = verb
        self.subject = subject
        self.obj = obj
        self.variable = variable
        self.modifier = modifier
        self.value = value

    def to_dict(self) -> dict:
        data = {
            "subject": self.subject,
            "verb": self.verb,
            "obj": self.obj,
            "variable": self.variable,
            "modifier": self.modifier,
            "value": self.value,
        }
        for k in list(data.keys()):
            if not data[k]:
                data.pop(k)
            elif isinstance(data[k], str):
                data[k] = data[k].lower()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'YAMLAction':
        return cls(
            verb=data.get("verb"),
            subject=data.get("subject"),
            obj=data.get("obj"),
            variable=data.get("variable"),
            modifier=data.get("modifier"),
            value=data.get("value")
        )

    def to_yaml(self, hass: HomeAssistant, as_event: bool = False) -> dict:
        '''
            It converts eca actions from natural language to hass format.
            Action as trigger:
                platform: event
                event_type: eud4xr
                event_data:
                    verb: {verb} (name of the service without 'async'),
                    subject: {game_object_name},
                    obj: {game_object_name} or a {value},
                    variable: {variable}
                    modifier: {modifier}
                    value: {value}
            Action as service:
                action: eud4xr.{name_service}
                data:
                    entity_id: sensor.{game_object_name}_{eca_script}
                    {argument_name} (optional and get from the service): sensor.{game_object_name}_{eca_script} or a {value}
        '''
        # the next code converts game object name to a game_object@eca_script
        # eventually, it also converts the value parameter if it is a reference to an object
        # trigger -> event (because a service cannot be a trigger)
        if as_event:
            if IS_DEBUG:
                print("------------start YAMLAction - AS EVENT - to_yaml------------")
                print(f"to_dict: {self.to_dict()}")
                print("------------end YAMLAction - AS EVENT - to_yaml------------\n")
            data = self.to_dict()
            return {
                "platform": "event",
                "event_type": DOMAIN,
                "event_data": data
            }
        if IS_DEBUG:
                print("------------start YAMLAction - AS service - to_yaml------------")
                print(f"to_dict: {self.to_dict()}")
                print("------------end YAMLAction - AS service - to_yaml------------\n")

        # as service #
        data = dict()
        passive_instance = None

        active_instance, method_name, _, sig = get_entity_instance_and_method_signature_by_structured_language(
            hass, self.subject, self.verb, self.variable, self.modifier)

        # active or passive action
        if not method_name:
            # new #
            passive_instance, method_name, _, sig = get_entity_instance_and_method_signature_by_structured_language(
            hass, self.obj, self.verb, self.variable, self.modifier)
            if not method_name:
                raise Exception(f"Service {self.verb} isnot supported")

        self.verb = method_name.replace("async_", "")
        if sig.parameters.items():
            for param_name, param in sig.parameters.items():
                if param_name != 'self':
                    param_type = param.annotation.__name__.lower()
                    v = None
                    if passive_instance:
                        v = self.subject
                    elif self.value:
                        v = self.value
                    else:
                        v = self.obj
                    # a ref to a sensor or a value?
                    if param_type in get_classes_subclassing(to_string=True):
                        data[param_name] = f"sensor.{v}_{param_type}".lower()
                    else:
                        data[param_name] = v
        self.subject = f"{active_instance.entity_id}" if active_instance else f"{passive_instance.entity_id}"
        # populate yaml service
        data["entity_id"] = self.subject
        return {
            "action": f"{DOMAIN}.{self.verb}",
            "data": data
        }

    @staticmethod
    def get_service_method(hass: HomeAssistant, entity_id: str, service: str) -> tuple:
        entity_instance = get_entity_instance_by_entity_id(hass, entity_id)
        method = getattr(entity_instance, f"async_{service}", None)
        signature_method = inspect.signature(method) if method else None
        return method, signature_method
