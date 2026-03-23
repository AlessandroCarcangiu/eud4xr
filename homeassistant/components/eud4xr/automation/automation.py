# ruff: noqa

import copy
import logging
import uuid
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .action import Action
from .condition import CompositeCondition, Condition, SimpleCondition, get_condition
from .eca_action import ECAAction
from .safe_action import SafeAction
from .yaml_action import YAMLAction
from ..const import (
    CONF_YAML_COMPOSITE_KEYS,
    CONF_YAML_SIMPLE_KEYS
)

_LOGGER = logging.getLogger(__name__)


class Automation:
    def __init__(
        self,
        trigger: Action | ECAAction,
        conditions: list[Condition],
        actions: list[Action | ECAAction],
        alias: str = "",
        description: str = "",
        id: str = None,
    ) -> None:
        if not id:
            id = str(uuid.uuid4())
        self.id = id  # datetime.now().strftime("%Y%m%d%H%M%S")
        self.trigger = trigger
        self.conditions = conditions
        self.actions = actions
        self.alias = slugify(alias)
        self.description = description

    def to_dict(self) -> dict:
        if isinstance(self.conditions, list):
            conditions = [c.to_dict() for c in self.conditions]
        elif self.conditions:
            conditions = self.conditions
            if isinstance(self.conditions, (SimpleCondition, CompositeCondition)):
                conditions = conditions.to_dict()
        else:
            conditions = self.conditions
        return {
            "id": self.id,
            "trigger": [self.trigger.to_dict()]
            if not isinstance(self.trigger, dict)
            else self.trigger,
            "conditions": conditions,
            "actions": [
                a.to_dict() if isinstance(a, ECAAction) else a for a in self.actions
            ]
            if self.actions
            else self.actions,
            "alias": self.alias,
            "description": self.description,
            "entity_id": f"automation.{slugify(self.alias)}",
            "mode": "single",
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Automation":
        r_conditions = data.get("conditions", [])
        kwargs = {
            "id": data.get("id"),
            "trigger": cls.__get_service(
                data.get("trigger")
            ),  # YAMLAction.from_dict(data.get("trigger")),
            "actions": [
                cls.__get_service(a) for a in data.get("actions")
            ],  # [YAMLAction.from_dict(a) for a in data.get("actions")],
            "alias": data.get("alias"),
            "description": data.get("description"),
        }
        kwargs["conditions"] = [get_condition(r_conditions)] if r_conditions else []
        return cls(**kwargs)

    @classmethod
    def __get_service(cls, service_data: dict) -> YAMLAction | list:
        try:
            result = YAMLAction.from_dict(service_data)
        except Exception as e:
            result = service_data
        return result

    def to_yaml(self, hass: HomeAssistant) -> str:
        yaml_data = dict()
        # id + alias + description
        yaml_data["id"] = self.id
        yaml_data["alias"] = self.alias
        yaml_data["description"] = self.description
        # trigger
        yaml_data["trigger"] = [
            self.safe_action_to_yaml(hass, self.trigger, as_event=True)
        ]
        # conditions
        conditions = list()
        for c in self.conditions:
            v = c.to_yaml(hass) if isinstance(c, (SimpleCondition, CompositeCondition)) else c
            conditions.append(v)
        yaml_data["condition"] = conditions
        # actions
        yaml_data["action"] = [self.safe_action_to_yaml(hass, a) for a in self.actions]
        # convert to yaml
        automation_yaml = yaml.dump(yaml_data, default_flow_style=False)
        return automation_yaml

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict) -> "Automation":
        # trigger
        trigger = cls.safe_action_from_yaml(hass, data.get("trigger"), is_trigger=True)
        # actions
        automation_actions = data.get("action")
        actions = list()
        if automation_actions:
            for a in automation_actions:
                if "service" in a:
                    service = a["service"]
                    if service in ["automation.turn_on", "automation.turn_off", "eud4xr.increment_counter"]:
                        break
                actions.append(cls.safe_action_from_yaml(hass, a))
        # conditions
        automation_conditions = data.get("condition")
        conditions = None
        if automation_conditions:
            conditions = list()
            for c in automation_conditions:
                if all(k in c for k in CONF_YAML_COMPOSITE_KEYS):
                    v = CompositeCondition.from_yaml(hass, c)
                elif all(k in c for k in CONF_YAML_SIMPLE_KEYS):
                    v = SimpleCondition.from_yaml(hass, c)
                else:
                    v = c
                conditions.append(v)

            if len(conditions) > 1:
                conditions = CompositeCondition("and", conditions)
            elif len(conditions) == 1:
                conditions = conditions[0]

        id = data.get("id")
        return cls(
            trigger=trigger,
            conditions=conditions,
            actions=actions,
            alias=data.get("alias"),
            description=data.get("description"),
            id=id,
        )

    @staticmethod
    def safe_action_to_yaml(
        hass: HomeAssistant, action, **kwargs
    ) -> dict:
        data = None
        try:
            data = action.to_yaml(hass, **kwargs)
        except Exception as e:
            print(f"Error on converting {action} to yaml - error occurred: {e}")
            return action
        return data

    @staticmethod
    def safe_action_from_yaml(
        hass: HomeAssistant, data: dict, **kwargs
    ) -> ECAAction | SafeAction | dict:
        action = None
        try:
            d = copy.deepcopy(data)
            action = ECAAction.from_yaml(hass=hass, data=d, **kwargs)
        except Exception as ed:
            try:
                d = copy.deepcopy(data)
                action = SafeAction.from_yaml(d)
            except:
                try:
                    action = (
                        data[0]
                        if kwargs.get("is_trigger") and isinstance(data, list)
                        else data
                    )
                except Exception as e:
                    _LOGGER.error(f"Potentially no action or trigger available. Data: {data}\nError detected: {e}")
                    raise e
        return action
