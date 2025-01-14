from datetime import datetime
import logging

import voluptuous as vol
import uuid
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    AUTOMATION_PATH,
    IS_DEBUG,
    CONF_SERVICE_ADD_UPDATE_AUTOMATION_DATA,
    CONF_SERVICE_REMOVE_AUTOMATION_ID,
)

_LOGGER = logging.getLogger(__name__)


RECEIVED_AUTOMATION_SCHEMA = vol.Schema(
    {vol.Required(CONF_SERVICE_ADD_UPDATE_AUTOMATION_DATA): cv.string}
)

REMOVE_AUTOMATION_SCHEMA = vol.Schema(
    {vol.Required(CONF_SERVICE_REMOVE_AUTOMATION_ID): cv.string}
)


def get_automations(hass: HomeAssistant, as_list: bool = False) -> dict | list:
    file = hass.config.path(AUTOMATION_PATH)
    with open(file) as f:
        data = yaml.safe_load(f)
    if data:
        return {a.get("id"): a for a in data} if not as_list else data
    return dict()


def add_automation(hass: HomeAssistant, yaml_code):
    file = hass.config.path(AUTOMATION_PATH)
    with open(file, "w") as f:
        yaml.dump(yaml_code, f)


async def update_automation_and_reload(hass: HomeAssistant, automations: dict) -> None:
    await hass.async_add_executor_job(add_automation, hass, list(automations.values()))
    await hass.services.async_call("automation", "reload", {})


async def async_get_automation(hass: HomeAssistant, id: str) -> dict:
    automations = await async_list_automations(hass)
    if id in automations:
        return automations[id]
    raise Exception(f"Automation with {id} does not exist")

async def async_list_automations(hass: HomeAssistant) -> list:
    automation_entities = await hass.async_add_executor_job(get_automations, hass, True)
    if automation_entities is None:
        automation_entities = list()
    return automation_entities


async def async_add_update_automation(hass: HomeAssistant, data: list) -> None:
    existing_automations = await hass.async_add_executor_job(get_automations, hass)
    try:
        # convert input string into yaml
        automations_data = list()
        if isinstance(data, dict):
            automations_data.append(automations_data)
        else:
            automations_data = [yaml.safe_load(d) for d in data]
        # append or update automations
        for automation_data in automations_data:
            automation_id = automation_data.get("id")
            if not automation_id:
                automation_id = str(uuid.uuid4()) #datetime.now().strftime("%Y%m%d%H%M%S")
                automation_data["id"] = automation_id
            existing_automations[automation_id] = automation_data
        # update and reload automation.yaml file
        await update_automation_and_reload(hass, existing_automations)
        hass.bus.async_fire("event_automation_reloaded")
        _LOGGER.info("Automations successfully updated or added")

    except yaml.YAMLError as e:
        _LOGGER.error(f"Error on parsing YAML code: {e}")
    except Exception as e:
        _LOGGER.error(f"Error on adding or updating an automation: {e}")


async def async_remove_automation(hass: HomeAssistant, automation_id: str) -> None:
    try:
        existing_automations = await hass.async_add_executor_job(get_automations, hass)
        if automation_id in existing_automations:
            del existing_automations[automation_id]
            await update_automation_and_reload(hass, existing_automations)
            _LOGGER.info("Automation {automation_id} successfully removed")
        else:
            _LOGGER.warning("Automation id not exists")
    except yaml.YAMLError as e:
        _LOGGER.error(f"Error on parsing YAML code: {e}")
    except Exception as e:
        _LOGGER.error(f"Error on removing a new automation: {e}")
