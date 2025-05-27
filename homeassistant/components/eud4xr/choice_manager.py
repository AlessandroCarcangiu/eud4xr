import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Schema per le singole scelte
CHOICE_SCHEMA = vol.Schema({
    vol.Required("name"): str,
    vol.Required("automation_id"): str,
})

# Schema per la registrazione scelte
REGISTER_CHOICES_SCHEMA = vol.Schema({
    vol.Required("context_id"): str,
    vol.Required("choices"): vol.All(cv.ensure_list, [CHOICE_SCHEMA]),
})

# Schema per eseguire la scelta
PERFORM_CHOICE_SCHEMA = vol.Schema({
    vol.Required("context_id"): str,
    vol.Required("selected_choice"): str,
})

class ChoiceManager:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._choices = {}

    def register_choices(self, call: ServiceCall):
        context_id = call.data["context_id"]
        choices = call.data["choices"]
        self._choices[context_id] = choices
        _LOGGER.info(f"Choices registered for context '{context_id}': {choices}")

    async def perform_choice(self, call: ServiceCall):
        context_id = call.data["context_id"]
        selected_choice = call.data["selected_choice"]
        choices = self._choices.get(context_id)
        if not choices:
            _LOGGER.error(f"No choices found for context '{context_id}'")
            return

        choice = next((c for c in choices if c["name"] == selected_choice), None)
        if not choice:
            _LOGGER.error(f"Choice '{selected_choice}' not found in context '{context_id}'")
            return

        automation_id = choice["automation_id"]
        _LOGGER.info(f"Triggering automation '{automation_id}' for choice '{selected_choice}' in context '{context_id}'")
        await self.hass.services.async_call(
            domain="automation",
            service="trigger",
            service_data={"entity_id": automation_id},
            blocking=True,
        )

    import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Schema per le singole scelte
CHOICE_SCHEMA = vol.Schema({
    vol.Required("name"): str,
    vol.Required("automation_id"): str,
})

# Schema per la registrazione scelte
REGISTER_CHOICES_SCHEMA = vol.Schema({
    vol.Required("context_id"): str,
    vol.Required("choices"): vol.All(cv.ensure_list, [CHOICE_SCHEMA]),
})

# Schema per eseguire la scelta
PERFORM_CHOICE_SCHEMA = vol.Schema({
    vol.Required("context_id"): str,
    vol.Required("selected_choice"): str,
})

class ChoiceManager:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._choices = {}

    def register_choices(self, call: ServiceCall):
        context_id = call.data["context_id"]
        choices = call.data["choices"]
        self._choices[context_id] = choices
        _LOGGER.info(f"Choices registered for context '{context_id}': {choices}")

    async def perform_choice(self, call: ServiceCall):
        context_id = call.data["context_id"]
        selected_choice = call.data["selected_choice"]
        choices = self._choices.get(context_id)
        if not choices:
            _LOGGER.error(f"No choices found for context '{context_id}'")
            return

        choice = next((c for c in choices if c["name"] == selected_choice), None)
        if not choice:
            _LOGGER.error(f"Choice '{selected_choice}' not found in context '{context_id}'")
            return

        automation_id = choice["automation_id"]
        _LOGGER.info(f"Triggering automation '{automation_id}' for choice '{selected_choice}' in context '{context_id}'")
        await self.hass.services.async_call(
            domain="automation",
            service="trigger",
            service_data={"entity_id": automation_id},
            blocking=True,
        )

