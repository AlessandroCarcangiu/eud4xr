import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = "eud4xr"
EVENT_STEP_COMPLETED = "sequence_step_completed"

ADD_SEQUENCE_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("sequence"): vol.All(
        cv.ensure_list,
        [vol.Schema({
            vol.Required("service"): cv.string,
            vol.Optional("data"): dict,
        })]
    ),
})


START_SEQUENCE_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string
})

REMOVE_SEQUENCE_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string
})


class SequenceManager(Entity):
    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Sequence Manager"
        self._attr_unique_id = "sequence_manager"

        self._sequences = {}
        self._current_sequence_name = None
        self._current_index = 0
        self._is_running = False

    @property
    def name(self):
        return self._attr_name

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def state(self):
        if self._is_running and self._current_sequence_name:
            seq = self._sequences.get(self._current_sequence_name, [])
            return f"running '{self._current_sequence_name}' ({self._current_index+1}/{len(seq)})"
        return "idle"

    async def added_to_hass(self):
        @callback
        def handle_step_completed(event):
            _LOGGER.info(f"[SequenceManager] Step completed event: {event.data}")
            if not self._is_running or not self._current_sequence_name:
                return

            seq = self._sequences.get(self._current_sequence_name)
            if not seq:
                _LOGGER.warning(f"[SequenceManager] Current sequence '{self._current_sequence_name}' not found")
                self._is_running = False
                self.async_write_ha_state()
                return

            self._current_index += 1
            if self._current_index < len(seq):
                next_automation = seq[self._current_index]
                _LOGGER.info(f"[SequenceManager] Triggering next automation: {next_automation}")
                self._hass.create_task(self._trigger_automation(next_automation))
            else:
                _LOGGER.info(f"[SequenceManager] Sequence '{self._current_sequence_name}' complete")
                self._is_running = False
                self._current_sequence_name = None

            self.async_write_ha_state()

        self._hass.bus.listen(EVENT_STEP_COMPLETED, handle_step_completed)

    async def _trigger_automation(self, automation_entity_id):
        _LOGGER.info(f"[SequenceManager] Triggering automation: {automation_entity_id}")
        await self._hass.services.call(
            "automation",
            "trigger",
            {"entity_id": automation_entity_id},
            blocking=False
        )
        self.async_write_ha_state()

    async def add_sequence(self, name: str, sequence: list[dict]):
        if not sequence:
            _LOGGER.warning(f"[SequenceManager] Empty sequence received for '{name}'")
            return
        self._sequences[name] = sequence
        _LOGGER.info(f"[SequenceManager] Added/Updated sequence '{name}': {sequence}")
        self.async_write_ha_state()

    async def remove_sequence(self, name: str):
        if name in self._sequences:
            del self._sequences[name]
            _LOGGER.info(f"[SequenceManager] Removed sequence '{name}'")
            self.async_write_ha_state()

    async def start_sequence(self, name: str):
        #Check if the sequence exist
        if name not in self._sequences:
            _LOGGER.warning(f"[SequenceManager] Tried to start unknown sequence '{name}'")
            return
        #Check if the sequence is already running
        if self._is_running:
            _LOGGER.warning(
                f"[SequenceManager] Already running a sequence '{self._current_sequence_name}', cannot start '{name}'"
            )
            return

        self._current_sequence_name = name
        self._current_index = 0
        self._is_running = True
        _LOGGER.info(f"[SequenceManager] Starting sequence '{name}'")

        # Exec the steps in order of the sequence
        for step in self._sequences[name]:
            service = step.get("service")
            data = step.get("data", {})
            try:
                domain, service_name = service.split(".")
                await self.hass.services.async_call(domain, service_name, data)
            except Exception as e:
                _LOGGER.error(f"[SequenceManager] Failed to execute service '{service}' with data {data}: {e}")

        self._is_running = False
        self.async_write_ha_state()
