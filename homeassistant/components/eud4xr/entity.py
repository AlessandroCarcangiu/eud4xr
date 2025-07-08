import inspect
import logging
import time
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import RegistryEntry


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

    def to_dict(self, hass) -> dict:
        # properties
        properties = []
        signature = inspect.signature(self.__init__)
        for param_name, param in list(filter(lambda x: x[0] not in ["self", "kwargs"], signature.parameters.items())):
            valore = getattr(self, param_name)
            properties.append({
                "name": param_name,
                "type": getattr(param.annotation, "__name__", str(param.annotation)),
                "current value": valore
            })
        # services
        services = {}
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
                #value = self.__mapping_parameter(param_name, param, hass)
                service_params[param_name] = str(param.annotation.__name__)

            services[getattr(method, "kwargs")["verb"]] = Service(
                method = method,

                eca_action=f"eud4xr.{name.replace('async_','')}",

                params=service_params,

                description=inspect.getdoc(method)
            ).to_dict()


        return {
            "properties": properties,
            "services": services
        }

    def generate_payload(
        self,
        verb: str,
        variable: str = "",
        modifier: str = "",
        on_event: bool = False,
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
                    paramater_to_send = (
                        str(v.original_name.split("@")).lower()
                        if on_event
                        else str(v.game_object)
                    )
                else:
                    if isinstance(v, str):
                        v = v.lower()

                    value_to_string = (
                        ", ".join([str(i).lower() for i in v])
                        if isinstance(v, list)
                        else str(v).lower()
                    )
                    if on_event:
                        print(f"v: {v} - {hasattr(v, 'to_value')}")
                    paramater_to_send = v.to_value() if hasattr(v, "to_value") else v if on_event else value_to_string
        if paramater_to_send:
            if variable and modifier:
                data["value"] = paramater_to_send
            else:
                data["obj"] = paramater_to_send
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
