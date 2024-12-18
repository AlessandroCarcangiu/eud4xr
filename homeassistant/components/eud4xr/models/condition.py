import json
import re
from homeassistant.core import HomeAssistant
from ..const import IS_DEBUG
from ..hass_utils import get_entity_id_by_game_object_and_property, convert_subject_to_unity


class Condition:

    def to_dict(self):
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict) -> 'Condition':
        return cls()


class SimpleCondition(Condition):

    def __init__(self, component: str, property: str, symbol: str, compareWith: object) -> None:
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
    def from_dict(cls, data: dict) -> 'SimpleCondition':
        return cls(
            component=data.get("component"),
            property=data.get("property"),
            symbol=data.get("symbol"),
            compareWith=data.get("compareWith"),
        )

    def to_yaml(self, hass: HomeAssistant) -> dict:
        '''
            It converts eca conditions from natural language to hass format.
            In natural language, a condition based on eca objects appears as:
                component: {game_object_name},
                property: {verb_name} (express in natural language),
                symbol: {symbol},
                compareWith: {value}
            In HASS, a condition based on eca objects would appear as:
                condition: template
                value_template: ' {{ state_attr('{sensor.game_object_name_eca_script}', '{property_name}') {symbol} {value} }}
        '''
        if IS_DEBUG:
            print("------------start SIMPLECONDITION to_yaml------------")
            print(f"data: {self.to_dict()}")
            print("------------end SIMPLECONDITION to_yaml------------\n")

        if isinstance(self.compareWith, (dict, list)):
            comparewith_str = json.dumps(self.compareWith)
        else:
            comparewith_str = f"\"{self.compareWith}\""

        # from game_object_name to sensor_name
        # - strategy: find a group with same name, loop on its entities and get the first that has property
        entity_id = get_entity_id_by_game_object_and_property(hass, self.component, self.property)
        res = {
            "condition": "template",
            "value_template": "{{ " + f"state_attr(\"{entity_id}\", \"{self.property}\") {self.symbol} {comparewith_str} " + "}}"
        }
        return res

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict) -> dict:
        '''
            It converts eca conditions from hass format to natural language:
                component: game_object_name@eca_script
                property: property_name
                symbol: symbol
                compareWith: value
        '''
        if IS_DEBUG:
            print("------------start SIMPLECONDITION from_yaml------------")
            print(f"data: {data}")
            print("------------end SIMPLECONDITION from_yaml------------\n")
        value_template = data["value_template"].strip()
        pattern = r'\{\{\s*state_attr\("([^"]+)",\s*"([^"]+)"\)\s*([!=<>]+)\s*(.+?)\s*\}\}'
        #r"state_attr\('([^']+)',\s'([^']+)'\)\s([!=<>]+)\s({.*})"
        # apply regex
        match = re.search(pattern, value_template)
        if not match:
            raise Exception(f"Error on converting condition - {value_template}")
        # extract group, the game object in unity, from the component
        #component = "_".join(match.group(1).split(".")[-1].split("_")[:-1])
        component = convert_subject_to_unity(hass, match.group(1))
        property = match.group(2)
        symbol = match.group(3)
        compareWith = match.group(4).replace(" }}", "").replace('\"', "")
        return cls(
            component=component,
            property=property,
            symbol=symbol,
            compareWith=compareWith
        )


class CompositeCondition(Condition):

    def __init__(self, operator: str, conditions: list[Condition]) -> None:
        self.operator = operator
        self.conditions = conditions

    def to_dict(self) -> dict:
        return {
            "op": self.operator,
            "conditions": [c.to_dict() for c in self.conditions] if isinstance(self.conditions, list) else self.conditions.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Condition':
        if IS_DEBUG:
            print("------------start CompositeCondition from_dict------------")
            print(f"data: {data}")
            print("------------end CompositeCondition from_dict------------\n")
        return cls(
            operator=data.get("operator"),
            conditions=[CompositeCondition.from_dict(c) if "operator" in c else SimpleCondition.from_dict(c)
                        for c in data.get("conditions")],
        )

    def to_yaml(self, hass: HomeAssistant) -> dict:
        return {
            "condition": self.operator,
            "conditions": [c.to_yaml(hass) for c in self.conditions]
        }

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict) -> dict:
        operator = data["condition"]
        data_conditions = data["conditions"]
        conditions = None

        if len(data_conditions) > 1:
            conditions = [CompositeCondition.from_yaml(hass, c) if "conditions" in c else SimpleCondition.from_yaml(hass, c)
                      for c in data_conditions]
            #conditions = CompositeCondition("and", c) if not operator else conditions
        else:
            conditions = CompositeCondition.from_yaml(hass, data_conditions) if "conditions" in data_conditions else SimpleCondition.from_yaml(hass, data_conditions)
        return cls(
            operator=operator,
            conditions=conditions
        )

def get_condition(data: dict | list) -> Condition | list[Condition]:
    def convert(i) -> Condition:
        return CompositeCondition.from_dict(i) if "operator" in i else SimpleCondition.from_dict(i)
    if isinstance(data, list):
        conditions = [convert(c) for c in conditions]
    else:
        conditions = convert(data)
    print(conditions)
    return conditions
