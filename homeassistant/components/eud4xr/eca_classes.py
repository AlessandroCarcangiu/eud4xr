# ruff: noqa

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

    def to_value(self) -> str:
        return self.choice.value

    def __bool__(self) -> bool:
        if self.choice in [ECABooleanEnum.TRUE, ECABooleanEnum.YES, ECABooleanEnum.ON]:
            return True
        return False

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

    def to_value(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}

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


class Vector3(ECAPosition):

    @staticmethod
    def validate(value):
        if not isinstance(value, dict):
            raise vol.Invalid("Expected a dictionary")
        if not isinstance(value, dict):
            raise Exception(
                "Invalid type for 'position': expected object with x, y, z"
            )

        #TODO The json below is accepted. Should we stricly check for ONLY the keys x, y, z?
        # 'position': {
        #   'x': -0.209391519,
        #   'y': 1.95605624,
        #   'z': -2.98058629,
        #   'normalized': {
        #       'x': -0.0586323962,
        #       'y': 0.5477216,
        #       'z': -0.8346036,
        #       'normalized': {
        #           'x': -0.0586324, 'y': 0.5477217, 'z': -0.834603667, 'magnitude': 1.0, 'sqrMagnitude': 1.00000012
        #       },
        #       'magnitude': 0.99999994,
        #       'sqrMagnitude': 0.99999994
        #   },
        #   'magnitude': 3.57125974,
        #   'sqrMagnitude': 12.7538958
        # }
        if not all(k in value for k in ("x", "y", "z")):
            raise Exception(
                "Missing one or more keys in 'position': x, y, z required"
            )

        if not all(isinstance(value[k], (int, float)) for k in ("x", "y", "z")):
            raise Exception(
                "Invalid type in 'position': x, y, z must be numbers"
            )
        x = value.get("x")
        y = value.get("y")
        z = value.get("z")
        return Vector3(x, y, z)

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
