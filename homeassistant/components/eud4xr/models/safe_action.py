import inspect
from homeassistant.core import HomeAssistant
from ..const import (
    DOMAIN,
    IS_DEBUG
)


class SafeAction:

    def __init__(self, verb: str, subject: str, obj: object=None, variable: str=None, modifier: str=None, value: str=None) -> None:
        self.verb = verb
        self.subject = subject
        self.obj = obj
        self.variable = variable
        self.modifier = modifier
        self.value = value

    def to_dict(self) -> dict:
        data = {
            "verb": self.verb,
            "subject": self.subject,
            **{k: v for k, v in {
                "obj": self.obj,
                "variable": self.variable,
                "modifier": self.modifier,
                "value": self.value
                }.items() if v}
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'SafeAction':
        return cls(
            verb=data.get("verb"),
            subject=data.get("subject"),
            obj=data.get("obj"),
            variable=data.get("variable"),
            modifier=data.get("modifier"),
            value=data.get("value"),
        )

    @classmethod
    def from_yaml(cls, data: dict) -> 'SafeAction':
        '''
            It converts eca actions from hass format to natural language:
        '''
        action_data = data[0]["event_data"] if isinstance(data, list) else data["event_data"]

        return SafeAction(**action_data)

    @classmethod
    def to_yaml(cls, data: dict) -> dict:
        '''
            It converts eca actions from natural language to hass event
        '''
        return {
            "platform": "event",
            "event_type": DOMAIN,
            "event_data": data
        }
