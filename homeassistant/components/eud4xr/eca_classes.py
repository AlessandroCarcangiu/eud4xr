from enum import Enum

import voluptuous as vol


class ECABooleanEnum(Enum):
    YES = "yes"
    ON = "on"
    TRUE = "true"
    NO = "no"
    OFF = "off"
    FALSE = "false"

    @classmethod
    def get_value_by_str(cls, value: str):
        try:
            return cls[value.upper()]
        except KeyError:
            raise Exception(f"{value} is not a valid option for ECABooleanEnum")

    def __str__(self):
        return self.value


class ECABoolean:
    def __init__(self, choice: ECABooleanEnum) -> None:
        self.choice = choice

    def __str__(self) -> str:
        return f"{self.choice}"

    @staticmethod
    def validate(value: str):
        if not isinstance(value, str):
            raise vol.Invalid("Expected a string")
        value = ECABooleanEnum.get_value_by_str(value)
        return ECABoolean(value)


class ECAPosition:
    def __init__(self, x, y, z) -> None:
        self.x = x
        self.y = y
        self.z = z

    def __str__(self) -> str:
        return "{" + f"'x': {self.x}, 'y': {self.y}, 'z': {self.z}" + "}"

    @classmethod
    def from_dict(cls, data):
        x = data.get("x")
        y = data.get("y")
        z = data.get("z")
        return cls(x, y, z)

    @staticmethod
    def validate(value):
        if not isinstance(value, dict):
            raise vol.Invalid("Expected a dictionary")
        x = value.get("x")
        y = value.get("y")
        z = value.get("z")
        if not all(isinstance(i, (int, float)) for i in [x, y, z]):
            raise vol.Invalid("x, y, z must be numbers")
        return ECAPosition(x, y, z)


class ECARotation(ECAPosition):
    pass


class ECAColor:
    def __init__(self, value: str = None) -> None:
        self.value = value

    def __str__(self) -> str:
        return f"{self.value}"

    @staticmethod
    def validate(value: str):
        if not isinstance(value, str):
            raise vol.Invalid("Expected a string")
        return ECAColor(value)


class ECAScale(ECAPosition):
    pass


# class ECAPath:

#     def __init__(self, points: List[ECAPosition]) -> None:
#         self.points = points

#     def __str__(self) -> str:
#         return "".join([f"{v}" for v in self.points])

#     @classmethod
#     def from_dict(cls, data: list) -> 'ECAPath':
#         values = [ECAPosition(**p) for p in data]
#         return cls(values)

#     @staticmethod
#     def validate(value):
#         if not isinstance(value, list) and not all(isinstance(e, dict) for e in value):
#             raise vol.Invalid("Expected a list of dictionaries")
#         return ECAPosition(value)
