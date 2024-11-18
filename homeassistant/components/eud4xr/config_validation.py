import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, GAME_OBJECT_NAME


def get_unity_entity(hass: HomeAssistant):
    def validate_unity_entity(value: any):
        reg = er.async_get(hass)
        if value not in reg.entities:
            raise vol.Invalid(f"Entity '{value}' does not found")
        entity = reg.entities.get(value)
        if (
            not entity.platform == DOMAIN
            and entity.original_device_class == GAME_OBJECT_NAME
        ):
            raise vol.Invalid(f"Entity {value} is not a game object")
        return entity

    return validate_unity_entity
