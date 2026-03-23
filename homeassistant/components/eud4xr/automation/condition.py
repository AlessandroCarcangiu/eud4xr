# ruff: noqa

import json
import re

from homeassistant.core import HomeAssistant

from ..const import (
    IS_DEBUG,
    CONF_JSON_COMPOSITE_KEYS,
    CONF_JSON_SIMPLE_KEYS
)
from ..hass_utils import (
    convert_subject_to_unity,
    get_entity_id_by_game_object_and_property,
)


class Condition:
    def to_dict(self):
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict) -> "Condition":
        return cls()


class SimpleCondition(Condition):
    def __init__(
        self, component: str, property: str, symbol: str, compareWith: object
    ) -> None:
        self.component = component
        self.property = property
        self.symbol = symbol
        self.compareWith = compareWith

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "property": self.property,
            "symbol": self.symbol,
            "compareWith": self.compareWith,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SimpleCondition":
        return cls(
            component=data.get("component"),
            property=data.get("property"),
            symbol=data.get("symbol"),
            compareWith=data.get("compareWith"),
        )

    def to_yaml(self, hass: HomeAssistant) -> dict:
        """It converts eca conditions from natural language to hass format.
        In natural language, a condition based on eca objects appears as:
            component: {game_object_name},
            property: {verb_name} (express in natural language),
            symbol: {symbol},
            compareWith: {value}
        In HASS, a condition based on eca objects would appear as:
            condition: template
            value_template: ' {{ state_attr('{sensor.game_object_name_eca_script}', '{property_name}') {symbol} {value} }}
        """
        if isinstance(self.compareWith, (dict, list)):
            comparewith_str = json.dumps(self.compareWith)
        else:
            comparewith_str = f'"{self.compareWith}"'

        # from game_object_name to sensor_name
        # - strategy: find a group with same name, loop on its entities and get the first that has property
        try:
            entity_id = get_entity_id_by_game_object_and_property(
                hass, self.component, self.property
            )
        except:
            entity_id = self.component
        res = {
            "condition": "template",
            "value_template": "{{ "
            + f'state_attr("{entity_id}", "{self.property}") {self.symbol} {comparewith_str} '
            + "}}",
        }
        return res

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict) -> dict:
        """It converts eca conditions from hass format to natural language:
        component: game_object_name@eca_script
        property: property_name
        symbol: symbol
        compareWith: value
        """
        value_template = data["value_template"].strip()
        pattern = (
            r'\{\{\s*state_attr\("([^"]+)",\s*"([^"]+)"\)\s*([!=<>]+)\s*(.+?)\s*\}\}'
        )
        # apply regex
        match = re.search(pattern, value_template)
        if not match:
            raise Exception(f"[SimpleCondition - from_yaml] Error on converting condition - {value_template}")
        # extract group, the game object in unity, from the component
        try:
            component = convert_subject_to_unity(hass, match.group(1))
        except Exception as e:
            component = match.group(1)
            print(f"[SimpleCondition - from_yaml] WARNING {component} is not an eca object or not found - Error generated: {e}")
        property = match.group(2)
        symbol = match.group(3)
        compareWith = match.group(4).replace(" }}", "").replace('"', "")
        return cls(
            component=component,
            property=property,
            symbol=symbol,
            compareWith=compareWith,
        )


class CompositeCondition(Condition):
    def __init__(self, operator: str, conditions: list[Condition]) -> None:
        self.operator = operator
        self.conditions = conditions

    def __str__(self) -> str:
        return f"operator: {self.operator} - conditions: {self.conditions}"

    def to_dict(self) -> dict:
        return {
            "op": self.operator,
            "conditions": [c.to_dict() for c in self.conditions]
            if isinstance(self.conditions, list)
            else self.conditions.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Condition":
        return cls(
            operator=data.get("operator"),
            conditions=[
                CompositeCondition.from_dict(c)
                if "operator" in c
                else SimpleCondition.from_dict(c)
                for c in data.get("conditions")
            ],
        )

    def to_yaml(self, hass: HomeAssistant) -> dict:
        return {
            "condition": self.operator,
            "conditions": [c.to_yaml(hass) for c in self.conditions],
        }

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict) -> dict:
        operator = data["condition"]
        data_conditions = data["conditions"]
        conditions = None

        if len(data_conditions) > 1:
            conditions = [
                CompositeCondition.from_yaml(hass, c)
                if "conditions" in c
                else SimpleCondition.from_yaml(hass, c)
                for c in data_conditions
            ]
            # conditions = CompositeCondition("and", c) if not operator else conditions
        else:
            conditions = (
                CompositeCondition.from_yaml(hass, data_conditions)
                if "conditions" in data_conditions
                else SimpleCondition.from_yaml(hass, data_conditions)
            )
        return cls(operator=operator, conditions=conditions)


def get_condition(data: dict | list) -> Condition | list[Condition]:
    def convert(i) -> Condition:
        converted_value = i
        if all(k in i for k in CONF_JSON_COMPOSITE_KEYS):
            converted_value = CompositeCondition.from_dict(i)
        elif all(k in i for k in CONF_JSON_SIMPLE_KEYS):
            converted_value = SimpleCondition.from_dict(i)
        return converted_value

    if isinstance(data, list):
        conditions = [convert(c) for c in data]
    else:
        conditions = convert(data)

    if isinstance(conditions, list) and len(conditions) == 1:
        conditions = conditions[0]
    return conditions
