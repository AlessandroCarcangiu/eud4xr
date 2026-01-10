# ruff: noqa

import inspect
import logging
import re
import time
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import RegistryEntry

from .eca_classes import Vector3


from .const import (
    CONF_SERVICE_UPDATE_FROM_UNITY_SUBJECT,
    CONF_SERVICE_UPDATE_FROM_UNITY_VERB,
    DOMAIN,
    SERVICE_SEND_REQUEST,
)

_LOGGER = logging.getLogger(__name__)


class ECAEntity(Entity):
    def __init__(
        self, eca_script: str, game_object: str, unity_id: str, hass: HomeAssistant
    ) -> None:
        super().__init__()
        if not unity_id:
            unity_id = f"{time.time()}"
        self._eca_script = eca_script
        self._game_object = game_object
        self._unique_id = unity_id
        self._name = game_object
        self._unity_name = game_object.lower().split("@")[0]
        self._hass = hass
        self._state = "active"
        self._last_updates = dict()
        self._attr_extra_state_attributes = dict()

    @property
    def should_poll(self):
        return False

    @property
    def device_class(self):
        return "eca_entity"

    @property
    def eca_script(self):
        return self._eca_script

    @property
    def game_object(self):
        return self._game_object

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def last_updates(self) -> dict:
        return self._last_updates

    def set_last_updates(self, attribute: str, ts: int) -> None:
        self._last_updates[attribute] = ts

    @property
    def state(self):
        """Return the state of the game object."""
        return self._state

    def get_description(self) -> str:
        return getattr(self, "_label", self.__class__.__doc__)

    def get_properties(self) -> list:
        properties = list()
        signature = inspect.signature(self.__init__)
        for param_name, param in list(
            filter(
                lambda x: x[0] not in ["self", "kwargs"], signature.parameters.items()
            )
        ):
            valore = getattr(self, param_name)
            data = {
                "name": param_name,
                "type": getattr(
                    param.annotation, "__name__", str(param.annotation)
                ),
                "current value": valore,
            }
            class_attr = getattr(type(self), param_name, None)
            if isinstance(class_attr, property) and hasattr(class_attr.fget, "_label"):
                data["description"] = class_attr.fget._label

            properties.append(
                data
            )
        return properties

    def get_services(self) -> list:
        services = list()
        eca_script_methods = [
            (name, method)
            for name, method in inspect.getmembers(self.__class__, inspect.isfunction)
            if hasattr(method, "_is_eca_script_action")
        ]
        from .utils import Service

        for name, method in eca_script_methods:
            service_params = dict()
            signature = inspect.signature(method).parameters.items()
            for param_name, param in list(filter(lambda x: x[0] != "self", signature)):
                service_params[param_name] = param.annotation #str(param.annotation.__name__)

            dry_descr = getattr(method, "_label", "")
            if not dry_descr:
                dry_descr = inspect.getdoc(method)
                if not dry_descr:
                    dry_descr = ""
                dry_descr = dry_descr.replace('\n', ' ').replace('\t', ' ').replace('\\"', '"')
                dry_descr = re.sub(r'<[^>]+>', '', dry_descr)
                dry_descr = re.sub(r'\s+', ' ', dry_descr)
                dry_descr = re.sub(r'\s+([,.!?;:])', r'\1', dry_descr).strip()
            s = Service(
                method=method,
                eca_action=f"eud4xr.{name.replace('async_','')}",
                params=service_params,
                description=dry_descr,
                object_name=self._unity_name,
            ).to_dict()
            services.append(
                {
                    #"service_of_component": self.game_object,
                    **s,
                }
            )
        return services

    def to_dict(self, hass: HomeAssistant) -> dict:
        description = self.get_description()
        properties = self.get_properties()
        services = self.get_services()
        return {
            "description": description,
            "properties": properties,
            "services": services
        }

    def generate_payload(
        self,
        verb: str,
        variable: str = "",
        modifier: str = "",
        on_event: bool = False,
        is_passive: bool = False,
        **kwargs,
    ) -> dict:
        data = {CONF_SERVICE_UPDATE_FROM_UNITY_VERB: verb}
        if variable:
            data["variable"] = variable.lower()
        if modifier:
            data["modifier"] = modifier.lower()

        data[CONF_SERVICE_UPDATE_FROM_UNITY_SUBJECT] = (
            self.game_object.lower().split("@")[0] if on_event else self.game_object
        )
        paramater_to_send = None
        for k, v in kwargs.items():
            if v:
                if isinstance(v, RegistryEntry):
                    #paramater_to_send = str(v.original_name.split("@")).lower() if on_event or getattr(v, "original_name") else str(v.game_object)
                    paramater_to_send = str(v.original_name) if on_event or getattr(v, "original_name") else str(v.game_object)
                else:
                    if isinstance(v, str):
                        v = v.lower()
                    value_to_string = ", ".join([str(i).lower() for i in v]) if isinstance(v, list) else str(v).lower()
                    paramater_to_send = v.to_value() if hasattr(v, "to_value") else v if on_event else value_to_string
                # remove @
                if on_event:
                    paramater_to_send = paramater_to_send.split("@")[0]
        if paramater_to_send:
            if variable and modifier:
                data["value"] = paramater_to_send
            else:
                if not is_passive:
                    data["obj"] = paramater_to_send
                else:
                    data["obj"] = data["subject"]
                    data["subject"] = paramater_to_send
        return data

    async def action(self, **kwargs) -> None:
        data = self.generate_payload(**kwargs)
        # send update to unity
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_REQUEST,
            data,
        )
        _LOGGER.info(f"Performed a service: {data}")

    def on_action(self, **kwargs) -> None:
        data = self.generate_payload(on_event=True, **kwargs)
        # generate ha event
        self.hass.bus.fire(DOMAIN, data)
        _LOGGER.info(f"Generated a new eud4xr event: {data}")


class EUD4XRIOTDevice:

    def __init__(self, sensor_name: str, position: Vector3, isInsideCamera: bool) -> None:
        self._sensor_name = sensor_name.lower()
        self._position = position
        self._isInsideCamera = isInsideCamera

    @property
    def sensor_name(self) -> str:
        return self._sensor_name

    @property
    def position(self) -> dict:
        return self._position.to_value()

    def set_position(self, new_position: Vector3) -> None:
        self._position = new_position

    @property
    def isInsideCamera(self) -> bool:
        return self._isInsideCamera

    def set_isInsideCamera(self, new_isInsideCamera: bool) -> None:
        self._isInsideCamera = new_isInsideCamera

    @classmethod
    def from_dict(cls, data: dict) -> 'EUD4XRIOTDevice':
        if not isinstance(data, dict):
            raise Exception("Invalid data: expected a JSON object")

        required_keys = {"sensor_name", "isInsideCamera", "position"}
        if not required_keys.issubset(data):
            raise Exception(
                "Missing one or more required keys. The required keys are: "
                + ", ".join(required_keys),
                400,
            )

        if not isinstance(data["sensor_name"], str):
            raise Exception(
                "Invalid type for 'sensor_name': expected string"
            )

        if not isinstance(data["isInsideCamera"], bool):
            raise Exception(
                "Invalid type for 'isInsideCamera': expected boolean"
            )

        position = Vector3.validate(data["position"])

        return cls(data["sensor_name"], position, data["isInsideCamera"])
