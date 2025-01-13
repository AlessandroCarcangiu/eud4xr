import inspect
import logging
import sys
import voluptuous as vol
from collections import deque
from homeassistant.const import CONF_SENSORS
from homeassistant.helpers import config_validation as cv, entity_platform
from typing import Union
from numbers import Number
from .const import *
from .eca_classes import ECABoolean, ECAColor, ECAPosition, ECARotation, ECAScale
from .entity import ECAEntity
from .utils import MappedClasses, eca_script_action, update_deque

_LOGGER = logging.getLogger(__name__)


DEQUE_FRAMED_OBJECTS = deque([], maxlen=MAX_LENGTH_CIRCULAR_LIST)

DEQUE_POINTED_OBJECTS = deque([], maxlen=MAX_LENGTH_CIRCULAR_LIST)

DEQUE_INTERACTED_OBJECTS = deque([], maxlen=MAX_LENGTH_CIRCULAR_LIST)


# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#     vol.Required(CONF_PLATFORM_ECA_SCRIPT): cv.string,
#     vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
#     vol.Required(CONF_NAME): cv.string,
#     vol.Required(CONF_PLATFORM_ATTRIBUTES, default={}): dict
# })

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_ECA_SCRIPT): cv.string,
        vol.Required(CONF_PLATFORM_GAME_OBJECT): cv.string,
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        # vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PLATFORM_ATTRIBUTES): dict,
    }
)

GAMEOBJECT_ECASCRIPT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_ECA_SCRIPT): cv.string,
        vol.Required(CONF_PLATFORM_GAME_OBJECT): cv.string,
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        # vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PLATFORM_ATTRIBUTES): dict,
        # cv.schema_with_slug_keys(
        #    cv.string
        # ),
    }
)

# NOTIFICATION_ACTION_FROM_UNITY_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
#         vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_VERB): cv.string,
#         vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_VARIABLE): cv.string,
#         vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_MODIFIER): cv.string,
#         vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_PARAMETERS): dict,
#     }
# )
NOTIFICATION_ACTION_FROM_UNITY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_VERB): cv.string,
        vol.Optional("obj"): object,
        vol.Optional("variable"): cv.string,
        vol.Optional("modifier"): cv.string,
        vol.Optional("value"): object,
    }
)

NOTIFICATION_UPDATE_FROM_UNITY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_ATTRIBUTE): cv.string,
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_NEW_VALUE): object,
    }
)

UPDATES_FROM_UNITY_SCHEMA = vol.Schema(
    # {vol.Required(CONF_UPDATES): vol.All(cv.ensure_list, [NOTIFICATION_UPDATE_FROM_UNITY_SCHEMA])}
    {
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_UPDATE): vol.Or(
            NOTIFICATION_UPDATE_FROM_UNITY_SCHEMA, NOTIFICATION_ACTION_FROM_UNITY_SCHEMA
        ),
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP): cv.Number,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SERVER_UNITY_URL): cv.url,
                vol.Required(CONF_SERVER_UNITY_TOKEN): cv.string,
                vol.Optional(CONF_SENSORS, default=list()): vol.All(
                    cv.ensure_list, [SENSOR_SCHEMA]
                ),
            }
        )
    }
)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    ECA_SCRIPTS = MappedClasses.get_eca_scripts()
    if ECA_SCRIPTS is None:
        ECA_SCRIPTS = MappedClasses.mapping_classes(hass)

    if discovery_info is None:
        print("discovery_info is none")
        return

    eca_script = discovery_info.get(CONF_PLATFORM_ECA_SCRIPT)
    eca_class = (
        ECA_SCRIPTS.get(eca_script)
        if ECA_SCRIPTS and eca_script in ECA_SCRIPTS
        else None
    )
    if not eca_class:
        return
    eca_scripts = list()
    attributes = discovery_info.get(CONF_PLATFORM_ATTRIBUTES, {})
    if attributes:
        discovery_info.pop(CONF_PLATFORM_ATTRIBUTES)
    parameters = {**discovery_info, **attributes, "hass": hass}
    eca_scripts.append(eca_class.cls(**parameters))
    async_add_entities(eca_scripts, True)

    # register all eca-scripts' methods as services
    platform = entity_platform.async_get_current_platform()
    for service_def in eca_class.service_definitions:
        platform.async_register_entity_service(*service_def)


def get_classes_subclassing(to_string: bool = False) -> list[any]:
    current_module = inspect.getmodule(inspect.currentframe())
    classes = inspect.getmembers(current_module, inspect.isclass)
    subclass_names = [
        cls if not to_string else name.lower() for name, cls in classes
        if issubclass(cls, ECAEntity) and cls is not ECAEntity
    ]
    return subclass_names
class Behaviour(ECAEntity):

    """
    Behaviour serves as a foundational component required for all behavior implementations within the automation framework.
            While only one instance of  is attached to a GameObject, it enables and supports specific behaviors such as Toggle or Switch,
            which inherit from this class and define unique functionality.
            This class does not contain any specific functionality, but rather serves as a base class for all behavior implementations.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class ECAObject(ECAEntity):

    """
    ECAObject is the base class for all virtual objects that can be used in the automations.
            All the other classes in this package inherit from this class or one of its subclasses.
            It supports properties such as position, rotation, scale, visibility, and activity, and provides methods for moving, rotating, scaling, and controlling visibility.

    Attributes:
    - position (ECAPosition): p represents the position of the virtual object in the 3D space. It's a vector with three components: x, y, and z.
    - rotation (ECARotation): r represents the rotation of the object in the 3D space. It's a vector with three components: x, y, and z (euler angles).
    - scale (ECAScale): r represents the scale of the object in the 3D space.
    - visible (ECABoolean): visible indicates whether the object is visible. The allowed values are either "yes" or "no".
            If invisible, the object is not rendered but remains interactive for collisions.
    - active (ECABoolean): active indicates whether the object is active. The allowed values are either "yes" or "no".
            When inactive, the object is not rendered and does not interact with other objects.
    - isInsideCamera (ECABoolean): isInsideCamera indicates whether the object is currently within the camera's field of view. This property is automatically updated at runtime.

    """
    def __init__(self, position: ECAPosition, rotation: ECARotation, scale: ECAScale, visible: ECABoolean, active: ECABoolean, isInsideCamera: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._position = position
        self._rotation = rotation
        self._scale = scale
        self._visible = visible
        self._active = active
        self._isInsideCamera = isInsideCamera
        self._attr_should_poll = False

    @property
    def position(self) -> ECAPosition:
        return self._position

    @property
    def rotation(self) -> ECARotation:
        return self._rotation

    @property
    def scale(self) -> ECAScale:
        return self._scale

    @property
    def visible(self) -> ECABoolean:
        return self._visible

    @property
    def active(self) -> ECABoolean:
        return self._active

    @property
    def isInsideCamera(self) -> ECABoolean:
        return self._isInsideCamera

    @isInsideCamera.setter
    @update_deque(DEQUE_FRAMED_OBJECTS)
    def isInsideCamera(self, v: ECABoolean) -> None:
        self._isInsideCamera = v

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "position": self.position,
            "rotation": self.rotation,
            "scale": self.scale,
            "visible": self.visible,
            "active": self.active,
            "isInsideCamera": self.isInsideCamera,
            **super_extra_attributes
        }

    @eca_script_action(verb = "moves to")
    async def async_moves_to(self, newPos: ECAPosition) -> None:
        """
        Moves (to) is a method that moves the object to a specified position in the 3D space.
        Argument:
            -newPos:The target position to move to.
        """
        _LOGGER.info(f"Performed moves_to action - {newPos}")

    @eca_script_action(verb = "moves on")
    async def async_moves_on(self, path: list[ECAPosition]) -> None:
        """
        Moves (to) is a method that moves the object to a specified position in the 3D space.
        Argument:
            -newPos:The target position to move to.
        """
        _LOGGER.info(f"Performed moves_on action - {path}")

    @eca_script_action(verb = "rotates around")
    async def async_rotates_around(self, newRot: ECARotation) -> None:
        """
        Rotates sets the object's rotation to a specified value in the 3D space.
        Argument:
            -newRot:The target rotation expressed as a vector with three components: x, y, and z.
        """
        _LOGGER.info(f"Performed rotates_around action - {newRot}")

    @eca_script_action(verb = "looks at")
    async def async_looks_at(self, o: object) -> None:
        """
        Looks adjusts the object's rotation to face a specified target object.
        Argument:
            -o:The target GameObject to look at.
        """
        _LOGGER.info(f"Performed looks_at action - {o}")

    @eca_script_action(verb = "scales to")
    async def async_scales_to(self, newScale: ECAScale) -> None:
        """
        Scales sets the object's scale to a specified value.
        Argument:
            -newScale:The new scale value fo the object. The scale is a vector with three components: x, y, and z.
        """
        _LOGGER.info(f"Performed scales_to action - {newScale}")

    @eca_script_action(verb = "restores original settings")
    async def async_restores_original_settings(self) -> None:
        """
        Restores the object's original position, rotation, and scale to their initial values.
        """
        _LOGGER.info(f"Performed restores_original_settings action")

    @eca_script_action(verb = "shows")
    async def async_shows(self) -> None:
        """
        Shows maakes the object visible if it is not already.
        """
        _LOGGER.info(f"Performed shows action")

    @eca_script_action(verb = "hides")
    async def async_hides(self) -> None:
        """
        Hides makes the object invisible if it is not already.
        """
        _LOGGER.info(f"Performed hides action")

    @eca_script_action(verb = "activates")
    async def async_activates(self) -> None:
        """
        Activates makes the object both interactable and visible.
        """
        _LOGGER.info(f"Performed activates action")

    @eca_script_action(verb = "deactivates")
    async def async_deactivates(self) -> None:
        """
        Deactivates makes the object invisible and non-interactable.
        """
        _LOGGER.info(f"Performed deactivates action")

    @eca_script_action(verb = "changes", variable = "visible", modifier = "to")
    async def async_changes_visible(self, yesNo: ECABoolean) -> None:
        """
        ShowsHides changes the visibility state of the object based on a parameter. The parameter can be either "yes" or "no".
        Argument:
            -yesNo:The new visibility state.
        """
        _LOGGER.info(f"Performed changes_visible action - {yesNo}")

    @eca_script_action(verb = "changes", variable = "active", modifier = "to")
    async def async_changes_active(self, yesNo: ECABoolean) -> None:
        """
        ActivatesDeactivates changes the active state of the object based on a parameter. The parameter can be either "yes" or "no".
        Argument:
            -yesNo:The new active state.
        """
        _LOGGER.info(f"Performed changes_active action - {yesNo}")


class Interactable(ECAEntity):

    """
    Interactable is a Behaviour that can be attached to an object in order to make it
            interactable with the player collison. If the action is not player initiated, then refer to

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Character(ECAEntity):

    """
    Represents a versatile character within the ECA rules framework.
            A Character can embody various forms, including animals, humanoids, robots, or generic creatures.
            It can operate autonomously or be controlled by the player, supporting a range of actions and state attributes
            to interact dynamically with the environment

    Attributes:
    - life (float): life is the current life of the character, represented as a float number.
    - playing (ECABoolean): playing indicates whether the character is controlled by the player ("yes") or operating autonomously ("no").

    """
    def __init__(self, life: float, playing: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._life = life
        self._playing = playing
        self._attr_should_poll = False

    @property
    def life(self) -> float:
        return self._life

    @property
    def playing(self) -> ECABoolean:
        return self._playing

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "life": self.life,
            "playing": self.playing,
            **super_extra_attributes
        }

    @eca_script_action(verb = "interacts with")
    async def async_interacts_with(self, o: Interactable) -> None:
        """
        Interacts enables the character to interact with a specified interactable object.
            The implementation details are managed by the  class logic.
        Argument:
            -o:The target interactable object
        """
        _LOGGER.info(f"Performed interacts_with action - {o}")

    @eca_script_action(verb = "stops-interacting with")
    async def async_stops_interacting_with(self, o: Interactable) -> None:
        """
        Stops interaction allows the character to stop its interaction with a specified interactable object.
            The implementation details are managed by the  class logic.
        Argument:
            -o:The target interactable object
        """
        _LOGGER.info(f"Performed stops_interacting_with action - {o}")

    @eca_script_action(verb = "points to")
    async def async_points_to(self, o: ECAObject) -> None:
        """
        Points the character to point at a specified object, emphasizing its focus or attention on the target.
        Argument:
            -o:The target object to point at.
        """
        _LOGGER.info(f"Performed points_to action - {o}")

    @eca_script_action(verb = "stops-pointing to")
    async def async_stops_pointing_to(self, o: ECAObject) -> None:
        """
        StopsPointing commands the character to stop pointing at a specified object, ceasing its focus or attention on the target.
        Argument:
            -o:The target object to stop pointing at.
        """
        _LOGGER.info(f"Performed stops_pointing_to action - {o}")

    @eca_script_action(verb = "jumps to")
    async def async_jumps_to(self, p: ECAPosition) -> None:
        """
        Jumps commands the character to jump to a specific position in the 3D world.
        Argument:
            -p:The destination position where the character will jump.
        """
        _LOGGER.info(f"Performed jumps_to action - {p}")

    @eca_script_action(verb = "jumps on")
    async def async_jumps_on(self, p: list[ECAPosition]) -> None:
        """
        Jumps commands the character to jump to a specific position in the 3D world.
        Argument:
            -p:The destination position where the character will jump.
        """
        _LOGGER.info(f"Performed jumps_on action - {p}")

    @eca_script_action(verb = "starts-animation")
    async def async_starts_animation(self, s: str) -> None:
        """
        StartsAnimation triggers a predefined animation for the character, using the provided animation identifier.
        Argument:
            -s:The string of the animation clip to play
        """
        _LOGGER.info(f"Performed starts_animation action - {s}")


class Vehicle(ECAEntity):

    """


    Attributes:
    - speed (float):
    - on (ECABoolean):

    """
    def __init__(self, speed: float, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._speed = speed
        self._on = on
        self._attr_should_poll = False

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def on(self) -> ECABoolean:
        return self._on

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "speed": self.speed,
            "on": self.on,
            **super_extra_attributes
        }

    @eca_script_action(verb = "starts")
    async def async_starts(self) -> None:
        _LOGGER.info(f"Performed starts action")

    @eca_script_action(verb = "steers-at")
    async def async_steers_at(self, angle: float) -> None:
        _LOGGER.info(f"Performed steers_at action - {angle}")

    @eca_script_action(verb = "accelerates-by")
    async def async_accelerates_by(self, f: float) -> None:
        _LOGGER.info(f"Performed accelerates_by action - {f}")

    @eca_script_action(verb = "slows-by")
    async def async_slows_by(self, f: float) -> None:
        _LOGGER.info(f"Performed slows_by action - {f}")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")


class AirVehicle(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "takes-off")
    async def async_takes_off(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed takes_off action - {p}")

    @eca_script_action(verb = "lands")
    async def async_lands(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed lands action - {p}")


class LandVehicle(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class SeaVehicle(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class SpaceVehicle(ECAEntity):

    """


    Attributes:
    - oxygen (float):
    - gravity (float):

    """
    def __init__(self, oxygen: float, gravity: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._oxygen = oxygen
        self._gravity = gravity
        self._attr_should_poll = False

    @property
    def oxygen(self) -> float:
        return self._oxygen

    @property
    def gravity(self) -> float:
        return self._gravity

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "oxygen": self.oxygen,
            "gravity": self.gravity,
            **super_extra_attributes
        }

    @eca_script_action(verb = "takes-off")
    async def async_takes_off(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed takes_off action - {p}")

    @eca_script_action(verb = "lands")
    async def async_lands(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed lands action - {p}")


class Scene(ECAEntity):

    """


    Attributes:
    - name (str):
    - position (ECAPosition):

    """
    def __init__(self, name: str, position: ECAPosition, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._name = name
        self._position = position
        self._attr_should_poll = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def position(self) -> ECAPosition:
        return self._position

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "name": self.name,
            "position": self.position,
            **super_extra_attributes
        }

    @eca_script_action(verb = "teleports to")
    async def async_teleports_to(self) -> None:
        _LOGGER.info(f"Performed teleports_to action")


class Prop(ECAEntity):

    """
    In Prop category we represent generic objects that can be placed in a scene and manipulated by characters.
            The possible sub-categories are, in this case, several; we can have passive actions, such as wear in Clothing
            script.

    Attributes:
    - price (float): Price: The price of the prop object.

    """
    def __init__(self, price: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._price = price
        self._attr_should_poll = False

    @property
    def price(self) -> float:
        return self._price

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "price": self.price,
            **super_extra_attributes
        }


class Clothing(ECAEntity):

    """
    Clothing: This class is used to define the clothing properties of the objects.

    Attributes:
    - brand (str): Brand: This property is used to define the brand of the clothing.
    - color (dict): Color: This property is used to define the color of the clothing.
    - size (str):
    - weared (ECABoolean): Weared: This property is used to define if the clothing is weared or not.

    """
    def __init__(self, brand: str, color: dict, size: str, weared: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._brand = brand
        self._color = color
        self._size = size
        self._weared = weared
        self._attr_should_poll = False

    @property
    def brand(self) -> str:
        return self._brand

    @property
    def color(self) -> dict:
        return self._color

    @property
    def size(self) -> str:
        return self._size

    @property
    def weared(self) -> ECABoolean:
        return self._weared

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "brand": self.brand,
            "color": self.color,
            "size": self.size,
            "weared": self.weared,
            **super_extra_attributes
        }

    @eca_script_action(verb = "wears")
    async def async_wears_(self, m: 'Mannequin') -> None:
        """
        _Wears: This method is used to allow the mannequin to wear the clothing.
        Argument:
            -m:The mannequin that wears the clothing
        """
        _LOGGER.info(f"Performed wears_ action - {m}")

    @eca_script_action(verb = "unwears")
    async def async_unwears_(self, m: 'Mannequin') -> None:
        """
        _Unwears: This method is used to allow the mannequin to unwear the clothing.
        Argument:
            -m:The mannequin that unwears the clothing
        """
        _LOGGER.info(f"Performed unwears_ action - {m}")

    @eca_script_action(verb = "wears")
    async def async_wears_(self, c: Character) -> None:
        """
        _Wears: This method is used to allow the mannequin to wear the clothing.
        Argument:
            -m:The mannequin that wears the clothing
        """
        _LOGGER.info(f"Performed wears_ action - {c}")

    @eca_script_action(verb = "unwears")
    async def async_unwears_(self, c: Character) -> None:
        """
        _Unwears: This method is used to allow the mannequin to unwear the clothing.
        Argument:
            -m:The mannequin that unwears the clothing
        """
        _LOGGER.info(f"Performed unwears_ action - {c}")


class Electronic(ECAEntity):

    """
    Electronic class is used to create and manage electronics objects, which are used to interact with the game.

    Attributes:
    - brand (str): Brand is the brand of the electronic.
    - model (str): Model is the model of the electronic.
    - on (ECABoolean): On is the state of the electronic.

    """
    def __init__(self, brand: str, model: str, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._brand = brand
        self._model = model
        self._on = on
        self._attr_should_poll = False

    @property
    def brand(self) -> str:
        return self._brand

    @property
    def model(self) -> str:
        return self._model

    @property
    def on(self) -> ECABoolean:
        return self._on

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "brand": self.brand,
            "model": self.model,
            "on": self.on,
            **super_extra_attributes
        }

    @eca_script_action(verb = "turns")
    async def async_turns(self, on: ECABoolean) -> None:
        """
        Turns: Turns the electronic on or off.
        Argument:
            -on:A boolean for the new state of the electronic
        """
        _LOGGER.info(f"Performed turns action - {on}")


class Food(ECAEntity):

    """
    Food is a class that represents something that can be eaten.

    Attributes:
    - weight (float): Weight: is the weight of the food.
    - expiration (str): Expiration: is the expiration date of the food.
    - description (str): Description: is the description of the food.
    - eaten (ECABoolean): Eaten: is true if the food has been eaten.

    """
    def __init__(self, weight: float, expiration: str, description: str, eaten: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._weight = weight
        self._expiration = expiration
        self._description = description
        self._eaten = eaten
        self._attr_should_poll = False

    @property
    def weight(self) -> float:
        return self._weight

    @property
    def expiration(self) -> str:
        return self._expiration

    @property
    def description(self) -> str:
        return self._description

    @property
    def eaten(self) -> ECABoolean:
        return self._eaten

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "weight": self.weight,
            "expiration": self.expiration,
            "description": self.description,
            "eaten": self.eaten,
            **super_extra_attributes
        }

    @eca_script_action(verb = "eats")
    async def async_eats(self, c: Character) -> None:
        """
        _Eats is the method that is called when the food is eaten. This is a passive action, so the Food type
            is not in the subject of the action, but on the object.
        Argument:
            -c:The character that eats the food
        """
        _LOGGER.info(f"Performed eats action - {c}")


class Weapon(ECAEntity):

    """
    The Weapon class is a base class for all weapons.

    Attributes:
    - power (float): Power: a float value that represents the power of the weapon.

    """
    def __init__(self, power: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._power = power
        self._attr_should_poll = False

    @property
    def power(self) -> float:
        return self._power

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "power": self.power,
            **super_extra_attributes
        }


class Bullet(ECAEntity):

    """
    Bullet: this class it is a type of  that is usually expelled from another object in the scene, usually a  object

    Attributes:
    - speed (float): Speed: this is the speed of the bullet

    """
    def __init__(self, speed: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._speed = speed
        self._attr_should_poll = False

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "speed": self.speed,
            **super_extra_attributes
        }


class EdgedWeapon(ECAEntity):

    """
    The EdgedWeapon class is a Weapon that has a sharp edge.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "stabs")
    async def async_stabs(self, obj: ECAObject) -> None:
        """
        Stabs: The action that occurs when a player stabs another ECAObject.
        Argument:
            -obj:The ECAObject that has been stabbed
        """
        _LOGGER.info(f"Performed stabs action - {obj}")

    @eca_script_action(verb = "slices")
    async def async_slices(self, obj: ECAObject) -> None:
        """
        Stabs: The action that occurs when a player slices another ECAObject.
        Argument:
            -obj:The ECAObject that has been sliced
        """
        _LOGGER.info(f"Performed slices action - {obj}")


class Firearm(ECAEntity):

    """
    Firearm is a class that represents a firearm, a firearm can expel bullets.

    Attributes:
    - charge (int): Charge is the current charge of the firearm.

    """
    def __init__(self, charge: int, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._charge = charge
        self._attr_should_poll = False

    @property
    def charge(self) -> int:
        return self._charge

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "charge": self.charge,
            **super_extra_attributes
        }

    @eca_script_action(verb = "recharges")
    async def async_recharges(self, charge: int) -> None:
        """
        Recharges: The action of recharging the firearm. It plays the particle system and increases the charge.
        Argument:
            -charge:The amount of charge
        """
        _LOGGER.info(f"Performed recharges action - {charge}")

    @eca_script_action(verb = "fires")
    async def async_fires(self, obj: ECAObject) -> None:
        """
        Fires: The action of firing the firearm. It plays the particle system and decreases the charge.
        Argument:
            -obj:The ECAObject that has been shot
        """
        _LOGGER.info(f"Performed fires action - {obj}")

    @eca_script_action(verb = "aims")
    async def async_aims(self, obj: ECAObject) -> None:
        """
        Aims: The action of aiming the firearm.
        Argument:
            -obj:
        """
        _LOGGER.info(f"Performed aims action - {obj}")


class Shield(ECAEntity):

    """
    Shield class allows to create a shield for defending from a .

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "blocks")
    async def async_blocks(self, weapon: Weapon) -> None:
        """
        Blocks: This action allows to block the  attack.
        Argument:
            -weapon:
        """
        _LOGGER.info(f"Performed blocks action - {weapon}")


class Interaction(ECAEntity):

    """
    Interaction represents entities in the scene that facilitate interaction with other objects or the environment.
            Unlike Behaviours, which define object-based rules and logic,
            Interaction focuses on physical entities that are perceived as independent objects by the user.
            These entities exist as standalone components within the environment, enhancing user engagement and interaction.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Button(ECAEntity):

    """
    Button is an  subclass that represents a button.
            When a  is pressed, it will trigger an event defined by the End User Developer.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "pushes")
    async def async_pushes(self, c: Character) -> None:
        """
        Presses is a passive function that represents the pressing of the button.
        Argument:
            -c:The  who presses the button.
        """
        _LOGGER.info(f"Performed pushes action - {c}")


class ECACamera(ECAEntity):

    """
    ECACamera is an  subclass that allows the user to interact with the camera the
            script is attached to.

    Attributes:
    - pov (str): POV is the camera's point of view.
    - zoomLevel (float): zoomLevel is the camera's zoom level.
    - playing (ECABoolean): Playing is a boolean that indicates whether the camera is currently playing.

    """
    def __init__(self, pov: str, zoomLevel: float, playing: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._pov = pov
        self._zoomLevel = zoomLevel
        self._playing = playing
        self._attr_should_poll = False

    @property
    def pov(self) -> str:
        return self._pov

    @property
    def zoomLevel(self) -> float:
        return self._zoomLevel

    @property
    def playing(self) -> ECABoolean:
        return self._playing

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "pov": self.pov,
            "zoomLevel": self.zoomLevel,
            "playing": self.playing,
            **super_extra_attributes
        }

    @eca_script_action(verb = "zooms-in")
    async def async_zooms_in(self, amount: float) -> None:
        """
        ZoomsIn reduces the camera's zoom level by the specified amount.
            If the resulting zoom is less than 30 the zoom is set to 30.
        Argument:
            -amount:The amount of zoom to remove
        """
        _LOGGER.info(f"Performed zooms_in action - {amount}")

    @eca_script_action(verb = "zooms-out")
    async def async_zooms_out(self, amount: float) -> None:
        """
        ZoomsOut increases the camera's zoom level by the specified amount.
             If the resulting zoom is greater than 100 the zoom is set to 100.
        Argument:
            -amount:The amount of zoom to add
        """
        _LOGGER.info(f"Performed zooms_out action - {amount}")

    @eca_script_action(verb = "changes", variable = "POV", modifier = "to")
    async def async_changes(self, pov: str) -> None:
        """
        ChangesPov changes the camera's point of view.
        Argument:
            -pov:The new  value.
        """
        _LOGGER.info(f"Performed changes action - {pov}")


class ECADoor(ECAEntity):

    """
    ECADoor: This class is used to define a door beviour.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "opens")
    async def async_opens(self) -> None:
        _LOGGER.info(f"Performed opens action")

    @eca_script_action(verb = "closes")
    async def async_closes(self) -> None:
        _LOGGER.info(f"Performed closes action")


class ECALight(ECAEntity):

    """
    ECALight represents a controllable light source in the environment.
            The ECALight class extends  to manage light properties such as intensity, color, and if it's on.

    Attributes:
    - intensity (float): intensity represents the brightness level of the light source. It cannot exceed the maximum intensity value.
    - maxIntensity (float): maxIntensity specifies the upper limit for the light's brightness. It ensures that the light's intensity does not exceed a predefined threshold.
    - color (dict): color represents the color of the light source. The value is a string that represents the color name (e.g., "red", "blue", "green").
    - on (ECABoolean): on indicates whether the light source is currently active or inactive. The accepted values are "on" or "off".

    """
    def __init__(self, intensity: float, maxIntensity: float, color: dict, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._intensity = intensity
        self._maxIntensity = maxIntensity
        self._color = color
        self._on = on
        self._attr_should_poll = False

    @property
    def intensity(self) -> float:
        return self._intensity

    @property
    def maxIntensity(self) -> float:
        return self._maxIntensity

    @property
    def color(self) -> dict:
        return self._color

    @property
    def on(self) -> ECABoolean:
        return self._on

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "intensity": self.intensity,
            "maxIntensity": self.maxIntensity,
            "color": self.color,
            "on": self.on,
            **super_extra_attributes
        }

    @eca_script_action(verb = "turns")
    async def async_turns(self, newStatus: ECABoolean) -> None:
        """
        Turns toggles the light source on or off based on the specified value ("on" or "off"), enabling or disabling illumination.
        Argument:
            -newStatus:The desired state of the light source (on or off).
        """
        _LOGGER.info(f"Performed turns action - {newStatus}")

    @eca_script_action(verb = "increases", variable = "intensity", modifier = "by")
    async def async_increases(self, amount: float) -> None:
        """
        IncreasesIntensity increases the brightness of the light source by a specified non-negative amount.
            If the resulting intensity exceeds the maximum allowed value, it is capped at maxIntensity.
        Argument:
            -amount:The value to add to the current intensity.
        """
        _LOGGER.info(f"Performed increases action - {amount}")

    @eca_script_action(verb = "decreases", variable = "intensity", modifier = "by")
    async def async_decreases(self, amount: float) -> None:
        """
        DecreasesIntensity reduces the brightness of the light source by a specified non-negative amount.
            If the resulting intensity drops below zero, it is set to zero to avoid negative values.
        Argument:
            -amount:The value to subtract from the current intensity.
        """
        _LOGGER.info(f"Performed decreases action - {amount}")

    @eca_script_action(verb = "sets", variable = "intensity", modifier = "to")
    async def async_sets(self, i: float) -> None:
        _LOGGER.info(f"Performed sets action - {i}")

    @eca_script_action(verb = "changes", variable = "color", modifier = "to")
    async def async_changes(self, inputColor: ECAColor) -> None:
        """
        SetsColor updates the light's color to the specified value. The allowed values are predefined color names (e.g., "red", "blue", "green").
        Argument:
            -inputColor:The desired color to apply to the light source.
        """
        _LOGGER.info(f"Performed changes action - {inputColor}")


class ECAVideo(ECAEntity):

    """
    ECAVideo is an  that represents a video player.

    Attributes:
    - source (str): Source is the video source.
    - volume (float): Volume is the video volume.
    - maxVolume (float): MaxVolume is the video max volume.
    - playing (ECABoolean): Playing defines whether the video is playing.
    - paused (ECABoolean): Paused defines whether the video is paused.
    - stopped (ECABoolean): Stopped defines whether the video is stopped.

    """
    def __init__(self, source: str, volume: float, maxVolume: float, playing: ECABoolean, paused: ECABoolean, stopped: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._source = source
        self._volume = volume
        self._maxVolume = maxVolume
        self._playing = playing
        self._paused = paused
        self._stopped = stopped
        self._attr_should_poll = False

    @property
    def source(self) -> str:
        return self._source

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def maxVolume(self) -> float:
        return self._maxVolume

    @property
    def playing(self) -> ECABoolean:
        return self._playing

    @property
    def paused(self) -> ECABoolean:
        return self._paused

    @property
    def stopped(self) -> ECABoolean:
        return self._stopped

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "source": self.source,
            "volume": self.volume,
            "maxVolume": self.maxVolume,
            "playing": self.playing,
            "paused": self.paused,
            "stopped": self.stopped,
            **super_extra_attributes
        }

    @eca_script_action(verb = "plays")
    async def async_plays(self) -> None:
        """
        Plays starts the video.
        """
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb = "pauses")
    async def async_pauses(self) -> None:
        """
        Pauses pauses the video.
        """
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        """
        Stops stops the video.
        """
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "changes", variable = "volume", modifier = "to")
    async def async_changes_volume(self, v: float) -> None:
        """
        ChangesVolume changes the video volume to the given value.
            If the value is greater than the max volume, the volume is set to the max volume.
            If the value is lower than 0, the volume is set to 0.
        Argument:
            -v:The new video volume.
        """
        _LOGGER.info(f"Performed changes_volume action - {v}")

    @eca_script_action(verb = "changes", variable = "source", modifier = "to")
    async def async_changes_source(self, newSource: str) -> None:
        """
        ChangesSource changes the video source to the given value.
            The new path must be relative to the user-accessible Inventory folder.
        Argument:
            -newSource:The path for the new video file.
        """
        _LOGGER.info(f"Performed changes_source action - {newSource}")


class Environment(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Artwork(ECAEntity):

    """
    Artwork represents an artwork in the environment.
            The Artwork class defines properties such as the author, price, and creation year of the artwork.

    Attributes:
    - author (str): author specifies the name of the artist of the artwork.
    - price (float): price represents the monetary value of the artwork.
    - year (int): year denotes the year in which the artwork was created.

    """
    def __init__(self, author: str, price: float, year: int, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._author = author
        self._price = price
        self._year = year
        self._attr_should_poll = False

    @property
    def author(self) -> str:
        return self._author

    @property
    def price(self) -> float:
        return self._price

    @property
    def year(self) -> int:
        return self._year

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "author": self.author,
            "price": self.price,
            "year": self.year,
            **super_extra_attributes
        }


class Building(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Exterior(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Furniture(ECAEntity):

    """


    Attributes:
    - price (float):
    - color (dict):
    - dimension (float):

    """
    def __init__(self, price: float, color: dict, dimension: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._price = price
        self._color = color
        self._dimension = dimension
        self._attr_should_poll = False

    @property
    def price(self) -> float:
        return self._price

    @property
    def color(self) -> dict:
        return self._color

    @property
    def dimension(self) -> float:
        return self._dimension

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "price": self.price,
            "color": self.color,
            "dimension": self.dimension,
            **super_extra_attributes
        }


class Terrain(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Vegetation(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Sky(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Animal(ECAEntity):

    """
    Represents an animal character within the ECA rules framework.
            An Animal is a specialized subclass of  that embodies animal-like traits
            and behaviors, enabling interactions and actions unique to animal entities.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "speaks")
    async def async_speaks(self, s: str) -> None:
        """
        Speaks allows the animal to produce a sound or "speak" by playing an associated audio clip.
            The audio clip is identified by the provided string, which must correspond to a valid resource.
        Argument:
            -s:The name of the audio resource to be played.
        """
        _LOGGER.info(f"Performed speaks action - {s}")


class AquaticAnimal(ECAEntity):

    """
    The AquaticAnimal class represents an aquatic animal.
            An AquaticAnimal can swim to specific positions or follow predefined paths, with animations for both swimming and idling states.
            This class extends the functionality of  to include aquatic-specific behaviors.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        """
        Swims (to) is a method that moves the aquatic animal to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        """
        Swims (to) is a method that moves the aquatic animal to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_on action - {p}")


class Creature(ECAEntity):

    """
    The Creature class represents a generic creature.
            A Creature can perform various movements such as running, walking, and swimming, each with a specific animation.
            This class extends the functionality of  to include creature-specific behaviors.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "flies to")
    async def async_flies_to(self, p: ECAPosition) -> None:
        """
        Flies (to) is a method that moves the creature to a specific position with a flying animation.
        Argument:
            -p:The target position to fly to.
        """
        _LOGGER.info(f"Performed flies_to action - {p}")

    @eca_script_action(verb = "flies on")
    async def async_flies_on(self, p: list[ECAPosition]) -> None:
        """
        Flies (to) is a method that moves the creature to a specific position with a flying animation.
        Argument:
            -p:The target position to fly to.
        """
        _LOGGER.info(f"Performed flies_on action - {p}")

    @eca_script_action(verb = "runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        """
        Runs (to) is a method that moves the creature to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        """
        Runs (to) is a method that moves the creature to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        """
        Swims (to) is a method that moves the creature to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        """
        Swims (to) is a method that moves the creature to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the creature to a specific position with a walking animation.
        Argument:
            -p:The target position to walk to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the creature to a specific position with a walking animation.
        Argument:
            -p:The target position to walk to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class FlyingAnimal(ECAEntity):

    """
    The FlyingAnimal class represents a flying animal.
            An FlyingAnimal can move using flying or walking animations and supports navigation to specific positions or along predefined paths.
            This class extends the functionality of  to include flying-specific behaviors.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "flies to")
    async def async_flies_to(self, p: ECAPosition) -> None:
        """
        Flies (to) is a method that moves the flying animal to a specific position with a flying animation.
        Argument:
            -p:The target position to fly to.
        """
        _LOGGER.info(f"Performed flies_to action - {p}")

    @eca_script_action(verb = "flies on")
    async def async_flies_on(self, p: list[ECAPosition]) -> None:
        """
        Flies (to) is a method that moves the flying animal to a specific position with a flying animation.
        Argument:
            -p:The target position to fly to.
        """
        _LOGGER.info(f"Performed flies_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the flying animal to a specific position with a walking animation.
        Argument:
            -p:The target position to walk to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the flying animal to a specific position with a walking animation.
        Argument:
            -p:The target position to walk to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class Human(ECAEntity):

    """
    The Human class represents a human character.
            A Human can perform various movements such as running, walking, and swimming, each with a specific animation.
            This class extends the functionality of  to include human-specific behaviors.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        """
        Runs (to) is a method that moves the human to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        """
        Runs (to) is a method that moves the human to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        """
        Swims (to) is a method that moves the human to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        """
        Swims (to) is a method that moves the human to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the human to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the human to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class Mannequin(ECAEntity):

    """
    The Mannequin class provides a way to include a character in the scene to wear 3D models of clothes that do not
            have rigging skeletons. Since the mannequin is supposed to stay still in the environment, the implementation contains
            for automatically positioning it on top of the mannequin according to the specified position (e.g., head, torso,
            left or right leg, arm, etc.). Provided that the distinction between a mannequin and a not-playable human is
            technical, it is up to the Unity developer to decide which object offers the best configuration options considering the
            template under development.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Robot(ECAEntity):

    """
    The Robot class represents a robot character (non-animal counterpart of a human).
            A Robot can perform various movements such as running, walking, and swimming, each with a specific animation.
            This class extends the functionality of  to include robot-specific behaviors.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        """
        Runs (to) is a method that moves the robot to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        """
        Runs (to) is a method that moves the robot to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        """
        Swims (to) is a method that moves the robot to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        """
        Swims (to) is a method that moves the robot to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the robot to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the robot to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class TerrestrialAnimal(ECAEntity):

    """
    The TerrestrialAnimal class represents a terrestrial animal.
            A TerrestrialAnimal can perform actions like running and walking, with corresponding animations for movement to specific positions or along paths.
            This class extends the functionality of  to include terrestrial-specific behaviors.

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        """
        Runs (to) is a method that moves the terrestrial animal to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        """
        Runs (to) is a method that moves the terrestrial animal to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the terrestrial animal to a specific position with a walking animation.
        Argument:
            -p:The target position to walk to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the terrestrial animal to a specific position with a walking animation.
        Argument:
            -p:The target position to walk to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class Collectable(ECAEntity):

    """
    Collectable is a Behaviour that lets an object to be taken inside a player/object owned inventory, or instantly used
            for interacting with other objects in the scene
            An object is collected, then a lock on a door unlocks

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class Container(ECAEntity):

    """
    Container is a Behaviour that enables the object to hold other objects.

    Attributes:
    - capacity (int): Capacity is the maximum number of objects that can be held by the container.
    - objectsCount (int): objectsCount is the number of objects that are currently held by the container.

    """
    def __init__(self, capacity: int, objectsCount: int, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._capacity = capacity
        self._objectsCount = objectsCount
        self._attr_should_poll = False

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def objectsCount(self) -> int:
        return self._objectsCount

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "capacity": self.capacity,
            "objectsCount": self.objectsCount,
            **super_extra_attributes
        }

    @eca_script_action(verb = "inserts")
    async def async_inserts(self, o: object) -> None:
        """
        Inserts inserts an object into the container.
        Argument:
            -o:The gameObject to be stored inside the container
        """
        _LOGGER.info(f"Performed inserts action - {o}")

    @eca_script_action(verb = "removes")
    async def async_removes(self, o: object) -> None:
        """
        Removes removes an object from the container.
        Argument:
            -o:The gameObject to be removed from the container
        """
        _LOGGER.info(f"Performed removes action - {o}")

    @eca_script_action(verb = "empties")
    async def async_empties(self) -> None:
        """
        Empties empties the container.
        """
        _LOGGER.info(f"Performed empties action")


class Counter(ECAEntity):

    """
    Counter is a Behaviour that enables the object to keep track of countable events
             Player steps, interaction count

    Attributes:
    - count (float): count is the current count of the counter

    """
    def __init__(self, count: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._count = count
        self._attr_should_poll = False

    @property
    def count(self) -> float:
        return self._count

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "count": self.count,
            **super_extra_attributes
        }

    @eca_script_action(verb = "changes", variable = "count", modifier = "to")
    async def async_changes(self, amount: float) -> None:
        """
        Changes changes the count of the counter
        Argument:
            -amount:the amount to set
        """
        _LOGGER.info(f"Performed changes action - {amount}")


class Highlight(ECAEntity):

    """
    Highlight is a Behaviour that is used to highlight the objects that are in the scene.

    Attributes:
    - color (dict): Color is the color that will be used to highlight the objects.
    - on (ECABoolean): On is a boolean that tells if the highlight is on or off.

    """
    def __init__(self, color: dict, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._color = color
        self._on = on
        self._attr_should_poll = False

    @property
    def color(self) -> dict:
        return self._color

    @property
    def on(self) -> ECABoolean:
        return self._on

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "color": self.color,
            "on": self.on,
            **super_extra_attributes
        }

    @eca_script_action(verb = "changes", variable = "color", modifier = "to")
    async def async_changes(self, c: dict) -> None:
        """
        ChangesColor changes the color of the outline.
        Argument:
            -c:
        """
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb = "turns")
    async def async_turns(self, on: ECABoolean) -> None:
        """
        TurnsOn turns the highlight on or off.
        Argument:
            -on:
        """
        _LOGGER.info(f"Performed turns action - {on}")


class Keypad(ECAEntity):

    """
    Keypad is a  that lets an object to receive codes and trigger
            actions when the code is correct.

    Attributes:
    - keycode (str): Keycode is the code that the keypad will accept.
    - input (str): Input is the input that the keypad is currently holding.

    """
    def __init__(self, keycode: str, input: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._keycode = keycode
        self._input = input
        self._attr_should_poll = False

    @property
    def keycode(self) -> str:
        return self._keycode

    @property
    def input(self) -> str:
        return self._input

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "keycode": self.keycode,
            "input": self.input,
            **super_extra_attributes
        }

    @eca_script_action(verb = "inserts")
    async def async_inserts(self, input: str) -> None:
        """
        Inserts inserts the whole input into the  variable.
        Argument:
            -input:The complete code to be checked
        """
        _LOGGER.info(f"Performed inserts action - {input}")

    @eca_script_action(verb = "adds")
    async def async_adds(self, input: str) -> None:
        """
        Adds adds a single character to the  variable.
        Argument:
            -input:
        """
        _LOGGER.info(f"Performed adds action - {input}")

    @eca_script_action(verb = "resets")
    async def async_resets(self) -> None:
        """
        Resets clears the  variable.
        """
        _LOGGER.info(f"Performed resets action")


class Lock(ECAEntity):

    """
    Lock is a  that locks the  it is attached to.
            It works in a similar way to the  behaviour, but it needs to by unlock by other means (like a key).

    Attributes:
    - locked (ECABoolean): locked defines whether the lock is open or not.

    """
    def __init__(self, locked: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._locked = locked
        self._attr_should_poll = False

    @property
    def locked(self) -> ECABoolean:
        return self._locked

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "locked": self.locked,
            **super_extra_attributes
        }

    @eca_script_action(verb = "opens")
    async def async_opens(self) -> None:
        """
        Opens sets the lock to open.
        """
        _LOGGER.info(f"Performed opens action")

    @eca_script_action(verb = "closes")
    async def async_closes(self) -> None:
        """
        Closes sets the lock to closed.
        """
        _LOGGER.info(f"Performed closes action")


class Particle(ECAEntity):

    """
    Particle is a  that lets the object emit particles.

    Attributes:
    - on (ECABoolean): On is a boolean that indicates if the particle system is active.

    """
    def __init__(self, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._on = on
        self._attr_should_poll = False

    @property
    def on(self) -> ECABoolean:
        return self._on

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "on": self.on,
            **super_extra_attributes
        }

    @eca_script_action(verb = "turns")
    async def async_turns(self, on: ECABoolean) -> None:
        """
        Turns is used to turn on/off the particle system.
        Argument:
            -on:The status of the particle system.
        """
        _LOGGER.info(f"Performed turns action - {on}")


class Placeholder(ECAEntity):

    """
    Placeholder is a  that is used to represent a placeholder in the scene. It will be
            used by the End User Developers in order to import and use custom mesh models.

    Attributes:
    - mesh (dict): newMesh is the mesh model that the object will use.

    """
    def __init__(self, mesh: dict, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._mesh = mesh
        self._attr_should_poll = False

    @property
    def mesh(self) -> dict:
        return self._mesh

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "mesh": self.mesh,
            **super_extra_attributes
        }

    @eca_script_action(verb = "changes", variable = "mesh", modifier = "to")
    async def async_changes(self, meshName: str) -> None:
        """
        Changes sets the new mesh model that the object will use.
        Argument:
            -meshName:The path of the mesh in the user-accessible mesh folder
        """
        _LOGGER.info(f"Performed changes action - {meshName}")


class Sound(ECAEntity):

    """


    Attributes:
    - source (str): Source is the audio filename that serves as the source for playback.
    - volume (float): Volume is the current volume level of the audio.
            Accepts values between 0 and the maximum volume, defined by .
    - maxVolume (float): MaxVolume is the maximum volume level the audio can reach.
    - currentTime (float): currentTime is the current playback position in seconds.
            Tracks the progression of the audio clip.
    - playing (ECABoolean): playing indicates whether the audio is currently playing. The value is either "yes" or "no". If paused or stopped are "yes", playing will be "no".
    - paused (ECABoolean): paused indicates whether the audio playback is paused. The value is either "yes" or "no". When playing again, the audio will resume from the paused time.
    - stopped (ECABoolean): Stopped  indicates whether the audio playback is stopped. The value is either "yes" or "no". When playing again, the audio will start from the beginning.

    """
    def __init__(self, source: str, volume: float, maxVolume: float, currentTime: float, playing: ECABoolean, paused: ECABoolean, stopped: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._source = source
        self._volume = volume
        self._maxVolume = maxVolume
        self._currentTime = currentTime
        self._playing = playing
        self._paused = paused
        self._stopped = stopped
        self._attr_should_poll = False

    @property
    def source(self) -> str:
        return self._source

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def maxVolume(self) -> float:
        return self._maxVolume

    @property
    def currentTime(self) -> float:
        return self._currentTime

    @property
    def playing(self) -> ECABoolean:
        return self._playing

    @property
    def paused(self) -> ECABoolean:
        return self._paused

    @property
    def stopped(self) -> ECABoolean:
        return self._stopped

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "source": self.source,
            "volume": self.volume,
            "maxVolume": self.maxVolume,
            "currentTime": self.currentTime,
            "playing": self.playing,
            "paused": self.paused,
            "stopped": self.stopped,
            **super_extra_attributes
        }

    @eca_script_action(verb = "plays")
    async def async_plays(self) -> None:
        """
        Plays starts the audio playback.
            Updates the state variables playing, stopped, and paused to reflect that playback is active.
        """
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb = "pauses")
    async def async_pauses(self) -> None:
        """
        Pauses pauses the audio playback.
            Maintains the current playback time (currentTime) for resuming later (by calling Plays).
        """
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        """
        Stops stops the audio playback and resets the playback time (currentTime) to the beginning.
        """
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "changes", variable = "volume", modifier = "to")
    async def async_changes_volume(self, v: float) -> None:
        """
        ChangesVolume changes the volume of the audio to a given value.
            Ensures the value remains within the range of 0 to
        Argument:
            -v:The new volume value.
        """
        _LOGGER.info(f"Performed changes_volume action - {v}")

    @eca_script_action(verb = "changes", variable = "source", modifier = "to")
    async def async_changes_source(self, newSource: str) -> None:
        """
        ChangesSource changes the audio filename source to the given filename.
            Validates the path and dynamically loads the audio for playback.
        Argument:
            -newSource:The new audio filename.
        """
        _LOGGER.info(f"Performed changes_source action - {newSource}")


class Switch(ECAEntity):

    """
    Switch is a  that can be use to let an object have an on/off state, useful for
            objects like lights, doors, etc.

    Attributes:
    - on (ECABoolean): On is the state of the switch.

    """
    def __init__(self, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._on = on
        self._attr_should_poll = False

    @property
    def on(self) -> ECABoolean:
        return self._on

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "on": self.on,
            **super_extra_attributes
        }

    @eca_script_action(verb = "turns")
    async def async_turns(self, on: ECABoolean) -> None:
        """
        Turns defines if the switch is on or off.
        Argument:
            -on:The new state of the switch.
        """
        _LOGGER.info(f"Performed turns action - {on}")


class Timer(ECAEntity):

    """
    Represents a time-based  that helps triggering actions after specified durations.
            The Timer class provides functionality to configure, start, pause, stop, and reset a timer, as well as to emit events when specific time milestones are reached or elapsed.

    Attributes:
    - duration (float): Duration specifies the total duration for which the timer will run.
    - current_time (float): Current represents the current time of the timer, meaning the elapsed time from the start. It dynamically updates as the timer counts down.

    """
    def __init__(self, duration: float, current_time: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._duration = duration
        self._current_time = current_time
        self._attr_should_poll = False

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def current_time(self) -> float:
        return self._current_time

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "duration": self.duration,
            "current_time": self.current_time,
            **super_extra_attributes
        }

    @eca_script_action(verb = "changes", variable = "duration", modifier = "to")
    async def async_changes_duration(self, amount: float) -> None:
        """
        ChangesDuration sets the total duration of the timer with a non-negative value.
        Argument:
            -amount:The new duration value for the timer.
        """
        _LOGGER.info(f"Performed changes_duration action - {amount}")

    @eca_script_action(verb = "changes", variable = "current-time", modifier = "to")
    async def async_changes_current_time(self, amount: float) -> None:
        """
        ChangeCurrentTime sets the elapsed time of the timer. It ensures that the new value is within the valid range [0, duration].
        Argument:
            -amount:The new
        """
        _LOGGER.info(f"Performed changes_current_time action - {amount}")

    @eca_script_action(verb = "starts")
    async def async_starts(self) -> None:
        """
        Starts activates the timer to begin counting down, resuming its operation from the last paused state.
        """
        _LOGGER.info(f"Performed starts action")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        """
        Stops deactivates the timer, resetting the elapsed time to zero.
        """
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "pauses")
    async def async_pauses(self) -> None:
        """
        Pauses deactivates the timer, leaving the elapsed time unchanged.
        """
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "reaches")
    async def async_reaches(self, seconds: int) -> None:
        """
        Reaches emits an event when the timer reaches a specified elapsed time. It can be used to trigger actions at predefined points in the elapsed timeline.
        Argument:
            -seconds:The elapsed time at which the event is triggered.
        """
        _LOGGER.info(f"Performed reaches action - {seconds}")

    @eca_script_action(verb = "resets")
    async def async_resets(self) -> None:
        """
        Resets resets the timer to its maximum duration and deactivates it.
        """
        _LOGGER.info(f"Performed resets action")


class Transition(ECAEntity):

    """
    Transition is a  that is used to trigger a transition to another scene.

    Attributes:
    - reference (Scene): Reference is the Unity Scene to transition to.

    """
    def __init__(self, reference: Scene, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._reference = reference
        self._attr_should_poll = False

    @property
    def reference(self) -> Scene:
        return self._reference

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "reference": self.reference,
            **super_extra_attributes
        }

    @eca_script_action(verb = "teleports to")
    async def async_teleports_to(self, reference: Scene) -> None:
        """
        Teleports changes the current scene to the scene referenced by .
        Argument:
            -reference:
        """
        _LOGGER.info(f"Performed teleports_to action - {reference}")


class Trigger(ECAEntity):

    """
    Trigger is a  that can be used to trigger an action without an explicit request
            from the player. If the action is player initiated, then refer to

    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "triggers")
    async def async_triggers(self, action: dict) -> None:
        """
        Triggers emits an event when the trigger is activated.
        Argument:
            -action:The event to trigger in the scene.
        """
        _LOGGER.info(f"Performed triggers action - {action}")


class ClothingCategories(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class POV(ECAEntity):

    """


    Attributes:

    """
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


class ECAXRPointer(ECAEntity):
    """
    ECAXRPointer is a Behaviour subclass that represents a pointable element.

    Attributes:

    """
    def __init__(self, isPointed: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._isPointed = isPointed
        self._attr_should_poll = False

    @property
    def isPointed(self) -> bool:
        return self._isPointed

    @isPointed.setter
    @update_deque(DEQUE_POINTED_OBJECTS)
    def isPointed(self, v: ECABoolean) -> None:
        self._isPointed = v

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "isPointed": self.isPointed,
            **super_extra_attributes
        }


class ECAXRInteractable(ECAEntity):
    """
    ECAXRInteractable is a Behaviour subclass that represents an interactable XR element.

    Attributes:

    """
    def __init__(self, isInteracted: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._isInteracted = isInteracted
        self._attr_should_poll = False

    @property
    def isInteracted(self) -> bool:
        return self._isInteracted

    @isInteracted.setter
    @update_deque(DEQUE_INTERACTED_OBJECTS)
    def isInteracted(self, v: ECABoolean) -> None:
        self._isInteracted = v

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "isInteracted": self.isInteracted,
            **super_extra_attributes
        }


CURRENT_MODULE = sys.modules[__name__]
