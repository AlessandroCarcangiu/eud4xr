import inspect
import textwrap
import voluptuous as vol
from collections import deque
from functools import wraps
from typing import Tuple
from homeassistant.helpers import config_validation as cv, entity_registry as er
from .config_validation import get_unity_entity
from .eca_classes import ECAPosition, ECARotation, ECAScale
from .entity import ECAEntity


def eca_script_action(verb: str, variable_name: str = "", modifier_string: str = "", is_passive: bool = False):
    def decorator(func):
        setattr(func, "kwargs", {"verb": verb, "variable_name":variable_name, "modifier_string": modifier_string})
        setattr(func, "is_passive", is_passive)
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            result = await func(self, *args, **kwargs)
            await self.action(
                verb=verb,
                variable_name=variable_name,
                modifier_string=modifier_string,
                **kwargs,
            )
            self.on_action(
                verb=verb,
                variable_name=variable_name,
                modifier_string=modifier_string,
                **kwargs,
            )
            return result
        wrapper._is_eca_script_action = True
        return wrapper
    return decorator


def update_deque(circular_list: deque):
    def decorator(func):
        @wraps(func)
        def wrapper(self, value: any):
            game_object_name = self.game_object.split("@")[0]
            if game_object_name in circular_list:
                circular_list.remove(game_object_name)
            circular_list.append(game_object_name)
            return func(self, value)
        return wrapper
    return decorator


class Service:

    def __init__(self, eca_action: dict, params: dict, description: str) -> None:
        self.eca_action = eca_action
        self.params = params
        self.description = description

    def to_dict(self):
        return {
            "eca_action": self.eca_action,
            "params": self.params,
            "description": self.description,
        }


class MappedClass:
    def __init__(self, cls: callable, properties: list, description_services: list, services: list[Service], description: str) -> None:
        self._cls = cls
        self._properties = properties
        self._description = description
        self._description_services = description_services
        self._services = services

    @property
    def cls(self) -> str:
        return self._cls

    @property
    def properties(self) -> str:
        return self._properties

    @property
    def service_definitions(self) -> list:
        return self._description_services

    @property
    def services(self) -> list[Service]:
        return self._services

    @property
    def description(self) -> str:
        return self._description

    def __str__(self) -> str:
        return f"{self.cls} - {self.service_definitions}"

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            #"properties": self.properties,
            "services": self.services,
        }


class MappedClasses:
    ECA_SCRIPTS = None

    @classmethod
    def get_eca_scripts(cls):
        return MappedClasses.ECA_SCRIPTS

    @classmethod
    def mapping_classes(cls, hass) -> dict:
        from .sensor import CURRENT_MODULE

        results = dict()
        for name, clazz in inspect.getmembers(CURRENT_MODULE, inspect.isclass):
            results[name] = cls.__mapping_class(hass, clazz)
        MappedClasses.ECA_SCRIPTS = results
        return MappedClasses.ECA_SCRIPTS

    @staticmethod
    def __is_built_in_class(type_class: callable) -> bool:
        return type_class in [str, int, float, dict]

    @staticmethod
    def __is_entity_class(type_class: callable) -> bool:
        return type_class == ECAEntity or issubclass(type_class, ECAEntity)

    @classmethod
    def __mapping_class(cls, hass, clazz: callable) -> MappedClass:
        # get class' properties
        properties = cls.__mapping_properties(clazz)
        # get class' services
        description_services, list_services = cls.__mapping_methods(clazz, hass)
        docstring = inspect.getdoc(clazz)
        return MappedClass(clazz, properties, description_services, list_services, docstring)

    @classmethod
    def __mapping_parameter(cls, name: str, param, hass) -> any:
        # (str, int, float, dict)
        if cls.__is_built_in_class(param.annotation):
            return param.annotation
        # List[something]
        if getattr(param.annotation, "__origin__", None) == list:
            args = getattr(param.annotation, "__args__", [None])
            values = list()
            for class_type in args:
                val = str
                if cls.__is_built_in_class(class_type):
                    val = class_type
                if hasattr(class_type, "validate"):
                    val = class_type.validate
                if cls.__is_entity_class(class_type):
                    val = get_unity_entity(hass)
                values.append(val)
            return vol.All(cv.ensure_list, values)
        # ECAClasses
        if hasattr(param.annotation, "validate"):
            class_type = None
            if param.annotation in [ECAPosition, ECARotation, ECAScale]:
                class_type = dict
            else:
                class_type = str
            return vol.All(vol.Coerce(class_type), param.annotation.validate)
        # ECAScript
        if cls.__is_entity_class(param.annotation):
            return vol.All(vol.Coerce(str), get_unity_entity(hass))
        # default
        return str

    @classmethod
    def __mapping_methods(cls, clazz, hass) -> Tuple[list, list]:
        list_methods = list()
        list_services = list()

        eca_script_methods = [
            (name, method)
            for name, method in inspect.getmembers(clazz, inspect.isfunction)
            if hasattr(method, "_is_eca_script_action")
        ]

        for name, method in eca_script_methods:
            signature = inspect.signature(method).parameters.items()

            service_params = dict()
            description_params = dict()
            for param_name, param in list(filter(lambda x: x[0] != "self", signature)):
                value = cls.__mapping_parameter(param_name, param, hass)
                service_params[param_name] = str(param.annotation.__name__)
                description_params[param_name] = value

            # description methods
            list_methods.append(
                (
                    name
                    if not name.startswith("async_")
                    else name.replace("async_", "", 1),
                    description_params,
                    name,
                )
            )
            # services
            list_services.append(
                Service(
                    eca_action=f"eud4xr.{name.replace('async_','')}",
                    params=service_params,
                    description=inspect.getdoc(method)
                ).to_dict()
            )

        return list_methods, list_services

    @classmethod
    def __mapping_properties(cls, clazz: callable):
        init_params = list()
        signature = inspect.signature(clazz.__init__)
        for param_name, _ in list(filter(lambda x: x[0] not in ["self", "kwargs"], signature.parameters.items())):
            init_params.append(param_name)
        return init_params
