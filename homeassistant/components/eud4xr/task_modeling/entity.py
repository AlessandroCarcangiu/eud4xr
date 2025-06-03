from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.storage import Store

from ..const import (
    CONF_TASK_MODELLING_STORE_NAME,
    CONF_TASK_MODELLING_STORE_VERSION,
    CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY,
)


class CounterOrderIndependence(Entity):
    def __init__(self, hass: HomeAssistant, name: str ) -> None:
        self._attr_name = name
        self._attr_unique_id = f"EXPR_counter_{name}"
        self._attr_state = 0

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        store = Store(self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME)
        data = await store.async_load() or {}
        counters_names = data.setdefault(CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY, [])
        if self.name not in counters_names:
            counters_names.append(self.name)
            data[CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY] = counters_names
            await store.async_save(data)


    @property
    def state(self) -> int:
        return self._attr_state

    @property
    def should_poll(self) -> bool:
        return False

    async def increment(self) -> None:
        self._attr_state += 1
        self.async_write_ha_state()




