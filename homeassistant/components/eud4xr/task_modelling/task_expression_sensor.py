import os

import yaml

from homeassistant.components.sensor import SensorEntity


class TaskExpressionSensor(SensorEntity):

    def __init__(self, hass) -> None:
        self.hass = hass
        self._state = {"orders": [], "sequences": [], "choices": []}
        self._attr_name = "Task Expression Sensor"
        self._attr_entity_id = "sensor.task_expression_sensor"
        self.EXPRESSIONS_FILE_PATH = os.path.join(
            hass.config.config_dir, "expressions.yaml"
        )

    async def async_added_to_hass(self):
        await self.update_state()

    @property
    def state(self):
        total_expr = (
            len(self._state["orders"])
            + len(self._state["sequences"])
            + len(self._state["choices"])
        )
        return total_expr

    @property
    def extra_state_attributes(self):
        return {"state": self._state}

    async def update_state(self):
        if not os.path.exists(self.EXPRESSIONS_FILE_PATH):
            self._state = {"sequences": [], "choices": [], "orders": []}
            self.async_write_ha_state()
            return

        with open(self.EXPRESSIONS_FILE_PATH) as f:
            expressions = yaml.safe_load(f) or {}

        def extract_name_state(list_of_items):
            result = []
            for item in list_of_items:
                result.append({
                    "name": item.get("name"),
                    "state": item.get("state", {})
                })
            return result

        self._state["sequences"] = extract_name_state(expressions.get("sequences", []))
        self._state["choices"] = extract_name_state(expressions.get("choices", []))
        self._state["orders"] = extract_name_state(expressions.get("orders", []))

        self.async_write_ha_state()
