from functools import wraps
import inspect

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .config_validation import get_unity_entity
from .eca_classes import ECAPosition, ECARotation, ECAScale
from .entity import ECAEntity


def eca_script_action(verb: str, variable_name: str = "", modifier_string: str = ""):
    def decorator(func):
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


# def eca_script_action(fun: callable):
#     fun._is_eca_script_action = True
#     return fun


class MappedClass:
    def __init__(self, cls: callable, service_definitions: dict) -> None:
        self._cls = cls
        self._service_definitions = service_definitions

    @property
    def cls(self) -> str:
        return self._cls

    @property
    def service_definitions(self) -> dict:
        return self._service_definitions

    def __str__(self) -> str:
        return f"{self.cls} - {self.service_definitions}"


class MappedClasses:
    ECA_SCRIPTS = None

    @classmethod
    def get_eca_scripts(cls):
        return MappedClasses.ECA_SCRIPTS

    @classmethod
    def mapping_classes(cls, module, hass) -> dict:
        results = dict()
        for name, clazz in inspect.getmembers(module, inspect.isclass):
            register_definition = cls.__mapping_methods(clazz, hass)
            results[name] = MappedClass(clazz, register_definition)
        MappedClasses.ECA_SCRIPTS = results
        return MappedClasses.ECA_SCRIPTS

    @staticmethod
    def __is_built_in_class(type_class: callable) -> bool:
        return type_class in [str, int, float, dict]

    @staticmethod
    def __is_entity_class(type_class: callable) -> bool:
        return type_class == ECAEntity or issubclass(type_class, ECAEntity)

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
                print(f"{class_type}")
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
    def __mapping_methods(cls, clazz, hass):
        methods = list()
        eca_script_methods = [
            (name, method)
            for name, method in inspect.getmembers(clazz, inspect.isfunction)
            if hasattr(method, "_is_eca_script_action")
        ]
        print(eca_script_methods)
        for name, method in eca_script_methods:
            signature = inspect.signature(method).parameters.items()
            print(f"{name} - {method}")
            params = dict()
            for param_name, param in list(filter(lambda x: x[0] != "self", signature)):
                value = cls.__mapping_parameter(param_name, param, hass)
                params[param_name] = value
            methods.append(
                (
                    name
                    if not name.startswith("async_")
                    else name.replace("async_", "", 1),
                    params,
                    name,
                )
            )
        return methods
