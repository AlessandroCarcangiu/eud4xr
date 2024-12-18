from datetime import datetime
import logging
import yaml
from homeassistant.core import HomeAssistant
from .action import Action
from .yaml_action import YAMLAction
from ..const import IS_DEBUG
from .condition import Condition, SimpleCondition, CompositeCondition, get_condition


_LOGGER = logging.getLogger(__name__)


class Automation:

    def __init__(self, trigger: Action, conditions: list[Condition], actions: list[Action],
                 alias: str = "", description: str = "", id: str = None) -> None:
        self.id = id if id else datetime.now().strftime("%Y%m%d%H%M%S")
        self.trigger = trigger
        self.conditions = conditions
        self.actions = actions
        self.alias = alias
        self.description = description

    def to_dict(self) -> dict:
        if isinstance(self.conditions, list):
            conditions = [c.to_dict() for c in self.conditions]
        elif self.conditions:
            conditions = self.conditions.to_dict()
        else:
            conditions = self.conditions
        return {
            "id": self.id,
            "trigger": [self.trigger.to_dict()],
            "conditions": conditions,
            "actions": [a.to_dict() for a in self.actions],
            "alias": self.alias,
            "description": self.description,
            "mode": "single"
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Automation':
        r_conditions = data.get("conditions", [])
        kwargs = {
            "id":data.get("id"),
            "trigger":YAMLAction.from_dict(data.get("trigger")),
            "actions":[YAMLAction.from_dict(a) for a in data.get("actions")],
            "alias":data.get("alias"),
            "description":data.get("description"),
        }
        kwargs["conditions"]=[get_condition(r_conditions)] if r_conditions else []
        return cls(**kwargs)

    def to_yaml(self, hass: HomeAssistant) -> str:
        yaml_data = dict()
        # id + alias + description
        yaml_data["id"] = self.id
        yaml_data["alias"] = self.alias
        yaml_data["description"] = self.description
        # trigger
        yaml_data["trigger"] = [self.trigger.to_yaml(hass=hass, as_event=True)]
        # conditions
        yaml_data["condition"] = [c.to_yaml(hass) for c in self.conditions]
        # actions
        yaml_data["action"] = [a.to_yaml(hass=hass) for a in self.actions]
        # convert to yaml
        automation_yaml = yaml.dump(yaml_data, default_flow_style=False)
        return automation_yaml

    @classmethod
    def from_yaml(cls, hass: HomeAssistant, data: dict) -> 'Automation':
        trigger = Action.from_yaml(hass, data.get("trigger"), is_trigger=True)
        actions = [Action.from_yaml(hass, a) for a in data.get("action")]
        data_conditions = data.get("condition")
        conditions = [
            SimpleCondition.from_yaml(hass, c) if c["condition"] == "template" else CompositeCondition.from_yaml(hass, c)
            for c in data_conditions
        ]

        if len(conditions) > 1:
            conditions = CompositeCondition("and", conditions)
        elif len(conditions) == 1:
            conditions = conditions[0]
        else:
            conditions = None

        return cls(
            trigger=trigger,
            conditions=conditions,
            actions=actions,
            alias=data.get("alias"),
            description=data.get("description"),
            id=data.get("id")
        )
