# ruff: noqa

import inspect
import logging
import sys
import voluptuous as vol
from collections import deque
from homeassistant.const import CONF_SENSORS
from homeassistant.helpers import config_validation as cv, entity_platform
from .const import *
from .eca_classes import ECABoolean, ECAColor, ECAPosition, ECARotation, ECAScale
from .entity import ECAEntity
from .task_modelling import CounterOrderIndependence
from .utils import (
    MappedClasses,
    eca_script_action,
    decorator_update_deque,
    describe
)

_LOGGER = logging.getLogger(__name__)

# region sensor init
DEQUE_FRAMED_OBJECTS = deque([], maxlen=MAX_LENGTH_CIRCULAR_LIST)

DEQUE_POINTED_OBJECTS = deque([], maxlen=MAX_LENGTH_CIRCULAR_LIST)

DEQUE_INTERACTED_OBJECTS = deque([], maxlen=MAX_LENGTH_CIRCULAR_LIST)

DICT_IOT_DEVICES = dict()

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_ECA_SCRIPT): cv.string,
        vol.Required(CONF_PLATFORM_GAME_OBJECT): cv.string,
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        vol.Optional(CONF_PLATFORM_ATTRIBUTES): dict,
    }
)

GAMEOBJECT_ECASCRIPT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_ECA_SCRIPT): cv.string,
        vol.Required(CONF_PLATFORM_GAME_OBJECT): cv.string,
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        vol.Optional(CONF_PLATFORM_ATTRIBUTES): dict,
    }
)

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
                vol.Optional(CONF_SERVER_UNITY_TOKEN): cv.string,
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
    if not discovery_info:
        return None

    # Task Expressions #
    if CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY in discovery_info:
        counters_names = discovery_info.pop(
            CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY
        )

        if counters_names:
            entities = []
            for name in counters_names:
                entities.append(CounterOrderIndependence(hass, name))

            async_add_entities(entities, True)

            # Salva le entità in hass.data
            hass.data.setdefault(CONF_TASK_MODELLING_ENTITIES, {})
            for entity in entities:
                hass.data[CONF_TASK_MODELLING_ENTITIES][entity.entity_id] = entity

    # ECA Objects #
    ECA_SCRIPTS = MappedClasses.get_eca_scripts()
    if ECA_SCRIPTS is None:
        ECA_SCRIPTS = MappedClasses.mapping_classes(hass)

    if discovery_info is None:
        print("discovery_info is none")
        return None

    eca_script = discovery_info.get(CONF_PLATFORM_ECA_SCRIPT)
    eca_class = (
        ECA_SCRIPTS.get(eca_script)
        if ECA_SCRIPTS and eca_script in ECA_SCRIPTS
        else None
    )
    if not eca_class:
        return None
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

    return True


def get_classes_subclassing(to_string: bool = False) -> list[any]:
    current_module = inspect.getmodule(inspect.currentframe())
    classes = inspect.getmembers(current_module, inspect.isclass)
    subclass_names = [
        cls if not to_string else name.lower()
        for name, cls in classes
        if issubclass(cls, ECAEntity) and cls is not ECAEntity
    ]
    return subclass_names

# endregion ECA scripts

#region ECA Sensors
@describe("ECAObject is the base class for all virtual objects that can be used in the automations. All the other classes in this package inherit from this class or one of its subclasses. It supports properties such as position, rotation, scale, visibility, and activity, and provides methods for moving, rotating, scaling, and controlling visibility.")
class ECAObject(ECAEntity):

    def __init__(self, description: str, position: ECAPosition, rotation: ECARotation, scale: ECAScale, visible: ECABoolean, active: ECABoolean, isInsideCamera: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._description = description
        self._position = position
        self._rotation = rotation
        self._scale = scale
        self._visible = visible
        self._active = active
        self._isInsideCamera = isInsideCamera
        self._attr_should_poll = False

    @property
    @describe("description (str): description describes in a few words what the object is and its role.")
    def description(self) -> str:
        return self._description

    @property
    @describe("position (ECAPosition): p represents the position of the virtual object in the 3D space. It's a vector with three components: x, y, and z.")
    def position(self) -> ECAPosition:
        return self._position

    @property
    @describe("rotation (ECARotation): r represents the rotation of the object in the 3D space. It's a vector with three components: x, y, and z (euler angles).")
    def rotation(self) -> ECARotation:
        return self._rotation

    @property
    @describe("scale (ECAScale): r represents the scale of the object in the 3D space.")
    def scale(self) -> ECAScale:
        return self._scale

    @property
    @describe("visible (ECABoolean): visible indicates whether the object is visible. The allowed values are either 'yes' or 'no'. If invisible, the object is not rendered but remains interactive for collisions.")
    def visible(self) -> ECABoolean:
        return self._visible

    @property
    @describe("active (ECABoolean): active indicates whether the object is active. The allowed values are either 'yes' or 'no'. When inactive, the object is not rendered and does not interact with other objects.")
    def active(self) -> ECABoolean:
        return self._active

    @property
    @describe("isInsideCamera (ECABoolean): isInsideCamera indicates whether the object is currently within the camera's field of view. This property is automatically updated at runtime.")
    def isInsideCamera(self) -> ECABoolean:
        return self._isInsideCamera

    @isInsideCamera.setter
    @decorator_update_deque(DEQUE_FRAMED_OBJECTS)
    def isInsideCamera(self, v: ECABoolean) -> None:
        self._isInsideCamera = v

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "description": self.description,
            "position": self.position,
            "rotation": self.rotation,
            "scale": self.scale,
            "visible": self.visible,
            "active": self.active,
            "isInsideCamera": self.isInsideCamera,
            **super_extra_attributes
        }

    @eca_script_action(verb = "moves to")
    @describe("Moves (to) is a method that moves the object to a specified position in the 3D space. Argument: -obj: The target position to move to.")
    async def async_moves_to(self, newPos: ECAPosition) -> None:
        _LOGGER.info(f"Performed moves_to action - {newPos}")

    @eca_script_action(verb = "moves on")
    @describe("Moves (to) is a method that moves the object to a specified position in the 3D space. Argument: -obj: The target position to move to.")
    async def async_moves_on(self, path: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed moves_on action - {path}")

    @eca_script_action(verb = "rotates around")
    @describe("Rotates sets the object's rotation to a specified value in the 3D space. Argument: -obj: The target rotation expressed as a vector with three components: x, y, and z.")
    async def async_rotates_around(self, newRot: ECARotation) -> None:
        _LOGGER.info(f"Performed rotates_around action - {newRot}")

    @eca_script_action(verb = "looks at")
    @describe("Looks adjusts the object's rotation to face a specified target object. Argument: -obj: The target GameObject to look at.")
    async def async_looks_at(self, o: object) -> None:
        _LOGGER.info(f"Performed looks_at action - {o}")

    @eca_script_action(verb = "scales to")
    @describe("Scales sets the object's scale to a specified value. Argument: -obj: The new scale value fo the object. The scale is a vector with three components: x, y, and z.")
    async def async_scales_to(self, newScale: ECAScale) -> None:
        _LOGGER.info(f"Performed scales_to action - {newScale}")

    @eca_script_action(verb = "restores original settings")
    @describe("Restores the object's original position, rotation, and scale to their initial values.")
    async def async_restores_original_settings(self) -> None:
        _LOGGER.info(f"Performed restores_original_settings action")

    @eca_script_action(verb = "shows")
    @describe("Shows maakes the object visible if it is not already.")
    async def async_shows(self) -> None:
        _LOGGER.info(f"Performed shows action")

    @eca_script_action(verb = "hides")
    @describe("Hides makes the object invisible if it is not already.")
    async def async_hides(self) -> None:
        _LOGGER.info(f"Performed hides action")

    @eca_script_action(verb = "activates")
    @describe("Activates makes the object both interactable and visible.")
    async def async_activates(self) -> None:
        _LOGGER.info(f"Performed activates action")

    @eca_script_action(verb = "deactivates")
    @describe("Deactivates makes the object invisible and non-interactable.")
    async def async_deactivates(self) -> None:
        _LOGGER.info(f"Performed deactivates action")

    @eca_script_action(verb = "changes", variable = "visible", modifier = "to")
    @describe("ShowsHides changes the visibility state of the object based on a parameter. The parameter can be either 'yes' or 'no'. Argument: -obj: The new visibility state.")
    async def async_changes_visible(self, yesNo: ECABoolean) -> None:
        _LOGGER.info(f"Performed changes_visible action - {yesNo}")

    @eca_script_action(verb = "changes", variable = "active", modifier = "to")
    @describe("ActivatesDeactivates changes the active state of the object based on a parameter. The parameter can be either 'yes' or 'no'. Argument: -obj: The new active state.")
    async def async_changes_active(self, yesNo: ECABoolean) -> None:
        _LOGGER.info(f"Performed changes_active action - {yesNo}")


@describe("")
class Vehicle(ECAEntity):

    def __init__(self, speed: float, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._speed = speed
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("speed (float): ")
    def speed(self) -> float:
        return self._speed

    @property
    @describe("on (ECABoolean): ")
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


@describe("")
class AirVehicle(ECAEntity):

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


@describe("")
class LandVehicle(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class SeaVehicle(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class SpaceVehicle(ECAEntity):

    def __init__(self, oxygen: float, gravity: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._oxygen = oxygen
        self._gravity = gravity
        self._attr_should_poll = False

    @property
    @describe("oxygen (float): ")
    def oxygen(self) -> float:
        return self._oxygen

    @property
    @describe("gravity (float): ")
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



class ECASystem(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "starts up")
    @describe("starts up represents the action that triggers the startup process of the virtual system. When executed, it signals that the system has initialized successfully and can serve as a trigger for ECA automation rules that should run at application startup.")
    async def async_starts_up(self) -> None:
        _LOGGER.info(f"Performed starts_up action")


@describe("")
class Scene(ECAEntity):

    def __init__(self, name: str, position: ECAPosition, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._name = name
        self._position = position
        self._attr_should_poll = False

    @property
    @describe("name (str): ")
    def name(self) -> str:
        return self._name

    @property
    @describe("position (ECAPosition): ")
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

    @eca_script_action(verb = "teleports to", is_passive = True)
    async def async_teleports_to(self) -> None:
        _LOGGER.info(f"Performed teleports_to action")



class ECAProp(ECAEntity):

    def __init__(self, price: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._price = price
        self._attr_should_poll = False

    @property
    @describe("price (float): Price: The price of the prop object.")
    def price(self) -> float:
        return self._price

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "price": self.price,
            **super_extra_attributes
        }


@describe("Interactable is a component that can be attached to an object in order to make it interactable with other objects collision.")
class ECAInteractable(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("ECACharacter is a behavior component that represents a versatile entity within the ECA rules framework. It can embody different forms such as animals, humanoids, robots, or other autonomous or player-controlled beings. The component supports a wide range of actions and state attributes, enabling dynamic interaction with the environment.")
class ECACharacter(ECAEntity):

    def __init__(self, life: float, playing: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._life = life
        self._playing = playing
        self._attr_should_poll = False

    @property
    @describe("life (float): life is the current life of the character, represented as a float number.")
    def life(self) -> float:
        return self._life

    @property
    @describe("playing (ECABoolean): playing indicates whether the character is controlled by the player ('yes') or operating autonomously ('no').")
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
    @describe("Interacts enables the character to interact with a specified interactable object. The implementation details are managed by the ECAInteractable class logic. Argument: -obj: The target interactable object")
    async def async_interacts_with(self, o: ECAInteractable) -> None:
        _LOGGER.info(f"Performed interacts_with action - {o}")

    @eca_script_action(verb = "stops-interacting with")
    @describe("Stops interaction allows the character to stop its interaction with a specified interactable object. The implementation details are managed by the ECAInteractable class logic. Argument: -obj: The target interactable object")
    async def async_stops_interacting_with(self, o: ECAInteractable) -> None:
        _LOGGER.info(f"Performed stops_interacting_with action - {o}")

    @eca_script_action(verb = "points to")
    @describe("Points the character to point at a specified object, emphasizing its focus or attention on the target. Argument: -obj: The target object to point at.")
    async def async_points_to(self, o: ECAObject) -> None:
        _LOGGER.info(f"Performed points_to action - {o}")

    @eca_script_action(verb = "stops-pointing to")
    @describe("StopsPointing commands the character to stop pointing at a specified object, ceasing its focus or attention on the target. Argument: -obj: The target object to stop pointing at.")
    async def async_stops_pointing_to(self, o: ECAObject) -> None:
        _LOGGER.info(f"Performed stops_pointing_to action - {o}")

    @eca_script_action(verb = "jumps to")
    @describe("Jumps commands the character to jump to a specific position in the 3D world. Argument: -obj: The destination position where the character will jump.")
    async def async_jumps_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed jumps_to action - {p}")

    @eca_script_action(verb = "jumps on")
    @describe("Jumps commands the character to jump to a specific position in the 3D world. Argument: -obj: The destination position where the character will jump.")
    async def async_jumps_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed jumps_on action - {p}")

    @eca_script_action(verb = "starts-animation")
    @describe("StartsAnimation triggers a predefined animation for the character, using the provided animation identifier. Argument: -obj: The string of the animation clip to play")
    async def async_starts_animation(self, s: str) -> None:
        _LOGGER.info(f"Performed starts_animation action - {s}")


@describe("ECAAnimal is a component that represents an animal character within the ECA rules framework. It extends ECACharacter to provide animal-specific traits and behaviors, enabling actions and interactions characteristic of animal entities.")
class ECAAnimal(ECAEntity):

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
    @describe("Speaks allows the animal to produce a sound or \"speak\" by playing an associated audio clip. The audio clip is identified by the provided string, which must correspond to a valid resource. Argument: -obj: The name of the audio resource to be played.")
    async def async_speaks(self, s: str) -> None:
        _LOGGER.info(f"Performed speaks action - {s}")


@describe("The Mannequin class provides a way to include a character in the scene to wear 3D models of clothes that do not have rigging skeletons. Since the mannequin is supposed to stay still in the environment, the implementation contains for automatically positioning it on top of the mannequin according to the specified position (e.g., head, torso, left or right leg, arm, etc.). Provided that the distinction between a mannequin and a not-playable human is technical, it is up to the Unity developer to decide which object offers the best configuration options considering the template under development.")
class Mannequin(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("Clothing: This class is used to define the clothing properties of the objects.")
class Clothing(ECAEntity):

    def __init__(self, brand: str, color: dict, size: str, weared: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._brand = brand
        self._color = color
        self._size = size
        self._weared = weared
        self._attr_should_poll = False

    @property
    @describe("brand (str): Brand: This property is used to define the brand of the clothing.")
    def brand(self) -> str:
        return self._brand

    @property
    @describe("color (dict): Color: This property is used to define the color of the clothing.")
    def color(self) -> dict:
        return self._color

    @property
    @describe("size (str): ")
    def size(self) -> str:
        return self._size

    @property
    @describe("weared (ECABoolean): Weared: This property is used to define if the clothing is weared or not.")
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

    @eca_script_action(verb = "wears", is_passive = True)
    @describe("_Wears: This method is used to allow the mannequin to wear the clothing. Argument: -subject: The mannequin that wears the clothing")
    async def async_wears_(self, m: Mannequin) -> None:
        _LOGGER.info(f"Performed wears_ action - {m}")

    @eca_script_action(verb = "unwears", is_passive = True)
    @describe("_Unwears: This method is used to allow the mannequin to unwear the clothing. Argument: -subject: The mannequin that unwears the clothing")
    async def async_unwears_(self, m: Mannequin) -> None:
        _LOGGER.info(f"Performed unwears_ action - {m}")

    @eca_script_action(verb = "wears", is_passive = True)
    @describe("_Wears: This method is used to allow the mannequin to wear the clothing. Argument: -subject: The mannequin that wears the clothing")
    async def async_wears_(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed wears_ action - {c}")

    @eca_script_action(verb = "unwears", is_passive = True)
    @describe("_Unwears: This method is used to allow the mannequin to unwear the clothing. Argument: -subject: The mannequin that unwears the clothing")
    async def async_unwears_(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed unwears_ action - {c}")


@describe("ECADoor: This class is used to define a door beviour.")
class ECADoor(ECAEntity):

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


@describe("ECAWindow is a component that represents a virtual window within the environment. It can be used as part of automation rules involving environmental interactions, such as opening or closing actions.")
class ECAWindow(ECAEntity):

    def __init__(self, isOpen: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._isOpen = isOpen
        self._attr_should_poll = False

    @property
    @describe("isOpen (ECABoolean): isOpen is a boolean state variable that indicates whether a window is open. Its value is automatically updated when the window executes the opens or closes action. This variable can be used as a condition within automation rules related to environmental control.")
    def isOpen(self) -> ECABoolean:
        return self._isOpen

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "isOpen": self.isOpen,
            **super_extra_attributes
        }

    @eca_script_action(verb = "opens")
    @describe("opens represents the action of opening a window. When executed, if the window is currently closed ( isOpen = false), it automatically updates the internal state variable isOpen to true and rotates the window to its predefined open position. Executing this action may be involved in automations related to ventilation, lighting, or other environmental interactions that depend on the window’s open state.")
    async def async_opens(self) -> None:
        _LOGGER.info(f"Performed opens action")

    @eca_script_action(verb = "closes")
    @describe("closes represents the action of closing a window. When executed, if the window is currently open ( isOpen = true), it automatically updates the internal state variable isOpen to false and rotates the window to its predefined closed position. This action may be involed in automations related to ventilation, insulation, energy efficiency, or security.")
    async def async_closes(self) -> None:
        _LOGGER.info(f"Performed closes action")


@describe("Electronic class is used to create and manage electronics objects, which are used to interact with the game.")
class Electronic(ECAEntity):

    def __init__(self, brand: str, model: str, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._brand = brand
        self._model = model
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("brand (str): Brand is the brand of the electronic.")
    def brand(self) -> str:
        return self._brand

    @property
    @describe("model (str): Model is the model of the electronic.")
    def model(self) -> str:
        return self._model

    @property
    @describe("on (ECABoolean): On is the state of the electronic.")
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
    @describe("Turns: Turns the electronic on or off. Argument: -obj: A boolean for the new state of the electronic")
    async def async_turns(self, on: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {on}")


@describe("Food is a class that represents something that can be eaten.")
class Food(ECAEntity):

    def __init__(self, weight: float, expiration: str, description: str, eaten: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._weight = weight
        self._expiration = expiration
        self._description = description
        self._eaten = eaten
        self._attr_should_poll = False

    @property
    @describe("weight (float): Weight: is the weight of the food.")
    def weight(self) -> float:
        return self._weight

    @property
    @describe("expiration (str): Expiration: is the expiration date of the food.")
    def expiration(self) -> str:
        return self._expiration

    @property
    @describe("description (str): Description: is the description of the food.")
    def description(self) -> str:
        return self._description

    @property
    @describe("eaten (ECABoolean): Eaten: is true if the food has been eaten.")
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

    @eca_script_action(verb = "eats", is_passive = True)
    @describe("_Eats is the method that is called when the food is eaten. This is a passive action, so the Food type is not in the subject of the action, but on the object. Argument: -subject: The character that eats the food")
    async def async_eats(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed eats action - {c}")


@describe("")
class SprayType(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("Spray is a class that represents a spray.")
class Spray(ECAEntity):

    def __init__(self, charge: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._charge = charge
        self._attr_should_poll = False

    @property
    @describe("charge (float): Charge: a float value that represents the charge of the spray.")
    def charge(self) -> float:
        return self._charge

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "charge": self.charge,
            **super_extra_attributes
        }

    @eca_script_action(verb = "changes", variable = "SprayType", modifier = "to")
    @describe("ChangesSprayType changes the spray type. Argument: -obj: The new SprayType value.")
    async def async_changes(self, type: SprayType) -> None:
        _LOGGER.info(f"Performed changes action - {type}")

    @eca_script_action(verb = "sprays")
    @describe("Sprays: The action of using the spray. It decreases the charge of the spray.")
    async def async_sprays(self) -> None:
        _LOGGER.info(f"Performed sprays action")


@describe("The Weapon class is a base class for all weapons.")
class Weapon(ECAEntity):

    def __init__(self, power: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._power = power
        self._attr_should_poll = False

    @property
    @describe("power (float): Power: a float value that represents the power of the weapon.")
    def power(self) -> float:
        return self._power

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "power": self.power,
            **super_extra_attributes
        }


@describe("Bullet: this class it is a type of Weapon that is usually expelled from another object in the scene, usually a Firearm object")
class Bullet(ECAEntity):

    def __init__(self, speed: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._speed = speed
        self._attr_should_poll = False

    @property
    @describe("speed (float): Speed: this is the speed of the bullet")
    def speed(self) -> float:
        return self._speed

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "speed": self.speed,
            **super_extra_attributes
        }


@describe("The EdgedWeapon class is a Weapon that has a sharp edge.")
class EdgedWeapon(ECAEntity):

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
    @describe("Stabs: The action that occurs when a player stabs another ECAObject. Argument: -obj: The ECAObject that has been stabbed")
    async def async_stabs(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed stabs action - {obj}")

    @eca_script_action(verb = "slices")
    @describe("Stabs: The action that occurs when a player slices another ECAObject. Argument: -obj: The ECAObject that has been sliced")
    async def async_slices(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed slices action - {obj}")


@describe("Firearm is a class that represents a firearm, a firearm can expel bullets.")
class Firearm(ECAEntity):

    def __init__(self, charge: int, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._charge = charge
        self._attr_should_poll = False

    @property
    @describe("charge (int): Charge is the current charge of the firearm.")
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
    @describe("Recharges: The action of recharging the firearm. It plays the particle system and increases the charge. Argument: -obj: The amount of charge")
    async def async_recharges(self, charge: int) -> None:
        _LOGGER.info(f"Performed recharges action - {charge}")

    @eca_script_action(verb = "fires")
    @describe("Fires: The action of firing the firearm. It plays the particle system and decreases the charge. Argument: -obj: The ECAObject that has been shot")
    async def async_fires(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed fires action - {obj}")

    @eca_script_action(verb = "aims")
    @describe("Aims: The action of aiming the firearm. Argument: -obj: ")
    async def async_aims(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed aims action - {obj}")


@describe("Shield class allows to create a shield for defending from a Weapon.")
class Shield(ECAEntity):

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
    @describe("Blocks: This action allows to block the Weapon attack. Argument: -obj: ")
    async def async_blocks(self, weapon: Weapon) -> None:
        _LOGGER.info(f"Performed blocks action - {weapon}")


@describe("ECALiquidDispenser is a component that represents a virtual dispenser capable of releasing or filling containers with specific types of liquids within the environment. It allows the definition of the liquid type it dispenses, such as water, degreaser, disinfectant, or battery killer, and integrates with other ECA components to support automated filling and wetting actions.")
class ECALiquidDispenser(ECAEntity):

    def __init__(self, liquidType: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._liquidType = liquidType
        self._attr_should_poll = False

    @property
    @describe("liquidType (str): liquidType specifies the type of liquid dispensed by this object. Possible values include 'water', 'degreaser', 'amuchina', and 'battery killer'.")
    def liquidType(self) -> str:
        return self._liquidType

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "liquidType": self.liquidType,
            **super_extra_attributes
        }


@describe("ECABottle is a component that represents a virtual bottle capable of containing and dispensing liquid within the environment. It maintains internal state variables such as capOpen and flipped, and interacts with objects equipped with an ECALiquidDispenser component to manage liquid flow and spawning. The bottle provides actions for flipping, opening or closing the cap, and starting or stopping the liquid flow. Several default automation rules are initialized at startup: - Flipping the bottle downward while the cap is open causes liquid to flow. - Flipping the bottle upward stops the liquid flow. - Closing the cap stops the liquid flow. - Opening the cap while the bottle is flipped downward resumes the liquid flow.")
class ECABottle(ECAEntity):

    def __init__(self, capOpen: ECABoolean, flipped: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._capOpen = capOpen
        self._flipped = flipped
        self._attr_should_poll = False

    @property
    @describe("capOpen (ECABoolean): capOpen indicates whether the cap of the bottle is open (YES) or closed (NO).")
    def capOpen(self) -> ECABoolean:
        return self._capOpen

    @property
    @describe("flipped (ECABoolean): flipped indicates whether the bottle is currently flipped upside down (YES) or upright (NO).")
    def flipped(self) -> ECABoolean:
        return self._flipped

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "capOpen": self.capOpen,
            "flipped": self.flipped,
            **super_extra_attributes
        }

    @eca_script_action(verb = "opens-cap", is_passive = True)
    @describe("opens-cap represents the action of opening the cap of a bottle equipped with an ECABottle component. When executed, it sets the internal state variable capOpen to true and, if the bottle is flipped downward, triggers the drops-liquid action to start the liquid flow.")
    async def async_opens_cap(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed opens_cap action - {c}")

    @eca_script_action(verb = "closes-cap", is_passive = True)
    @describe("closes-cap represents the action of closing the cap of a bottle equipped with an ECABottle component. When executed, it sets the internal state variable capOpen to false and triggers the stops-dropping action to halt any ongoing liquid flow.")
    async def async_closes_cap(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed closes_cap action - {c}")

    @eca_script_action(verb = "flips-down")
    @describe("flips-down represents the action of turning a bottle equipped with an ECABottle component upside down. When executed, it updates the internal state variable flipped to true and, if the cap is open, triggers the drops-liquid action to start the liquid flow.")
    async def async_flips_down(self) -> None:
        _LOGGER.info(f"Performed flips_down action")

    @eca_script_action(verb = "flips-up")
    @describe("flips-up represents the action of turning a bottle equipped with an ECABottle component to an upright position. When executed, it updates the internal state variable flipped to false and stops any ongoing liquid flow if the bottle was previously pouring.")
    async def async_flips_up(self) -> None:
        _LOGGER.info(f"Performed flips_up action")

    @eca_script_action(verb = "drops-liquid")
    @describe("drops liquid represents the action that initiates the release of liquid from the spawner associated with an object equipped with an ECABottle component. When executed, it starts the spawning of liquid particles or drops within the environment.")
    async def async_drops_liquid(self) -> None:
        _LOGGER.info(f"Performed drops_liquid action")

    @eca_script_action(verb = "stops-dropping")
    @describe("stops dropping represents the internal action that stops the flow of liquid from an object equipped with an ECABottle component. When executed, it halts the spawning of liquid particles or drops and updates the dispenser’s internal state to indicate that the liquid flow has stopped.")
    async def async_stops_dropping(self) -> None:
        _LOGGER.info(f"Performed stops_dropping action")


@describe("ECAWaterMixerTap is a component that represents a virtual water mixer tap within the environment. It can be turned to the left, idle (center), or right positions, corresponding respectively to warm, neutral, and cold water flow states. Several default automation rules are initialized at startup: - Turning left starts the flow of warm water. - Turning right starts the flow of cold water. - Returning to the idle (center) position stops the water flow. The component provides properties and actions for controlling its rotation state, managing the water flow, and responding to user interactions or automation triggers.")
class ECAWaterMixerTap(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "flows-warm-water")
    @describe("flows-warm-water represents the action that causes an object equipped with an ECAWaterMixerTap component, typically a tap, to emit warm water.")
    async def async_flows_warm_water(self) -> None:
        _LOGGER.info(f"Performed flows_warm_water action")

    @eca_script_action(verb = "flows-cold-water")
    @describe("FlowsColdWater causes the tap to emit cold water.")
    async def async_flows_cold_water(self) -> None:
        _LOGGER.info(f"Performed flows_cold_water action")

    @eca_script_action(verb = "stops-flowing-water")
    @describe("StopFlowingWater stops any water from flowing.")
    async def async_stops_flowing_water(self) -> None:
        _LOGGER.info(f"Performed stops_flowing_water action")

    @eca_script_action(verb = "turns-left", is_passive = True)
    @describe("TurnsLeft is an action where a character turns the tap handle to the left. Argument: -subject: The character performing the action.")
    async def async_turns_left(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed turns_left action - {c}")

    @eca_script_action(verb = "turns-idle", is_passive = True)
    @describe("TurnsIdle is an action where a character returns the tap handle to the center (idle) position. Argument: -subject: The character performing the action.")
    async def async_turns_idle(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed turns_idle action - {c}")

    @eca_script_action(verb = "turns-right", is_passive = True)
    @describe("TurnsRight is an action where a character turns the tap handle to the right. Argument: -subject: The character performing the action.")
    async def async_turns_right(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed turns_right action - {c}")


@describe("ECALiquidContainer is a component that represents a virtual container capable of holding different types of virtual liquids and tracking their fill levels within the environment.")
class ECALiquidContainer(ECAEntity):

    def __init__(self, waterDrops: int, degreaserDrops: int, batteryKillerDrops: int, amuchinaDrops: int, temperature: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._waterDrops = waterDrops
        self._degreaserDrops = degreaserDrops
        self._batteryKillerDrops = batteryKillerDrops
        self._amuchinaDrops = amuchinaDrops
        self._temperature = temperature
        self._attr_should_poll = False

    @property
    @describe("waterDrops (int): waterDrops counts how many water drops have been added to the container.")
    def waterDrops(self) -> int:
        return self._waterDrops

    @property
    @describe("degreaserDrops (int): degreaserDrops counts how many degreaser drops have been added to the container.")
    def degreaserDrops(self) -> int:
        return self._degreaserDrops

    @property
    @describe("batteryKillerDrops (int): batteryKillerDrops counts how many battery killer drops have been added to the container.")
    def batteryKillerDrops(self) -> int:
        return self._batteryKillerDrops

    @property
    @describe("amuchinaDrops (int): amuchinaDrops counts how many amuchina drops have been added to the container.")
    def amuchinaDrops(self) -> int:
        return self._amuchinaDrops

    @property
    @describe("temperature (float): temperature represents the current temperature of the liquid mixture inside the container. It is updated dynamically as new liquid drops with different temperatures are added.")
    def temperature(self) -> float:
        return self._temperature

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "waterDrops": self.waterDrops,
            "degreaserDrops": self.degreaserDrops,
            "batteryKillerDrops": self.batteryKillerDrops,
            "amuchinaDrops": self.amuchinaDrops,
            "temperature": self.temperature,
            **super_extra_attributes
        }

    @eca_script_action(verb = "fills-in", is_passive = True)
    @describe("fills-in represents the action performed when an object equipped with an ECALiquidContainer component is filled by an object equipped with an ECALiquidDispenser component. Argument: -subject: The object equipped with an ECALiquidDispenser component that fills the container.")
    async def async_fills_in(self, dispenser: ECALiquidDispenser) -> None:
        _LOGGER.info(f"Performed fills_in action - {dispenser}")


@describe("ECABucket is a component that represents a virtual bucket capable of containing different types of virtual liquids within the environment. It extends the functionality of ECALiquidContainer by specializing it as a bucket-type container. The bucket can be filled with liquids such as water, degreaser, disinfectant, or battery killer, and provides visual feedback to indicate both the current fill level and the type of liquid contained.")
class ECABucket(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("ECACleaningItem is a base component that represents a generic cleaning tool. It provides shared properties and behaviors for all cleaning-related objects and enables integration with other components and ECA-based automation rules.")
class ECACleaningItem(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("ECAEnvironment is a component that represents non-interactable elements of the environment. Unlike props ( ECAProp), environment items cannot be directly manipulated or interacted with by objects equipped with an ECACharacter component.")
class ECAEnvironment(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("ECASurface is a component that represents a virtual surface within the automation environment. It defines surfaces such as tables, floors, walls, or ceilings that can be detected and interacted with by cleaning items ( ECACleaningItem) or other objects.")
class ECASurface(ECAEntity):

    def __init__(self, type: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._type = type
        self._attr_should_poll = False

    @property
    @describe("type (str): type specifies the kind of surface represented by an object equipped with the ECASurface component. Valid values include 'table', 'floor', 'wall', and 'ceiling'. This attribute is used by cleaning items to determine how to interact with the surface.")
    def type(self) -> str:
        return self._type

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "type": self.type,
            **super_extra_attributes
        }


@describe("ECABroom is a component that represents broom objects within the environment. It defines the properties and capabilities associated with virtual brooms used in automation scenarios.")
class ECABroom(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "sweeps")
    @describe("sweeps represents a triggerable interaction performed by a broom on an object equipped with an ECASurface component. When sweeps is used as a trigger in an ECA automation, it implicitly defines a causal action within the same automation. Specifically, if the swept surface is equipped with both ECASurface and ECADustBall components, the trigger sweeps MUST result in the execution of the removes-dust-with-broom action. This action removes all dust balls present on the surface. Therefore, in an ECA rule, sweeps should be interpreted not only as a trigger condition but also as a semantic indicator that the automation includes the action removes-dust-with-broom applied to the same surface involved in the trigger. Optionally, the removal of dust can enable secondary actions (e.g., dust collection) by nearby objects equipped with an ECADustPan component. Argument: -obj: The object equipped with an ECASurface component representing the surface being swept.")
    async def async_sweeps(self, surface: ECASurface) -> None:
        _LOGGER.info(f"Performed sweeps action - {surface}")


@describe("ECASoakableCleaningItem is a component that represents a reusable virtual cleaning item capable of absorbing and releasing various types of liquids, such as water, degreaser, battery killer, or disinfectant. It can be wetted or dried and maintains its current state through dedicated ECA boolean variables, which indicate the presence or absence of specific absorbed substances.")
class ECASoakableCleaningItem(ECAEntity):

    def __init__(self, hasWater: ECABoolean, hasDegreaser: ECABoolean, hasBatteryKiller: ECABoolean, hasAmuchina: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._hasWater = hasWater
        self._hasDegreaser = hasDegreaser
        self._hasBatteryKiller = hasBatteryKiller
        self._hasAmuchina = hasAmuchina
        self._attr_should_poll = False

    @property
    @describe("hasWater (ECABoolean): hasWater indicates whether the item currently contains water.")
    def hasWater(self) -> ECABoolean:
        return self._hasWater

    @property
    @describe("hasDegreaser (ECABoolean): hasDegreaser indicates whether the item currently contains degreaser.")
    def hasDegreaser(self) -> ECABoolean:
        return self._hasDegreaser

    @property
    @describe("hasBatteryKiller (ECABoolean): hasBatteryKiller indicates whether the item currently contains battery killer solution.")
    def hasBatteryKiller(self) -> ECABoolean:
        return self._hasBatteryKiller

    @property
    @describe("hasAmuchina (ECABoolean): hasAmuchina indicates whether the item currently contains Amuchina (a disinfectant).")
    def hasAmuchina(self) -> ECABoolean:
        return self._hasAmuchina

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "hasWater": self.hasWater,
            "hasDegreaser": self.hasDegreaser,
            "hasBatteryKiller": self.hasBatteryKiller,
            "hasAmuchina": self.hasAmuchina,
            **super_extra_attributes
        }

    @eca_script_action(verb = "wets", is_passive = True)
    @describe("wets represents the action in which an object equipped with the ECASoakableCleaningItem component, such as a cloth, rag, or paper towel, becomes wet after being poured on by an object equipped with the ECALiquidDispenser component, such as a bottle or sprayer within the environment. When the ECASoakableCleaningItem is wetted, this event acts as a trigger within an ECA automation. The resulting state change depends on the liquid dispensed: - When the ECALiquidDispenser contains water, the cleaning item implicitly performs the action changes-has-water. - When the ECALiquidDispenser contains degreaser, it implicitly performs the action changes-has-dDegreaser. - When the ECALiquidDispenser contains amuchina, it implicitly performs the action changes-has-amuchina. Executing this action updates the internal state of the cleaning item to reflect the absorbed liquid.")
    async def async_wets(self, ld: ECALiquidDispenser) -> None:
        _LOGGER.info(f"Performed wets action - {ld}")

    @eca_script_action(verb = "dries")
    @describe("Dries is an action method that resets the item to a dry state, both visually and logically by clearing the water state variable.")
    async def async_dries(self) -> None:
        _LOGGER.info(f"Performed dries action")

    @eca_script_action(verb = "changes has water")
    @describe("changes has water represents the implicit action performed when an object equipped with an ECASoakableCleaningItem component absorbs water due to the wets action triggered by an object equipped with a ECALiquidDispenser component whose liquidSpawner property is explicitly set to water (e.g., a spruzzino object). In other words, this action is only applicable if the liquid dispenser is configured to dispense water; liquid dispensers configured with any other liquid do not trigger this state change. When this condition is satisfied, the action updates the internal state of the cleaning item by setting the hasWater variable to true, indicating that the object has absorbed water and is now ready for water-based cleaning operations.")
    async def async_changes_has_water(self) -> None:
        _LOGGER.info(f"Performed changes_has_water action")

    @eca_script_action(verb = "changes has degreaser")
    @describe("changes-has-degreaser represents the implicit action performed when an object equipped with an ECASoakableCleaningItem component absorbs degreaser due to the wets action triggered by an object equipped with a ECALiquidDispenser component whose liquidSpawner property is explicitly set to degreaser (e.g., spruzzinosgrassatore object). In other words, this action is only applicable if the liquid dispenser is configured to dispense degreaser; liquid dispensers configured with any other liquid do not trigger this state change. When this condition is satisfied, the action updates the internal state of the cleaning item by setting the hasDegreaser variable to true, indicating that the object has absorbed degreaser and is therefore ready for degreasing operations.")
    async def async_changes_has_degreaser(self) -> None:
        _LOGGER.info(f"Performed changes_has_degreaser action")

    @eca_script_action(verb = "changes has amuchina")
    @describe("changes-has-amuchina represents the implicit action performed when an object equipped with an ECASoakableCleaningItem component absorbs amuchina due to the wets action triggered by an object equipped with a ECALiquidDispenser component whose liquidSpawner property is explicitly set to amuchina (e.g., spruzzinoamuchina object). In other words, this action is only applicable if the liquid dispenser is configured to dispense amuchina; liquid dispensers configured with any other liquid do not trigger this state change. When this condition is satisfied, the action updates the internal state of the cleaning item by setting the hasAmuchina variable to true, indicating that the object has absorbed amuchina and is therefore ready for sanitizing operations.")
    async def async_changes_has_amuchina(self) -> None:
        _LOGGER.info(f"Performed changes_has_amuchina action")


@describe("ECACleaningRag is a component that represents a cleaning rag object used to wash objects equipped with an ECASurface component.")
class ECACleaningRag(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "washes")
    @describe("washes simulates the cleaning action performed by a rag on an object equipped with an ECASurface component, typically a surface within the environment. When executed, it removes dirt, dust, or stains from the surface. If the rag contains water or detergent, the action represents a washing process; otherwise, it performs a dry wiping action. Both cases trigger the washes automation event. When interacting with surfaces equipped with an ECAOilStain component, it removes oil stains, and when the surface includes an ECADustBall component, it removes dust balls. This method is automatically invoked when the rag comes into contact with an object equipped with an ECASurface component, typically detected through a collision event. Argument: -obj: The object equipped with an ECASurface component representing the surface to be cleaned.")
    async def async_washes(self, surface: ECASurface) -> None:
        _LOGGER.info(f"Performed washes action - {surface}")


@describe("ECAScottex represents a virtual disposable paper towel used to clean an object equipped with an ECASurface component, typically a surface within the environment.")
class ECAScottex(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "sweeps")
    @describe("sweeps represents the action of a paper towel (or scottex) cleaning an object equipped with an ECASurface component, typically representing a surface within the environment. This method is usually invoked when the paper towel comes into contact with an object equipped with an ECASurface component. When sweeps is used as a trigger in an ECA automation, if it interacts with objects equipped with both ECASurface and ECADustBall components, it MUST trigger in the same automation the corresponding removes-dust-with-scottex action (that removes the dust from the surface). Argument: -obj: The object equipped with an ECASurface component representing the surface to be swept.")
    async def async_sweeps(self, surface: ECASurface) -> None:
        _LOGGER.info(f"Performed sweeps action - {surface}")


@describe("The EcaDustBall component represents the presence of dust on a virtual object, typically a surface equipped with an see ECASurface component. Dust can be swept away using specialized objects such as brooms, rags, or scottex equipped with an ( ECACleaningItem) component. After being swept, the object updates its state through the `allSwept` property.")
class ECADustBall(ECAEntity):

    def __init__(self, allSwept: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._allSwept = allSwept
        self._attr_should_poll = False

    @property
    @describe("allSwept (ECABoolean): allSwept indicates whether all the dust has been successfully removed from the object.")
    def allSwept(self) -> ECABoolean:
        return self._allSwept

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "allSwept": self.allSwept,
            **super_extra_attributes
        }

    @eca_script_action(verb = "removes-dust-with-scottex", is_passive = True)
    @describe("removes-dust-with-scottex defines the sweeping action performed by an object equipped with an ECAScottex component. When the action is executed, the dust balls are removed. Typically, this is the result of a wipes event performed by an object equipped with an ECAScottex. Argument: -subject: The object equipped with an ECAScottex component responsible for performing the sweeping action.")
    async def async_removes_dust_with_scottex(self, scottex: ECAScottex) -> None:
        _LOGGER.info(f"Performed removes_dust_with_scottex action - {scottex}")

    @eca_script_action(verb = "removes-dust-with-broom", is_passive = True)
    @describe("removes-dust-with-scottex defines the sweeping action performed by an object equipped with an ECAScottex component. When the action is executed, the dust balls are removed. Typically, this is the result of a wipes event performed by an object equipped with an ECAScottex. Argument: -subject: The object equipped with an ECAScottex component responsible for performing the sweeping action.")
    async def async_removes_dust_with_broom(self, broom: ECABroom) -> None:
        _LOGGER.info(f"Performed removes_dust_with_broom action - {broom}")


@describe("ECADustPan is a component that represents a virtual dustpan used in cleaning tasks within the environment. It interacts with objects equipped with an ECADustBall component and allows the collection and containment of dust balls that have been previously removed or swept by other cleaning tools.")
class ECADustPan(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "collects-dust")
    @describe("collects-dust simulates the action of a dustpan collecting a dust ball from an object equipped with the ECADustBall component, generally a surface within the environment. This method is typically triggered after a sweeps action performed by an object equipped with an ECABroom component, often in combination with the remove-dust action of an ECADustBall component. When executed, it transfers the dust ball into the dustpan, updating its collected state Argument: -obj: The ECADustBall object being collected by the dustpan.")
    async def async_collects_dust(self, dustBall: ECADustBall) -> None:
        _LOGGER.info(f"Performed collects_dust action - {dustBall}")


@describe("ECAMop is a component that represents a virtual mop used to wash objects equipped with an ECASurface component, typically representing surfaces within the environment.")
class ECAMop(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "washes")
    @describe("washes specifies the action of a mop cleaning an object equipped with an ECASurface component, typically representing a surface within the environment. This method is typically invoked when the mop comes into contact with an object equipped with an ECASurface component, and it assumes that the mop has the property hasWater set to true. When washes is used as a trigger in an ECA automation, if it interacts with objects equipped with both ECASurface and ECAOilStain components, it MUST trigger in the same automation the corresponding removes-stain-with-mop action (that removes dirt, liquid residues, or stains from the surface as part of the cleaning process). Argument: -obj: The object equipped with an ECASurface component representing the surface to be cleaned.")
    async def async_washes(self, surface: ECASurface) -> None:
        _LOGGER.info(f"Performed washes action - {surface}")



class ECAInteraction(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("Button is an ECAInteraction subclass that represents a button. When a ECAButton is pressed, it will trigger an event defined by the End User Developer.")
class ECAButton(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }

    @eca_script_action(verb = "pushes", is_passive = True)
    @describe("Presses is a passive function that represents the pressing of the button by a character C. Argument: -subject: The ECACharacter who presses the button.")
    async def async_pushes(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed pushes action - {c}")


@describe("")
class POV(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("ECACamera is an !:Interaction subclass that allows the user to interact with the camera the script is attached to.")
class ECACamera(ECAEntity):

    def __init__(self, pov: POV, zoomLevel: float, playing: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._pov = pov
        self._zoomLevel = zoomLevel
        self._playing = playing
        self._attr_should_poll = False

    @property
    @describe("pov (POV): POV is the camera's point of view.")
    def pov(self) -> POV:
        return self._pov

    @property
    @describe("zoomLevel (float): zoomLevel is the camera's zoom level.")
    def zoomLevel(self) -> float:
        return self._zoomLevel

    @property
    @describe("playing (ECABoolean): Playing is a boolean that indicates whether the camera is currently playing.")
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
    @describe("ZoomsIn reduces the camera's zoom level by the specified amount. If the resulting zoom is less than 30 the zoom is set to 30. Argument: -obj: The amount of zoom to remove")
    async def async_zooms_in(self, amount: float) -> None:
        _LOGGER.info(f"Performed zooms_in action - {amount}")

    @eca_script_action(verb = "zooms-out")
    @describe("ZoomsOut increases the camera's zoom level by the specified amount. If the resulting zoom is greater than 100 the zoom is set to 100. Argument: -obj: The amount of zoom to add")
    async def async_zooms_out(self, amount: float) -> None:
        _LOGGER.info(f"Performed zooms_out action - {amount}")

    @eca_script_action(verb = "changes", variable = "POV", modifier = "to")
    @describe("ChangesPov changes the camera's point of view. Argument: -obj: The new POV value.")
    async def async_changes(self, pov: POV) -> None:
        _LOGGER.info(f"Performed changes action - {pov}")


@describe("ECALight represents a controllable light source in the environment. The ECALight class extends ECAInteraction to manage light properties such as intensity, color, and if it's on.")
class ECALight(ECAEntity):

    def __init__(self, intensity: float, maxIntensity: float, color: dict, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._intensity = intensity
        self._maxIntensity = maxIntensity
        self._color = color
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("intensity (float): intensity represents the brightness level of the light source. It cannot exceed the maximum intensity value.")
    def intensity(self) -> float:
        return self._intensity

    @property
    @describe("maxIntensity (float): maxIntensity specifies the upper limit for the light's brightness. It ensures that the light's intensity does not exceed a predefined threshold.")
    def maxIntensity(self) -> float:
        return self._maxIntensity

    @property
    @describe("color (dict): color represents the color of the light source. The value is a string that represents the color name (e.g., 'red', 'blue', 'green').")
    def color(self) -> dict:
        return self._color

    @property
    @describe("on (ECABoolean): on indicates whether the light source is currently active or inactive. The accepted values are 'on' or 'off'.")
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
    @describe("Turns toggles the light source on or off based on the specified value (\"on\" or \"off\"), enabling or disabling illumination. Argument: -obj: The desired state of the light source (on or off).")
    async def async_turns(self, newStatus: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {newStatus}")

    @eca_script_action(verb = "increases", variable = "intensity", modifier = "by")
    @describe("IncreasesIntensity increases the brightness of the light source by a specified non-negative amount. If the resulting intensity exceeds the maximum allowed value, it is capped at maxIntensity. Argument: -obj: The value to add to the current intensity.")
    async def async_increases(self, amount: float) -> None:
        _LOGGER.info(f"Performed increases action - {amount}")

    @eca_script_action(verb = "decreases", variable = "intensity", modifier = "by")
    @describe("DecreasesIntensity reduces the brightness of the light source by a specified non-negative amount. If the resulting intensity drops below zero, it is set to zero to avoid negative values. Argument: -obj: The value to subtract from the current intensity.")
    async def async_decreases(self, amount: float) -> None:
        _LOGGER.info(f"Performed decreases action - {amount}")

    @eca_script_action(verb = "sets", variable = "intensity", modifier = "to")
    async def async_sets(self, i: float) -> None:
        _LOGGER.info(f"Performed sets action - {i}")

    @eca_script_action(verb = "changes", variable = "color", modifier = "to")
    @describe("SetsColor updates the light's color to the specified value. The allowed values are predefined color names (e.g., \"red\", \"blue\", \"green\"). Argument: -obj: The desired color to apply to the light source.")
    async def async_changes(self, inputColor: ECAColor) -> None:
        _LOGGER.info(f"Performed changes action - {inputColor}")


@describe("ECAVideo is an ECAInteraction that represents a video player.")
class ECAVideo(ECAEntity):

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
    @describe("source (str): Source is the video source.")
    def source(self) -> str:
        return self._source

    @property
    @describe("volume (float): Volume is the video volume.")
    def volume(self) -> float:
        return self._volume

    @property
    @describe("maxVolume (float): MaxVolume is the video max volume.")
    def maxVolume(self) -> float:
        return self._maxVolume

    @property
    @describe("playing (ECABoolean): Playing defines whether the video is playing.")
    def playing(self) -> ECABoolean:
        return self._playing

    @property
    @describe("paused (ECABoolean): Paused defines whether the video is paused.")
    def paused(self) -> ECABoolean:
        return self._paused

    @property
    @describe("stopped (ECABoolean): Stopped defines whether the video is stopped.")
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
    @describe("Plays starts the video.")
    async def async_plays(self) -> None:
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb = "pauses")
    @describe("Pauses pauses the video.")
    async def async_pauses(self) -> None:
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "stops")
    @describe("Stops stops the video.")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "changes", variable = "volume", modifier = "to")
    @describe("ChangesVolume changes the video volume to the given value. If the value is greater than the max volume, the volume is set to the max volume. If the value is lower than 0, the volume is set to 0. Argument: -obj: The new video volume.")
    async def async_changes_volume(self, v: float) -> None:
        _LOGGER.info(f"Performed changes_volume action - {v}")

    @eca_script_action(verb = "changes", variable = "source", modifier = "to")
    @describe("ChangesSource changes the video source to the given value. The new path must be relative to the user-accessible Inventory folder. Argument: -obj: The path for the new video file.")
    async def async_changes_source(self, newSource: str) -> None:
        _LOGGER.info(f"Performed changes_source action - {newSource}")


@describe("Artwork represents an artwork in the environment. The Artwork class defines properties such as the author, price, and creation year of the artwork.")
class Artwork(ECAEntity):

    def __init__(self, author: str, price: float, year: int, type: str, description: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._author = author
        self._price = price
        self._year = year
        self._type = type
        self._description = description
        self._attr_should_poll = False

    @property
    @describe("author (str): author specifies the name of the artist of the artwork.")
    def author(self) -> str:
        return self._author

    @property
    @describe("price (float): price represents the monetary value of the artwork.")
    def price(self) -> float:
        return self._price

    @property
    @describe("year (int): year denotes the year in which the artwork was created.")
    def year(self) -> int:
        return self._year

    @property
    @describe("type (str): type denotes the type of the artwork (e.g., painting, sculpture).")
    def type(self) -> str:
        return self._type

    @property
    @describe("description (str): description denotes the description of the artwork (e.g., style, technique).")
    def description(self) -> str:
        return self._description

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "author": self.author,
            "price": self.price,
            "year": self.year,
            "type": self.type,
            "description": self.description,
            **super_extra_attributes
        }


@describe("")
class Building(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class Exterior(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class Furniture(ECAEntity):

    def __init__(self, price: float, color: dict, dimension: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._price = price
        self._color = color
        self._dimension = dimension
        self._attr_should_poll = False

    @property
    @describe("price (float): ")
    def price(self) -> float:
        return self._price

    @property
    @describe("color (dict): ")
    def color(self) -> dict:
        return self._color

    @property
    @describe("dimension (float): ")
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


@describe("")
class Terrain(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class Vegetation(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class Sky(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("The AquaticAnimal class represents an aquatic animal. An AquaticAnimal can swim to specific positions or follow predefined paths, with animations for both swimming and idling states. This class extends the functionality of !:Animal to include aquatic-specific behaviors.")
class AquaticAnimal(ECAEntity):

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
    @describe("Swims (to) is a method that moves the aquatic animal to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    @describe("Swims (to) is a method that moves the aquatic animal to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")


@describe("The Creature class represents a generic creature. A Creature can perform various movements such as running, walking, and swimming, each with a specific animation. This class extends the functionality of !:Animal to include creature-specific behaviors.")
class Creature(ECAEntity):

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
    @describe("Flies (to) is a method that moves the creature to a specific position with a flying animation. Argument: -obj: The target position to fly to.")
    async def async_flies_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed flies_to action - {p}")

    @eca_script_action(verb = "flies on")
    @describe("Flies (to) is a method that moves the creature to a specific position with a flying animation. Argument: -obj: The target position to fly to.")
    async def async_flies_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed flies_on action - {p}")

    @eca_script_action(verb = "runs to")
    @describe("Runs (to) is a method that moves the creature to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    @describe("Runs (to) is a method that moves the creature to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    @describe("Swims (to) is a method that moves the creature to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    @describe("Swims (to) is a method that moves the creature to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    @describe("Walks (to) is a method that moves the creature to a specific position with a walking animation. Argument: -obj: The target position to walk to.")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    @describe("Walks (to) is a method that moves the creature to a specific position with a walking animation. Argument: -obj: The target position to walk to.")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


@describe("ECAHuman is a component that represents a human character capable of performing physical actions within the environment. It can execute movements such as walking, running, and swimming, each associated with a specific animation sequence. This component extends ECAAnimal by adding human-specific behaviors and interaction capabilities.")
class ECAHuman(ECAEntity):

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
    @describe("Runs (to) is a method that moves the human to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    @describe("Runs (to) is a method that moves the human to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    @describe("Swims (to) is a method that moves the human to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    @describe("Swims (to) is a method that moves the human to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    @describe("Walks (to) is a method that moves the human to a specific position with a walking animation. Argument: -obj: The target position to move to.")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    @describe("Walks (to) is a method that moves the human to a specific position with a walking animation. Argument: -obj: The target position to move to.")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


@describe("The Robot class represents a robot character (non-animal counterpart of a human). A Robot can perform various movements such as running, walking, and swimming, each with a specific animation. This class extends the functionality of ECAAnimal to include robot-specific behaviors.")
class ECARobot(ECAEntity):

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
    @describe("Runs (to) is a method that moves the robot to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    @describe("Runs (to) is a method that moves the robot to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    @describe("Swims (to) is a method that moves the robot to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    @describe("Swims (to) is a method that moves the robot to a specific position with a swimming animation. Argument: -obj: The target position to swim to.")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    @describe("Walks (to) is a method that moves the robot to a specific position with a walking animation. Argument: -obj: The target position to move to.")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    @describe("Walks (to) is a method that moves the robot to a specific position with a walking animation. Argument: -obj: The target position to move to.")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


@describe("The FlyingAnimal class represents a flying animal. An FlyingAnimal can move using flying or walking animations and supports navigation to specific positions or along predefined paths. This class extends the functionality of !:Animal to include flying-specific behaviors.")
class FlyingAnimal(ECAEntity):

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
    @describe("Flies (to) is a method that moves the flying animal to a specific position with a flying animation. Argument: -obj: The target position to fly to.")
    async def async_flies_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed flies_to action - {p}")

    @eca_script_action(verb = "flies on")
    @describe("Flies (to) is a method that moves the flying animal to a specific position with a flying animation. Argument: -obj: The target position to fly to.")
    async def async_flies_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed flies_on action - {p}")

    @eca_script_action(verb = "walks to")
    @describe("Walks (to) is a method that moves the flying animal to a specific position with a walking animation. Argument: -obj: The target position to walk to.")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    @describe("Walks (to) is a method that moves the flying animal to a specific position with a walking animation. Argument: -obj: The target position to walk to.")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


@describe("The TerrestrialAnimal class represents a terrestrial animal. A TerrestrialAnimal can perform actions like running and walking, with corresponding animations for movement to specific positions or along paths. This class extends the functionality of !:Animal to include terrestrial-specific behaviors.")
class TerrestrialAnimal(ECAEntity):

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
    @describe("Runs (to) is a method that moves the terrestrial animal to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    @describe("Runs (to) is a method that moves the terrestrial animal to a specific position with a running animation. Argument: -obj: The target position to run to.")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "walks to")
    @describe("Walks (to) is a method that moves the terrestrial animal to a specific position with a walking animation. Argument: -obj: The target position to walk to.")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    @describe("Walks (to) is a method that moves the terrestrial animal to a specific position with a walking animation. Argument: -obj: The target position to walk to.")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


@describe("")
class ECAPlayer_Singleton(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class ECALiquidDrop(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("")
class ECALiquidSpawner(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("Collectable is a Behaviour that lets an object to be taken inside a player/object owned inventory, or instantly used for interacting with other objects in the scene An object is collected, then a lock on a door unlocks")
class Collectable(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes
        }


@describe("Container is a Behaviour that enables the object to hold other objects.")
class Container(ECAEntity):

    def __init__(self, capacity: int, objectsCount: int, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._capacity = capacity
        self._objectsCount = objectsCount
        self._attr_should_poll = False

    @property
    @describe("capacity (int): Capacity is the maximum number of objects that can be held by the container.")
    def capacity(self) -> int:
        return self._capacity

    @property
    @describe("objectsCount (int): objectsCount is the number of objects that are currently held by the container.")
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
    @describe("Inserts inserts an object into the container. Argument: -obj: The gameObject to be stored inside the container")
    async def async_inserts(self, o: object) -> None:
        _LOGGER.info(f"Performed inserts action - {o}")

    @eca_script_action(verb = "removes")
    @describe("Removes removes an object from the container. Argument: -obj: The gameObject to be removed from the container")
    async def async_removes(self, o: object) -> None:
        _LOGGER.info(f"Performed removes action - {o}")

    @eca_script_action(verb = "empties")
    @describe("Empties empties the container.")
    async def async_empties(self) -> None:
        _LOGGER.info(f"Performed empties action")


@describe("Counter is a Behaviour that enables the object to keep track of countable events Player steps, interaction count")
class Counter(ECAEntity):

    def __init__(self, count: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._count = count
        self._attr_should_poll = False

    @property
    @describe("count (float): count is the current count of the counter")
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
    @describe("Changes changes the count of the counter Argument: -obj: the amount to set")
    async def async_changes(self, amount: float) -> None:
        _LOGGER.info(f"Performed changes action - {amount}")


@describe("ECAOilStain is a component that attaches oil stains to a virtual object, ideally a surface equipped with an ECASurface component. It can be 'washed' using other objects such as mops or cleaning rags. Once fully washed, the object updates its state.")
class ECAOilStain(ECAEntity):

    def __init__(self, allWashed: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._allWashed = allWashed
        self._attr_should_poll = False

    @property
    @describe("allWashed (ECABoolean): allWashed indicates whether all the stains have been successfully removed from the object.")
    def allWashed(self) -> ECABoolean:
        return self._allWashed

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "allWashed": self.allWashed,
            **super_extra_attributes
        }

    @eca_script_action(verb = "removes-stain-with-rag", is_passive = True)
    @describe("removes-stain-with-rag defines the sweeping action performed by an object that has an ECACleaningRag component. When the action is executed, the stains are removed. Typically, this is the result of a washes event performed by an object that has an ECACleaningRag. Argument: -subject: The object that has a ECACleaningRag component responsible for performing the washing action.")
    async def async_removes_stain_with_rag(self, cleaningRag: ECACleaningRag) -> None:
        _LOGGER.info(f"Performed removes_stain_with_rag action - {cleaningRag}")

    @eca_script_action(verb = "removes-stain-with-mop", is_passive = True)
    @describe("removes-stain-with-rag defines the sweeping action performed by an object that has an ECACleaningRag component. When the action is executed, the stains are removed. Typically, this is the result of a washes event performed by an object that has an ECACleaningRag. Argument: -subject: The object that has a ECACleaningRag component responsible for performing the washing action.")
    async def async_removes_stain_with_mop(self, mop: ECAMop) -> None:
        _LOGGER.info(f"Performed removes_stain_with_mop action - {mop}")


@describe("ECAPhysicalGrabbable is a component that represents a physical object in the scene which can be grabbed by a player, or user, object equipped with an ECACharacter component, using one or both hands. It tracks the grabbing state, manages interaction logic based on trigger collisions with hand colliders, and communicates grab-related events through the automation system.")
class ECAPhysicalGrabbable(ECAEntity):

    def __init__(self, grabbed: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._grabbed = grabbed
        self._attr_should_poll = False

    @property
    @describe("grabbed (ECABoolean): grabbed indicates whether the object is currently being held by a player or user object equipped with an ECACharacter component. This state is updated based on trigger collisions with hand colliders and is used to control interactive behaviors.")
    def grabbed(self) -> ECABoolean:
        return self._grabbed

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "grabbed": self.grabbed,
            **super_extra_attributes
        }

    @eca_script_action(verb = "starts-grabbing", is_passive = True)
    @describe("starts-grabbing is triggered when a player or user object equipped with an ECACharacter component begins to grab this object with either hand. When triggered, it sets the grabbed state to true and notifies the automation system of the grab event. Argument: -subject: The object equipped with an ECACharacter component that initiates the grab action.")
    async def async_starts_grabbing(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed starts_grabbing action - {c}")

    @eca_script_action(verb = "stops-grabbing", is_passive = True)
    @describe("stops-grabbing is triggered when a player or user object equipped with an ECACharacter component releases this object with both hands. When triggered, it sets the grabbed state to false and notifies the automation system that the grab interaction has ended. Argument: -subject: The object equipped with an ECACharacter component that releases the object.")
    async def async_stops_grabbing(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed stops_grabbing action - {c}")


@describe("Highlight is a component that is used to highlight the objects that are in the scene.")
class ECAHighlight(ECAEntity):

    def __init__(self, color: dict, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._color = color
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("color (dict): Color is the color that will be used to highlight the objects.")
    def color(self) -> dict:
        return self._color

    @property
    @describe("on (ECABoolean): On is a boolean that tells if the highlight is on or off.")
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
    @describe("ChangesColor changes the color of the outline. Argument: -obj: ")
    async def async_changes(self, c: dict) -> None:
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb = "turns")
    @describe("TurnsOn turns the highlight on or off. Argument: -obj: ")
    async def async_turns(self, on: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {on}")


@describe("Sound is a behavior component that acts as a media player specifically designed for audio playback. It provides functionalities such as playing, pausing, and stopping audio, as well as controlling volume and managing audio sources.")
class ECASound(ECAEntity):

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
    @describe("source (str): Source is the audio filename that serves as the source for playback.")
    def source(self) -> str:
        return self._source

    @property
    @describe("volume (float): Volume is the current volume level of the audio. Accepts values between 0 and the maximum volume, defined by .")
    def volume(self) -> float:
        return self._volume

    @property
    @describe("maxVolume (float): MaxVolume is the maximum volume level the audio can reach.")
    def maxVolume(self) -> float:
        return self._maxVolume

    @property
    @describe("currentTime (float): currentTime is the current playback position in seconds. Tracks the progression of the audio clip.")
    def currentTime(self) -> float:
        return self._currentTime

    @property
    @describe("playing (ECABoolean): playing indicates whether the audio is currently playing. The value is either 'yes' or 'no'. If paused or stopped are 'yes', playing will be 'no'.")
    def playing(self) -> ECABoolean:
        return self._playing

    @property
    @describe("paused (ECABoolean): paused indicates whether the audio playback is paused. The value is either 'yes' or 'no'. When playing again, the audio will resume from the paused time.")
    def paused(self) -> ECABoolean:
        return self._paused

    @property
    @describe("stopped (ECABoolean): Stopped  indicates whether the audio playback is stopped. The value is either 'yes' or 'no'. When playing again, the audio will start from the beginning.")
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
    @describe("Plays starts the audio playback. Updates the state variables playing, stopped, and paused to reflect that playback is active.")
    async def async_plays(self) -> None:
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb = "pauses")
    @describe("Pauses pauses the audio playback. Maintains the current playback time (currentTime) for resuming later (by calling Plays).")
    async def async_pauses(self) -> None:
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "stops")
    @describe("Stops stops the audio playback and resets the playback time (currentTime) to the beginning.")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "changes", variable = "volume", modifier = "to")
    @describe("ChangesVolume changes the volume of the audio to a given value. Ensures the value remains within the range of 0 to Argument: -obj: The new volume value.")
    async def async_changes_volume(self, v: float) -> None:
        _LOGGER.info(f"Performed changes_volume action - {v}")

    @eca_script_action(verb = "changes", variable = "source", modifier = "to")
    @describe("ChangesSource changes the audio filename source to the given filename. Validates the path and dynamically loads the audio for playback. Argument: -obj: The new audio filename.")
    async def async_changes_source(self, newSource: str) -> None:
        _LOGGER.info(f"Performed changes_source action - {newSource}")


@describe("Highlight is a Behaviour that is used to highlight the objects that are in the scene.")
class Highlight(ECAEntity):

    def __init__(self, color: dict, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._color = color
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("color (dict): Color is the color that will be used to highlight the objects.")
    def color(self) -> dict:
        return self._color

    @property
    @describe("on (ECABoolean): On is a boolean that tells if the highlight is on or off.")
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
    @describe("ChangesColor changes the color of the outline. Argument: -obj: ")
    async def async_changes(self, c: dict) -> None:
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb = "turns")
    @describe("TurnsOn turns the highlight on or off. Argument: -obj: ")
    async def async_turns(self, on: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {on}")


@describe("Keypad is a Behaviour that lets an object to receive codes and trigger actions when the code is correct.")
class Keypad(ECAEntity):

    def __init__(self, keycode: str, input: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._keycode = keycode
        self._input = input
        self._attr_should_poll = False

    @property
    @describe("keycode (str): Keycode is the code that the keypad will accept.")
    def keycode(self) -> str:
        return self._keycode

    @property
    @describe("input (str): Input is the input that the keypad is currently holding.")
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
    @describe("Inserts inserts the whole input into the input variable. Argument: -obj: The complete code to be checked")
    async def async_inserts(self, input: str) -> None:
        _LOGGER.info(f"Performed inserts action - {input}")

    @eca_script_action(verb = "adds")
    @describe("Adds adds a single character to the input variable. Argument: -obj: ")
    async def async_adds(self, input: str) -> None:
        _LOGGER.info(f"Performed adds action - {input}")

    @eca_script_action(verb = "resets")
    @describe("Resets clears the input variable.")
    async def async_resets(self) -> None:
        _LOGGER.info(f"Performed resets action")


@describe("Lock is a Behaviour that locks the ECAObject it is attached to. It works in a similar way to the Keypad behaviour, but it needs to by unlock by other means (like a key).")
class Lock(ECAEntity):

    def __init__(self, locked: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._locked = locked
        self._attr_should_poll = False

    @property
    @describe("locked (ECABoolean): locked defines whether the lock is open or not.")
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
    @describe("Opens sets the lock to open.")
    async def async_opens(self) -> None:
        _LOGGER.info(f"Performed opens action")

    @eca_script_action(verb = "closes")
    @describe("Closes sets the lock to closed.")
    async def async_closes(self) -> None:
        _LOGGER.info(f"Performed closes action")


@describe("Particle is a Behaviour that lets the object emit particles.")
class Particle(ECAEntity):

    def __init__(self, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("on (ECABoolean): On is a boolean that indicates if the particle system is active.")
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
    @describe("Turns is used to turn on/off the particle system. Argument: -obj: The status of the particle system.")
    async def async_turns(self, on: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {on}")


@describe("Placeholder is a Behaviour that is used to represent a placeholder in the scene. It will be used by the End User Developers in order to import and use custom mesh models.")
class Placeholder(ECAEntity):

    def __init__(self, mesh: dict, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._mesh = mesh
        self._attr_should_poll = False

    @property
    @describe("mesh (dict): newMesh is the mesh model that the object will use.")
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
    @describe("Changes sets the new mesh model that the object will use. Argument: -obj: The path of the mesh in the user-accessible mesh folder")
    async def async_changes(self, meshName: str) -> None:
        _LOGGER.info(f"Performed changes action - {meshName}")


@describe("Switch is a Behaviour that can be use to let an object have an on/off state, useful for objects like lights, doors, etc.")
class Switch(ECAEntity):

    def __init__(self, on: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._on = on
        self._attr_should_poll = False

    @property
    @describe("on (ECABoolean): On is the state of the switch.")
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
    @describe("Turns defines if the switch is on or off. Argument: -obj: The new state of the switch.")
    async def async_turns(self, on: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {on}")

    @eca_script_action(verb = "toggle status")
    @describe("Toggle status toggles the switch state.")
    async def async_toggle_status(self) -> None:
        _LOGGER.info(f"Performed toggle_status action")


@describe("Represents a time-based Behaviour that helps triggering actions after specified durations. The Timer class provides functionality to configure, start, pause, stop, and reset a timer, as well as to emit events when specific time milestones are reached or elapsed.")
class Timer(ECAEntity):

    def __init__(self, duration: float, current_time: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._duration = duration
        self._current_time = current_time
        self._attr_should_poll = False

    @property
    @describe("duration (float): Duration specifies the total duration for which the timer will run.")
    def duration(self) -> float:
        return self._duration

    @property
    @describe("current_time (float): Current represents the current time of the timer, meaning the elapsed time from the start. It dynamically updates as the timer counts down.")
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
    @describe("ChangesDuration sets the total duration of the timer with a non-negative value. Argument: -obj: The new duration value for the timer.")
    async def async_changes_duration(self, amount: float) -> None:
        _LOGGER.info(f"Performed changes_duration action - {amount}")

    @eca_script_action(verb = "changes", variable = "current-time", modifier = "to")
    @describe("ChangeCurrentTime sets the elapsed time of the timer. It ensures that the new value is within the valid range [0, duration]. Argument: -obj: The new")
    async def async_changes_current_time(self, amount: float) -> None:
        _LOGGER.info(f"Performed changes_current_time action - {amount}")

    @eca_script_action(verb = "starts")
    @describe("Starts activates the timer to begin counting down, resuming its operation from the last paused state.")
    async def async_starts(self) -> None:
        _LOGGER.info(f"Performed starts action")

    @eca_script_action(verb = "stops")
    @describe("Stops deactivates the timer, resetting the elapsed time to zero.")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "pauses")
    @describe("Pauses deactivates the timer, leaving the elapsed time unchanged.")
    async def async_pauses(self) -> None:
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "reaches")
    @describe("Reaches emits an event when the timer reaches a specified elapsed time. It can be used to trigger actions at predefined points in the elapsed timeline. Argument: -obj: The elapsed time at which the event is triggered.")
    async def async_reaches(self, seconds: int) -> None:
        _LOGGER.info(f"Performed reaches action - {seconds}")

    @eca_script_action(verb = "resets")
    @describe("Resets resets the timer to its maximum duration and deactivates it.")
    async def async_resets(self) -> None:
        _LOGGER.info(f"Performed resets action")


@describe("Transition is a Behaviour that is used to trigger a transition to another scene.")
class Transition(ECAEntity):

    def __init__(self, reference: Scene, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._reference = reference
        self._attr_should_poll = False

    @property
    @describe("reference (Scene): Reference is the Unity Scene to transition to.")
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
    @describe("Teleports changes the current scene to the scene referenced by reference. Argument: -obj: ")
    async def async_teleports_to(self, reference: Scene) -> None:
        _LOGGER.info(f"Performed teleports_to action - {reference}")


@describe("Trigger is a Behaviour that can be used to trigger an action without an explicit request from the player. If the action is player initiated, then refer to !:Interactable")
class Trigger(ECAEntity):

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
    @describe("Triggers emits an event when the trigger is activated. Argument: -obj: The event to trigger in the scene.")
    async def async_triggers(self, action: dict) -> None:
        _LOGGER.info(f"Performed triggers action - {action}")

#endregion ECA Sensors

#region Taxonomy classes mr test
class ECAXRGrabbable(ECAEntity):
    """
    <b>ECAXRGrabbable</b> is a custom ECA component that makes an object grabbable in XR.
    It ensures ensures that grab and release events are mapped into the ECA system.
    This class exposes the state variable <b>grabbed</b> and the actions
    <b>starts-grabbing</b> and <b>stops-grabbing</b>, which allow automations
    to reason about when a character interacts physically with this object.

    Attributes:
    - grabbed (ECABoolean): it indicates whether the object is currently being held by the player character.

    """

    def __init__(self, grabbed: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._grabbed = grabbed
        self._attr_should_poll = False

    @property
    def grabbed(self) -> ECABoolean:
        return self._grabbed

    @grabbed.setter
    @decorator_update_deque(DEQUE_INTERACTED_OBJECTS)
    def grabbed(self, v: ECABoolean) -> None:
        self._grabbed = v

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "grabbed": self.grabbed,
            **super_extra_attributes,
        }

    @eca_script_action(verb="starts-grabbing", is_passive = True)
    async def async_starts_grabbing(self, c: ECACharacter) -> None:
        """
        <b>StartsGrabbing</b> is an action that occurs when the player character begins holding this object.
        Argument:
            -c: The "ECACharacter" that performs the grabbing action.
        """
        _LOGGER.info(f"Performed changes_source action - {c}")

    @eca_script_action(verb="stops-grabbing", is_passive = True)
    async def async_stops_grabbing(self, c: ECACharacter) -> None:
        """
        <b>StopsGrabbing</b> is an action that occurs when the player character releases this object.
        Argument:
            -c: The "ECACharacter" that performs the releasing action.
        """
        _LOGGER.info(f"Performed changes_source action - {c}")


@describe("ECASprayBottle is a component that represents a virtual spray bottle capable of detecting pinch gestures to trigger a spray action. The action is activated when both the index and middle fingers pinch beyond a configurable threshold, causing the bottle to emit a spray and potentially trigger related ECA automation events.")
class ECASprayBottle(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            **super_extra_attributes,
        }

    @describe("sprays represents the action of dispensing liquid from an object equipped with an ECASprayBottle component, typically triggered by a character performing a pinch gesture with the hand. When executed, it releases a burst of liquid, plays an associated audio cue, and may trigger automation events related to cleaning, wetting, or environmental interactions. -Argument: 'subject' The object equipped with an ECACharacter component performing the spray action.</param>")
    @eca_script_action(verb="sprays", is_passive = True)
    async def async_sprays(self, c: ECACharacter) -> None:
        _LOGGER.info(f"Performed changes_source action - {c}")


class ECAXRPointer(ECAEntity):
    """
    <b>ECAXRPointer</b> is a custom ECA component that makes the object owner pointable by the user represents an XR ray pointer interaction.

    Attributes:
    - isPointed: <b>isPointed</b> indicates whether this object is currently being pointed at by the player character's XR ray pointer.
    """

    def __init__(self, isPointed: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._isPointed = isPointed
        self._attr_should_poll = False

    @property
    def isPointed(self) -> ECABoolean:
        return self._isPointed

    @isPointed.setter
    @decorator_update_deque(DEQUE_POINTED_OBJECTS)
    def isPointed(self, v: ECABoolean) -> None:
        self._isPointed = v

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "isPointed": self.isPointed
            **super_extra_attributes,
        }

    @eca_script_action(verb="sprays")
    async def async_sprays(self, c: ECACharacter) -> None:
        """
        <b>sprays</b> is an action that dispenses liquid from the spray bottle when triggered by a character,
        typically through a hand pinch gesture. It also plays an audio cue when the spray starts.
        Argument:
            -c: The "ECACharacter" performing the spray action.
        """
        _LOGGER.info(f"Performed changes_source action - {c}")
#endregion


########## DO NOT DELETE IT
CURRENT_MODULE = sys.modules[__name__]
