import logging

import voluptuous as vol

from homeassistant.helpers import (
    condition as condition_helper,  # evita shadowing
    config_validation as cv,
)

_LOGGER = logging.getLogger(__name__)

START_ITERATION_SCHEMA = vol.Schema(
    {
        vol.Required("actions"): vol.All(cv.ensure_list, [dict]),
        vol.Optional("repeat"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("condition"): cv.CONDITION_SCHEMA,
    }
)


class IterationManager:
    def __init__(self, hass):
        self.hass = hass
        self._is_running = False

    async def start_iteration(self, actions, repeat=None, condition=None):
        if self._is_running:
            _LOGGER.warning("Iteration already running")
            return

        self._is_running = True

        if repeat is not None:
            _LOGGER.info(f"Starting iteration for {repeat} times")
            for _ in range(repeat):
                for action in actions:
                    await self._call_action(action)
            _LOGGER.info("Repeat iteration complete")
            self._is_running = False

        elif condition is not None:
            _LOGGER.info(f"Starting conditional iteration: {condition}")

            check_condition = await condition_helper.async_from_config(
                self.hass, condition
            )

            while self._is_running:
                if not check_condition(self.hass):
                    _LOGGER.info("Condition no longer valid. Stopping iteration.")
                    break

                for action in actions:
                    await self._call_action(action)

            self._is_running = False

        else:
            _LOGGER.error("Invalid iteration parameters")
            self._is_running = False

    async def _call_action(self, action):
        domain, service = action["service"].split(".")
        data = action.get("data", {})
        target = action.get("target", None)

        _LOGGER.debug(f"Calling {domain}.{service} with data={data} target={target}")
        if target:
            await self.hass.services.async_call(domain, service, data, target=target)
        else:
            await self.hass.services.async_call(domain, service, data)
