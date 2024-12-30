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


class ECAAction:

    def __init__(self, verb: str, subject: str, obj: object=None, variable: object=None, modifier: str=None, value: str=None) -> None:
        self.verb = verb
        self.subject = subject
        self.obj = obj
        self.variable = variable
        self.modifier = modifier
        self.value = value

    def to_dict(self, to_lower: bool = False, remove_nullable: bool = False) -> dict:
        if to_lower:
            for i in ["verb", "subject", "variable", "modifier", "obj", "value"]:
                v = getattr(self, i)
                if isinstance(v, str):
                    setattr(self, i, v.lower())
        data = {
            "verb": self.verb,
            "subject": self.subject,
            "obj": self.obj,
            "variable": self.variable,
            "modifier": self.modifier,
            "value": self.value
        }
        for k in list(data.keys()):
            if not data[k]:
                data.pop(k)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ECAAction':
        return cls(
            verb=data.get("verb"),
            subject=data.get("subject"),
            obj=data.get("obj"),
            variable=data.get("variable"),
            modifier=data.get("modifier"),
            value=data.get("value"),
        )

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict, is_trigger: bool = False) -> 'ECAAction':
        '''
            It converts eca actions from hass format to natural language:
                verb: {verb in natural language},
                subject: {game_object_name@eca_script},
                obj:
                variable_name: {variable_name},
                modifier_string: {modifier_string}
        '''
        # an eca action expressed as trigger is an event very similar to the ECARules4All's action definition (it contains verb, subject, ecc.)
        # consequently, we just extract the event_data and send it to Unity
        if is_trigger:
            # trigger's subject and param does not have reference to the sensor
            kwargs = data[0]["event_data"] if isinstance(data, list) else data["event_data"]
            method = None
            try:
                # active action - get subject and service
                entity_id = get_entity_id_by_game_object_and_verb(hass, kwargs['subject'], kwargs['verb'])
                kwargs["subject"] = convert_subject_to_unity(hass, entity_id)
                method, sig = cls.get_service_method(hass, entity_id, kwargs["verb"])
            except:
                # passive action
                passive_entity_id = get_entity_id_by_game_object_and_verb(hass, kwargs['variable_name'], kwargs['verb'])
                _, sig = cls.get_service_method(hass, passive_entity_id, kwargs["verb"])
                param = next (p for n, p in sig.parameters.items() if n != "self")
                entity_id = get_entity_id_by_game_object_and_eca_script(hass, kwargs['subject'], param.annotation.__name__.lower())
                kwargs["subject"] = entity_id

            if method:
                # get method's kwargs
                other_params = getattr(method, "kwargs")
                params = sig.parameters.items()
                if params:
                    v = None
                    for param_name, param in sig.parameters.items():
                        if param_name != "self":
                            v = data["data"][param_name]
                    if v:
                        if kwargs.get("variable", None):
                            kwargs["value"] = v
                        else:
                            kwargs["obj"] = v
            else:
                kwargs["variable"] = cls.convert_variable_to_unity(hass, kwargs["variable"])
            return cls(
                **kwargs
            )
        # an eca action expressed in the service form requires different operation in order to obtain
        # its representation in ECARules4All
        subject_name = data["data"]["entity_id"]
        service_name = data["action"].split(".")[-1]
        subject = convert_subject_to_unity(hass, subject_name)
        method, sig = cls.get_service_method(hass, subject_name, service_name)
        # populate params
        v = None
        modifier = None
        variable = None
        if method:
            other_params = getattr(method, "kwargs")
            is_passive = getattr(method, "is_passive")
            # passive action
            if is_passive:
                param_name = next(k for k,v in sig.parameters.items() if k != "self")
                variable = subject
                verb = other_params["verb"]
                subject = convert_subject_to_unity(hass, data["data"][param_name])
            # active action
            else:
                # other action parameters
                other_params = getattr(method, "kwargs")
                verb = other_params["verb"]
                variable = other_params["variable_name"]
                modifier = other_params["modifier_string"]
                if sig:
                    params = sig.parameters.items()
                if params:
                    for param_name, param in sig.parameters.items():
                        if param_name != "self":
                            v = data["data"][param_name]
        else:
            verb = service_name.replace("_", " ")
        # define kwargs
        kwargs = {
            "subject":subject,
            "verb": verb
        }
        if variable:
            kwargs["variable"] = variable
        if modifier:
            kwargs["modifier"] = modifier
        if v:
            if variable and modifier:
                kwargs["value"] = v
            else:
                kwargs["obj"] = v
        return cls(**kwargs)

    @staticmethod
    def convert_variable_to_unity(hass: HomeAssistant, variable_name: str, variable_type: callable = None) -> str:
        # get the first entity of other group
        entity = get_first_entity_by_group(hass, variable_name)
        unity_name = convert_subject_to_unity(hass, entity)
        if not variable_type:
            variable_name = unity_name
        else:
            variable_name = f"{unity_name.split("@")[0]}@{variable_type.annotation.__name__}"
        return variable_name

    @staticmethod
    def get_service_method(hass: HomeAssistant, entity_id: str, service: str) -> tuple:
        entity_instance = get_entity_instance_by_entity_id(hass, entity_id)
        method = getattr(entity_instance, f"async_{service}", None)
        signature_method = inspect.signature(method) if method else None
        return method, signature_method
