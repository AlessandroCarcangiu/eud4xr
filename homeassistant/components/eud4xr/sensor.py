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
from .utils import MappedClasses, eca_script_action, decorator_update_deque

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


class ECAObject(ECAEntity):
    """
    ECAObject is the base class for all virtual objects that can be used in the automations.
            All the other classes in this package inherit from this class or one of its subclasses.
            It supports properties such as position, rotation, scale, visibility, and activity, and provides methods for moving, rotating, scaling, and controlling visibility.

    Attributes:
    - description (str): description describes in a few words what the object is and its role.
    - position (ECAPosition): p represents the position of the virtual object in the 3D space. It's a vector with three components: x, y, and z.
    - rotation (ECARotation): r represents the rotation of the object in the 3D space. It's a vector with three components: x, y, and z (euler angles).
    - scale (ECAScale): r represents the scale of the object in the 3D space.
    - visible (ECABoolean): visible indicates whether the object is visible. The allowed values are either "yes" or "no".
            If invisible, the object is not rendered but remains interactive for collisions.
    - active (ECABoolean): active indicates whether the object is active. The allowed values are either "yes" or "no".
            When inactive, the object is not rendered and does not interact with other objects.
    - isInsideCamera (ECABoolean): isInsideCamera indicates whether the object is currently within the camera's field of view. This property is automatically updated at runtime.

    """

    def __init__(
        self,
        description: str,
        position: ECAPosition,
        rotation: ECARotation,
        scale: ECAScale,
        visible: ECABoolean,
        active: ECABoolean,
        isInsideCamera: ECABoolean,
        **kwargs: dict,
    ) -> None:
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
    def description(self) -> str:
        return self._description

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
            **super_extra_attributes,
        }

    @eca_script_action(verb="moves to")
    async def async_moves_to(self, newPos: ECAPosition) -> None:
        """
        Moves (to) is a method that moves the object to a specified position in the 3D space.
        Argument:
            -newPos:The target position to move to.
        """
        _LOGGER.info(f"Performed moves_to action - {newPos}")

    @eca_script_action(verb="moves on")
    async def async_moves_on(self, path: list[ECAPosition]) -> None:
        """
        Moves (to) is a method that moves the object to a specified position in the 3D space.
        Argument:
            -newPos:The target position to move to.
        """
        _LOGGER.info(f"Performed moves_on action - {path}")

    @eca_script_action(verb="rotates around")
    async def async_rotates_around(self, newRot: ECARotation) -> None:
        """
        Rotates sets the object's rotation to a specified value in the 3D space.
        Argument:
            -newRot:The target rotation expressed as a vector with three components: x, y, and z.
        """
        _LOGGER.info(f"Performed rotates_around action - {newRot}")

    @eca_script_action(verb="looks at")
    async def async_looks_at(self, o: object) -> None:
        """
        Looks adjusts the object's rotation to face a specified target object.
        Argument:
            -o:The target GameObject to look at.
        """
        _LOGGER.info(f"Performed looks_at action - {o}")

    @eca_script_action(verb="scales to")
    async def async_scales_to(self, newScale: ECAScale) -> None:
        """
        Scales sets the object's scale to a specified value.
        Argument:
            -newScale:The new scale value fo the object. The scale is a vector with three components: x, y, and z.
        """
        _LOGGER.info(f"Performed scales_to action - {newScale}")

    @eca_script_action(verb="restores original settings")
    async def async_restores_original_settings(self) -> None:
        """
        Restores the object's original position, rotation, and scale to their initial values.
        """
        _LOGGER.info(f"Performed restores_original_settings action")

    @eca_script_action(verb="shows")
    async def async_shows(self) -> None:
        """
        Shows maakes the object visible if it is not already.
        """
        _LOGGER.info(f"Performed shows action")

    @eca_script_action(verb="hides")
    async def async_hides(self) -> None:
        """
        Hides makes the object invisible if it is not already.
        """
        _LOGGER.info(f"Performed hides action")

    @eca_script_action(verb="activates")
    async def async_activates(self) -> None:
        """
        Activates makes the object both interactable and visible.
        """
        _LOGGER.info(f"Performed activates action")

    @eca_script_action(verb="deactivates")
    async def async_deactivates(self) -> None:
        """
        Deactivates makes the object invisible and non-interactable.
        """
        _LOGGER.info(f"Performed deactivates action")

    @eca_script_action(verb="changes", variable="visible", modifier="to")
    async def async_changes_visible(self, yesNo: ECABoolean) -> None:
        """
        ShowsHides changes the visibility state of the object based on a parameter. The parameter can be either "yes" or "no".
        Argument:
            -yesNo:The new visibility state.
        """
        _LOGGER.info(f"Performed changes_visible action - {yesNo}")

    @eca_script_action(verb="changes", variable="active", modifier="to")
    async def async_changes_active(self, yesNo: ECABoolean) -> None:
        """
        ActivatesDeactivates changes the active state of the object based on a parameter. The parameter can be either "yes" or "no".
        Argument:
            -yesNo:The new active state.
        """
        _LOGGER.info(f"Performed changes_active action - {yesNo}")


class ECABehaviour(ECAEntity):
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
        return {**super_extra_attributes}


class LiquidDrop(ECAEntity):
    """


    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}


class LiquidSpawner(ECAEntity):
    """


    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}


class ECASystem(ECAEntity):
    """
    ECASystem represents the virtual system within the automation system.
            It notifies when the virtual system starts, allowing the execution of rules at the start of the application.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="starts-up")
    async def async_starts_up(self) -> None:
        """
        StartsUpTest is a method that triggers the startup process of the system.
            It can be used as trigger for automations.
        """
        _LOGGER.info(f"Performed starts_up action")


class ECAProp(ECAEntity):
    """
    In Prop category we represent generic objects that can be placed in a scene and manipulated by characters.
            The possible sub-categories are, in this case, several; we can have passive actions.

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
        return {"price": self.price, **super_extra_attributes}


class ECAInteractable(ECAEntity):
    """
    Interactable is a Behaviour that can be attached to an object in order to make it
            interactable with the player collison.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}


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
        return {**super_extra_attributes}

    @eca_script_action(verb="opens")
    async def async_opens(self) -> None:
        _LOGGER.info(f"Performed opens action")

    @eca_script_action(verb="closes")
    async def async_closes(self) -> None:
        _LOGGER.info(f"Performed closes action")


class ECALiquidDispenser(ECAEntity):
    """
    ECALiquidDispenser is a virtual dispenser capable of filling containers with specific types of liquid.
            Supports defining the type of liquid it dispenses (e.g., water, degreaser, amuchina, battery killer).

    Attributes:
    - liquidType (str): liquidType specifies the type of liquid dispensed by this object.
            Possible values include "water", "degreaser", "amuchina", and "battery killer".

    """

    def __init__(self, liquidType: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._liquidType = liquidType
        self._attr_should_poll = False

    @property
    def liquidType(self) -> str:
        return self._liquidType

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {"liquidType": self.liquidType, **super_extra_attributes}


class ECABottle(ECAEntity):
    """
    ECABottle is a virtual bottle object that can contain and dispense liquid.
            It supports state variables such as capOpen and flipped, and interacts with a  component for liquid spawning.
            It provides actions for flipping the bottle, opening or closing its cap, and starting or stopping the flow of liquid.
            Some rules are added automatically at the start:
            - Flipping the bottle down while the cap is open will cause liquid to drop.
            - Flipping the bottle up will stop the liquid from dropping.
            - Closing the cap will stop the liquid from dropping.
            - Opening the cap while the bottle is flipped down will cause liquid to drop.

    Attributes:
    - capOpen (ECABoolean): capOpen indicates whether the cap of the bottle is open (YES) or closed (NO).
    - flipped (ECABoolean): flipped indicates whether the bottle is currently flipped upside down (YES) or upright (NO).

    """

    def __init__(
        self, capOpen: ECABoolean, flipped: ECABoolean, **kwargs: dict
    ) -> None:
        super().__init__(**kwargs)
        self._capOpen = capOpen
        self._flipped = flipped
        self._attr_should_poll = False

    @property
    def capOpen(self) -> ECABoolean:
        return self._capOpen

    @property
    def flipped(self) -> ECABoolean:
        return self._flipped

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "capOpen": self.capOpen,
            "flipped": self.flipped,
            **super_extra_attributes,
        }

    @eca_script_action(verb="opens-cap")
    async def async_opens_cap(self) -> None:
        """
        opens-cap is an action that opens the bottle’s cap.
        """
        _LOGGER.info(f"Performed opens_cap action")

    @eca_script_action(verb="closes-cap")
    async def async_closes_cap(self) -> None:
        """
        closes-cap is an action that closes the bottle’s cap.
        """
        _LOGGER.info(f"Performed closes_cap action")

    @eca_script_action(verb="flips-down")
    async def async_flips_down(self) -> None:
        """
        flips-down is an action that simulates turning the bottle upside down.
        """
        _LOGGER.info(f"Performed flips_down action")

    @eca_script_action(verb="flips-up")
    async def async_flips_up(self) -> None:
        """
        flips-up is an action that simulates turning the bottle upright.
        """
        _LOGGER.info(f"Performed flips_up action")

    @eca_script_action(verb="drops-liquid")
    async def async_drops_liquid(self) -> None:
        """
        drops-liquid is an internal action that triggers the liquid to start spawning from the spawner.
        """
        _LOGGER.info(f"Performed drops_liquid action")

    @eca_script_action(verb="stops-dropping")
    async def async_stops_dropping(self) -> None:
        """
        stops-dropping is an internal action that stops the flow of liquid from the bottle.
        """
        _LOGGER.info(f"Performed stops_dropping action")


class ECACharacter(ECAEntity):
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
        return {"life": self.life, "playing": self.playing, **super_extra_attributes}

    @eca_script_action(verb="interacts with")
    async def async_interacts_with(self, o: ECAInteractable) -> None:
        """
        Interacts enables the character to interact with a specified interactable object.
            The implementation details are managed by the  class logic.
        Argument:
            -o:The target interactable object
        """
        _LOGGER.info(f"Performed interacts_with action - {o}")

    @eca_script_action(verb="stops-interacting with")
    async def async_stops_interacting_with(self, o: ECAInteractable) -> None:
        """
        Stops interaction allows the character to stop its interaction with a specified interactable object.
            The implementation details are managed by the  class logic.
        Argument:
            -o:The target interactable object
        """
        _LOGGER.info(f"Performed stops_interacting_with action - {o}")

    @eca_script_action(verb="points to")
    async def async_points_to(self, o: ECAObject) -> None:
        """
        Points the character to point at a specified object, emphasizing its focus or attention on the target.
        Argument:
            -o:The target object to point at.
        """
        _LOGGER.info(f"Performed points_to action - {o}")

    @eca_script_action(verb="stops-pointing to")
    async def async_stops_pointing_to(self, o: ECAObject) -> None:
        """
        StopsPointing commands the character to stop pointing at a specified object, ceasing its focus or attention on the target.
        Argument:
            -o:The target object to stop pointing at.
        """
        _LOGGER.info(f"Performed stops_pointing_to action - {o}")

    @eca_script_action(verb="jumps to")
    async def async_jumps_to(self, p: ECAPosition) -> None:
        """
        Jumps commands the character to jump to a specific position in the 3D world.
        Argument:
            -p:The destination position where the character will jump.
        """
        _LOGGER.info(f"Performed jumps_to action - {p}")

    @eca_script_action(verb="jumps on")
    async def async_jumps_on(self, p: list[ECAPosition]) -> None:
        """
        Jumps commands the character to jump to a specific position in the 3D world.
        Argument:
            -p:The destination position where the character will jump.
        """
        _LOGGER.info(f"Performed jumps_on action - {p}")

    @eca_script_action(verb="starts-animation")
    async def async_starts_animation(self, s: str) -> None:
        """
        StartsAnimation triggers a predefined animation for the character, using the provided animation identifier.
        Argument:
            -s:The string of the animation clip to play
        """
        _LOGGER.info(f"Performed starts_animation action - {s}")


class ECAWaterMixerTap(ECAEntity):
    """
    ECAWaterMixerTap is a virtual object representing a water mixer tap that can be turned left, idle (middle), or right.
            Some rules are added automatically at the start:
            - Turning left flows warm water.
            - Turning right flows cold water
            - Turning idle (middle) stops the flow.
            The class includes properties and methods for controlling and responding to user interactions.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="flows-warm-water")
    async def async_flows_warm_water(self) -> None:
        """
        FlowsWarmWater causes the tap to emit warm water.
        """
        _LOGGER.info(f"Performed flows_warm_water action")

    @eca_script_action(verb="flows-cold-water")
    async def async_flows_cold_water(self) -> None:
        """
        FlowsColdWater causes the tap to emit cold water.
        """
        _LOGGER.info(f"Performed flows_cold_water action")

    @eca_script_action(verb="stops-flowing-water")
    async def async_stops_flowing_water(self) -> None:
        """
        StopFlowingWater stops any water from flowing.
        """
        _LOGGER.info(f"Performed stops_flowing_water action")

    @eca_script_action(verb="turns-left")
    async def async_turns_left(self, c: ECACharacter) -> None:
        """
        TurnsLeft is an action where a character turns the tap handle to the left.
        Argument:
            -c:The character performing the action.
        """
        _LOGGER.info(f"Performed turns_left action - {c}")

    @eca_script_action(verb="turns-idle")
    async def async_turns_idle(self, c: ECACharacter) -> None:
        """
        TurnsIdle is an action where a character returns the tap handle to the center (idle) position.
        Argument:
            -c:The character performing the action.
        """
        _LOGGER.info(f"Performed turns_idle action - {c}")

    @eca_script_action(verb="turns-right")
    async def async_turns_right(self, c: ECACharacter) -> None:
        """
        TurnsRight is an action where a character turns the tap handle to the right.
        Argument:
            -c:The character performing the action.
        """
        _LOGGER.info(f"Performed turns_right action - {c}")


class ECALiquidContainer(ECAEntity):
    """
    ECALiquidContainer represents a virtual container that can hold various virtual liquids and tracks their fill levels.
            It manages the fill steps between start and end positions, tracks different types of liquid drops,
            updates the visual liquid level, and handles temperature changes as liquids are added.

    Attributes:
    - waterDrops (int): waterDrops counts how many water drops have been added to the container.
    - degreaserDrops (int): degreaserDrops counts how many degreaser drops have been added to the container.
    - batteryKillerDrops (int): batteryKillerDrops counts how many battery killer drops have been added to the container.
    - amuchinaDrops (int): amuchinaDrops counts how many amuchina drops have been added to the container.
    - temperature (float): temperature represents the current temperature of the liquid mixture inside the container.
            It is updated dynamically as new liquid drops with different temperatures are added.

    """

    def __init__(
        self,
        waterDrops: int,
        degreaserDrops: int,
        batteryKillerDrops: int,
        amuchinaDrops: int,
        temperature: float,
        **kwargs: dict,
    ) -> None:
        super().__init__(**kwargs)
        self._waterDrops = waterDrops
        self._degreaserDrops = degreaserDrops
        self._batteryKillerDrops = batteryKillerDrops
        self._amuchinaDrops = amuchinaDrops
        self._temperature = temperature
        self._attr_should_poll = False

    @property
    def waterDrops(self) -> int:
        return self._waterDrops

    @property
    def degreaserDrops(self) -> int:
        return self._degreaserDrops

    @property
    def batteryKillerDrops(self) -> int:
        return self._batteryKillerDrops

    @property
    def amuchinaDrops(self) -> int:
        return self._amuchinaDrops

    @property
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
            **super_extra_attributes,
        }

    @eca_script_action(verb="fills-in")
    async def async_fills_in(self, dispenser: ECALiquidDispenser) -> None:
        """
        _FillsIn is an action method invoked when the container is filled by a liquid dispenser.
        Argument:
            -dispenser:The liquid dispenser that fills the container.
        """
        _LOGGER.info(f"Performed fills_in action - {dispenser}")


class ECABucket(ECAEntity):
    """
    ECABucket represents a virtual bucket that can contain different types of virtual liquids in the automation system.
            It extends the functionality of  by specializing the container as a bucket.
            This class can be filled with water, degreaser, amuchina, or battery killer, and it supports visual feedback such as fill level and liquid type.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}


class ECACleaningItem(ECAEntity):
    """
    ECACleaningItem represents a generic cleaning item within the automation framework.
            It serves as a base component for all cleaning tools and supports integration with ECA objects.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}


class ECAEnvironment(ECAEntity):
    """
    ECAEnvironment represents a generic class for environment items.
            On contrary with props (), environment items are not interactable by characters.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}


class ECASurface(ECAEntity):
    """
    ECASurface represents a physical or virtual surface within the automation environment.
            It is used to define surfaces such as tables, floors, walls, or ceilings that cleaning items can interact with.

    Attributes:
    - type (str): type specifies the kind of surface.
            Possible values include "table", "floor", "wall", or "ceiling".

    """

    def __init__(self, type: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._type = type
        self._attr_should_poll = False

    @property
    def type(self) -> str:
        return self._type

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {"type": self.type, **super_extra_attributes}


class ECABroom(ECAEntity):
    """
    ECABroom is a virtual cleaning tool used to simulate sweeping actions within an interactive environment.
            When it comes into contact with a surface, it triggers the sweeping action, which is then propagated through the automation system.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="sweeps")
    async def async_sweeps(self, surface: ECASurface) -> None:
        """
        Sweeps is a method that simulates the broom sweeping a surface.
            It is typically invoked upon collision with an , either manually or automatically.
        Argument:
            -surface:The surface to be swept by the broom.
        """
        _LOGGER.info(f"Performed sweeps action - {surface}")


class ECASoakableCleaningItem(ECAEntity):
    """
    ECASoakableCleaningItem is a virtual object that represents a reusable cleaning item
            capable of absorbing and releasing different types of liquids (e.g., water, degreaser, battery killer, disinfectant).
            It supports being wetted and dried, and tracks its current state using dedicated ECA boolean variables.

    Attributes:
    - hasWater (ECABoolean): hasWater indicates whether the item currently contains water.
    - hasDegreaser (ECABoolean): hasDegreaser indicates whether the item currently contains degreaser.
    - hasBatteryKiller (ECABoolean): hasBatteryKiller indicates whether the item currently contains battery killer solution.
    - hasAmuchina (ECABoolean): hasAmuchina indicates whether the item currently contains Amuchina (a disinfectant).

    """

    def __init__(
        self,
        hasWater: ECABoolean,
        hasDegreaser: ECABoolean,
        hasBatteryKiller: ECABoolean,
        hasAmuchina: ECABoolean,
        **kwargs: dict,
    ) -> None:
        super().__init__(**kwargs)
        self._hasWater = hasWater
        self._hasDegreaser = hasDegreaser
        self._hasBatteryKiller = hasBatteryKiller
        self._hasAmuchina = hasAmuchina
        self._attr_should_poll = False

    @property
    def hasWater(self) -> ECABoolean:
        return self._hasWater

    @property
    def hasDegreaser(self) -> ECABoolean:
        return self._hasDegreaser

    @property
    def hasBatteryKiller(self) -> ECABoolean:
        return self._hasBatteryKiller

    @property
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
            **super_extra_attributes,
        }

    @eca_script_action(verb="wets")
    async def async_wets(self, ld: ECALiquidDispenser) -> None:
        """
        Wets is an action method that updates the item’s internal state to reflect it has absorbed a specific liquid.
            It changes the item's material to a "wet" visual and starts a timer for automatic drying.
        Argument:
            -ld:The liquid dispenser responsible for wetting this item.
        """
        _LOGGER.info(f"Performed wets action - {ld}")

    @eca_script_action(verb="dries")
    async def async_dries(self) -> None:
        """
        Dries is an action method that resets the item to a dry state,
            both visually and logically by clearing the water state variable.
        """
        _LOGGER.info(f"Performed dries action")


class ECACleaningRag(ECAEntity):
    """
    ECACleaningRag is a virtual object that simulates a cleaning rag used for washing surfaces.
            It interacts with  objects and triggers the washing action when it comes into contact with them.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="washes")
    async def async_washes(self, surface: ECASurface) -> None:
        """
        Washes is a method that simulates the action of cleaning a surface using the rag.
            It is triggered when the rag interacts with a surface, typically via collision detection.
        Argument:
            -surface:The  to be washed.
        """
        _LOGGER.info(f"Performed washes action - {surface}")


class ECAScottex(ECAEntity):
    """
    ECAScottex represents a virtual disposable paper towel used to clean surfaces in the simulation.
            It interacts with surfaces by sweeping over them and is automatically linked to a soakable cleaning system via the  component.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="sweeps")
    async def async_sweeps(self, surface: ECASurface) -> None:
        """
        Sweeps is a method that simulates the action of the scottex wiping or cleaning a given surface.
            This action is used to trigger an ECA event when a surface is swept by the object.
        Argument:
            -surface:The surface being swept by the scottex.
        """
        _LOGGER.info(f"Performed sweeps action - {surface}")


class ECADustBall(ECAEntity):
    """
    ECADustBall is a Behaviour that attaches dust balls to a virtual object, ideally a  Surface.
            It can be "swept" using other objects such as brooms or scottex, and define the number of sweeps needed until all dust is removed.
            Once fully swept, the object updates its state and optionally plays audio feedback.

    Attributes:
    - sweepsCounter (int): sweepsCounter defines how many times the dust ball needs to be swept before it's considered clean.
            Each sweep reduces this counter until it reaches zero, triggering a "fully swept" state.
    - allSwept (ECABoolean): allSwept indicates whether all the dust has been successfully removed from the object.
            It becomes true once the sweeps counter reaches zero.

    """

    def __init__(
        self, sweepsCounter: int, allSwept: ECABoolean, **kwargs: dict
    ) -> None:
        super().__init__(**kwargs)
        self._sweepsCounter = sweepsCounter
        self._allSwept = allSwept
        self._attr_should_poll = False

    @property
    def sweepsCounter(self) -> int:
        return self._sweepsCounter

    @property
    def allSwept(self) -> ECABoolean:
        return self._allSwept

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "sweepsCounter": self.sweepsCounter,
            "allSwept": self.allSwept,
            **super_extra_attributes,
        }

    @eca_script_action(verb="changes", variable="sweepsCounter", modifier="to")
    async def async_changes(self, v: int) -> None:
        """
        Changes the value of the sweeps counter to a specified integer.
            This method ensures the new value is not negative and updates the internal sweep logic accordingly.
        Argument:
            -v:The new counter value.
        """
        _LOGGER.info(f"Performed changes action - {v}")

    @eca_script_action(verb="increasingly-removes-dust")
    async def async_increasingly_removes_dust_(self, scottex: ECAScottex) -> None:
        """
        increasingly-removes-dust simulates a sweeping action by a , decreasing by one the number of sweeps needed.
            When enough sweeps are performed, the dust ball is considered clean.
        Argument:
            -scottex:The scottex object performing the sweep.
        """
        _LOGGER.info(f"Performed increasingly_removes_dust_ action - {scottex}")

    @eca_script_action(verb="increasingly-removes-dust")
    async def async_increasingly_removes_dust_(self, broom: ECABroom) -> None:
        """
        increasingly-removes-dust simulates a sweeping action by a , decreasing by one the number of sweeps needed.
            When enough sweeps are performed, the dust ball is considered clean.
        Argument:
            -scottex:The scottex object performing the sweep.
        """
        _LOGGER.info(f"Performed increasingly_removes_dust_ action - {broom}")


class ECADustPan(ECAEntity):
    """
    ECADustPan is a virtual object that simulates the behavior of a dustpan used in cleaning tasks.
            It has a method for collecting dust balls ().

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="collects-dust")
    async def async_collects_dust(self, dustBall: ECADustBall) -> None:
        """
        CollectsDust is a method that simulates the action of the dustpan collecting a dust ball.
        Argument:
            -dustBall:The  object being collected.
        """
        _LOGGER.info(f"Performed collects_dust action - {dustBall}")


class ECAMop(ECAEntity):
    """
    ECAMop represents a virtual mop used to clean surfaces within the simulation.
            It is designed to interact with surfaces by "washing" them, typically triggered when coming into contact with a surface.

    Attributes:

    """

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}

    @eca_script_action(verb="washes")
    async def async_washes(self, surface: ECASurface) -> None:
        """
        Washes is a method that simulates the action of the mop cleaning a surface.
            This action is triggered when the mop collides with a surface object, and notifies the automation system accordingly.
        Argument:
            -surface:The surface being cleaned by the mop.
        """
        _LOGGER.info(f"Performed washes action - {surface}")


class ECAInteraction(ECAEntity):
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
        return {**super_extra_attributes}


class ECAButton(ECAEntity):
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
        return {**super_extra_attributes}

    @eca_script_action(verb="pushes")
    async def async_pushes(self, c: ECACharacter) -> None:
        """
        Presses is a passive function that represents the pressing of the button by a character C.
        Argument:
            -c:The  who presses the button.
        """
        _LOGGER.info(f"Performed pushes action - {c}")


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

    def __init__(
        self,
        intensity: float,
        maxIntensity: float,
        color: dict,
        on: ECABoolean,
        **kwargs: dict,
    ) -> None:
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
            **super_extra_attributes,
        }

    @eca_script_action(verb="turns")
    async def async_turns(self, newStatus: ECABoolean) -> None:
        """
        Turns toggles the light source on or off based on the specified value ("on" or "off"), enabling or disabling illumination.
        Argument:
            -newStatus:The desired state of the light source (on or off).
        """
        _LOGGER.info(f"Performed turns action - {newStatus}")

    @eca_script_action(verb="increases", variable="intensity", modifier="by")
    async def async_increases(self, amount: float) -> None:
        """
        IncreasesIntensity increases the brightness of the light source by a specified non-negative amount.
            If the resulting intensity exceeds the maximum allowed value, it is capped at maxIntensity.
        Argument:
            -amount:The value to add to the current intensity.
        """
        _LOGGER.info(f"Performed increases action - {amount}")

    @eca_script_action(verb="decreases", variable="intensity", modifier="by")
    async def async_decreases(self, amount: float) -> None:
        """
        DecreasesIntensity reduces the brightness of the light source by a specified non-negative amount.
            If the resulting intensity drops below zero, it is set to zero to avoid negative values.
        Argument:
            -amount:The value to subtract from the current intensity.
        """
        _LOGGER.info(f"Performed decreases action - {amount}")

    @eca_script_action(verb="sets", variable="intensity", modifier="to")
    async def async_sets(self, i: float) -> None:
        _LOGGER.info(f"Performed sets action - {i}")

    @eca_script_action(verb="changes", variable="color", modifier="to")
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

    def __init__(
        self,
        source: str,
        volume: float,
        maxVolume: float,
        playing: ECABoolean,
        paused: ECABoolean,
        stopped: ECABoolean,
        **kwargs: dict,
    ) -> None:
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
            **super_extra_attributes,
        }

    @eca_script_action(verb="plays")
    async def async_plays(self) -> None:
        """
        Plays starts the video.
        """
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb="pauses")
    async def async_pauses(self) -> None:
        """
        Pauses pauses the video.
        """
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb="stops")
    async def async_stops(self) -> None:
        """
        Stops stops the video.
        """
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb="changes", variable="volume", modifier="to")
    async def async_changes_volume(self, v: float) -> None:
        """
        ChangesVolume changes the video volume to the given value.
            If the value is greater than the max volume, the volume is set to the max volume.
            If the value is lower than 0, the volume is set to 0.
        Argument:
            -v:The new video volume.
        """
        _LOGGER.info(f"Performed changes_volume action - {v}")

    @eca_script_action(verb="changes", variable="source", modifier="to")
    async def async_changes_source(self, newSource: str) -> None:
        """
        ChangesSource changes the video source to the given value.
            The new path must be relative to the user-accessible Inventory folder.
        Argument:
            -newSource:The path for the new video file.
        """
        _LOGGER.info(f"Performed changes_source action - {newSource}")


class ECAAnimal(ECAEntity):
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
        return {**super_extra_attributes}

    @eca_script_action(verb="speaks")
    async def async_speaks(self, s: str) -> None:
        """
        Speaks allows the animal to produce a sound or "speak" by playing an associated audio clip.
            The audio clip is identified by the provided string, which must correspond to a valid resource.
        Argument:
            -s:The name of the audio resource to be played.
        """
        _LOGGER.info(f"Performed speaks action - {s}")


class ECAHuman(ECAEntity):
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
        return {**super_extra_attributes}

    @eca_script_action(verb="runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        """
        Runs (to) is a method that moves the human to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb="runs on")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        """
        Runs (to) is a method that moves the human to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb="swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        """
        Swims (to) is a method that moves the human to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb="swims on")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        """
        Swims (to) is a method that moves the human to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb="walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the human to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb="walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the human to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class ECARobot(ECAEntity):
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
        return {**super_extra_attributes}

    @eca_script_action(verb="runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        """
        Runs (to) is a method that moves the robot to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb="runs on")
    async def async_runs_on(self, p: list[ECAPosition]) -> None:
        """
        Runs (to) is a method that moves the robot to a specific position with a running animation.
        Argument:
            -p:The target position to run to.
        """
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb="swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        """
        Swims (to) is a method that moves the robot to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb="swims on")
    async def async_swims_on(self, p: list[ECAPosition]) -> None:
        """
        Swims (to) is a method that moves the robot to a specific position with a swimming animation.
        Argument:
            -p:The target position to swim to.
        """
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb="walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        """
        Walks (to) is a method that moves the robot to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb="walks on")
    async def async_walks_on(self, p: list[ECAPosition]) -> None:
        """
        Walks (to) is a method that moves the robot to a specific position with a walking animation.
        Argument:
            -p:The target position to move to.
        """
        _LOGGER.info(f"Performed walks_on action - {p}")


class ECAOilStain(ECAEntity):
    """
    ECAOilStain is a Behaviour that attaches oil stains to a virtual object, ideally a  Surface.
            It can be "washed" using other objects such as mops or cleaning rags, and define the number of washes needed until all stains are removed.
            Once fully washed, the object updates its state and optionally plays audio feedback.

    Attributes:
    - washesCounter (int): washesCounter defines how many times the oil stains needs to be washed before it's considered clean.
            Each wash reduces this counter until it reaches zero, triggering a "fully washed" state.
    - allWashed (ECABoolean): allWashed indicates whether all the stains have been successfully removed from the object.
            It becomes true once the washes counter reaches zero.

    """

    def __init__(
        self, washesCounter: int, allWashed: ECABoolean, **kwargs: dict
    ) -> None:
        super().__init__(**kwargs)
        self._washesCounter = washesCounter
        self._allWashed = allWashed
        self._attr_should_poll = False

    @property
    def washesCounter(self) -> int:
        return self._washesCounter

    @property
    def allWashed(self) -> ECABoolean:
        return self._allWashed

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
            "washesCounter": self.washesCounter,
            "allWashed": self.allWashed,
            **super_extra_attributes,
        }

    @eca_script_action(verb="changes", variable="washesCounter", modifier="to")
    async def async_changes(self, v: int) -> None:
        """
        Changes the value of the washes counter to a specified integer.
            This method ensures the new value is not negative and updates the internal wash logic accordingly.
        Argument:
            -v:The new counter value.
        """
        _LOGGER.info(f"Performed changes action - {v}")

    @eca_script_action(verb="increasingly-removes-stain")
    async def async_increasingly_removes_stain_(
        self, cleaningRag: ECACleaningRag
    ) -> None:
        """
        increasingly-removes-stain simulates a washing action by a , decreasing by one the number of washes needed.
            When enough washes are performed, the oil stains are considered clean.
        Argument:
            -cleaningRag:The cleaning rag object performing the wash.
        """
        _LOGGER.info(f"Performed increasingly_removes_stain_ action - {cleaningRag}")

    @eca_script_action(verb="increasingly-removes-stain")
    async def async_increasingly_removes_stain_(self, mop: ECAMop) -> None:
        """
        increasingly-removes-stain simulates a washing action by a , decreasing by one the number of washes needed.
            When enough washes are performed, the oil stains are considered clean.
        Argument:
            -cleaningRag:The cleaning rag object performing the wash.
        """
        _LOGGER.info(f"Performed increasingly_removes_stain_ action - {mop}")


class ECAPhysicalGrabbable(ECAEntity):
    """
    ECAPhysicalGrabbable represents a physical object in the scene that can be grabbed by the player using one or both hands.
            It tracks the grabbing state, handles interaction logic based on trigger collisions with hand colliders, and communicates grabbing events through the automation system.

    Attributes:
    - grabbed (ECABoolean): grabbed indicates whether the object is currently being held by the player.
            This state is updated based on collision triggers with hand colliders and is used to drive interactive behaviors.

    """

    def __init__(self, grabbed: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._grabbed = grabbed
        self._attr_should_poll = False

    @property
    def grabbed(self) -> ECABoolean:
        return self._grabbed

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {"grabbed": self.grabbed, **super_extra_attributes}

    @eca_script_action(verb="starts-grabbing")
    async def async_starts_grabbing(self, c: ECACharacter) -> None:
        """
        starts-grabbing is triggered when the player begins to grab the object with either hand.
            Updates the  state and notifies the system about the interaction.
        Argument:
            -c:The character initiating the grab.
        """
        _LOGGER.info(f"Performed starts_grabbing action - {c}")

    @eca_script_action(verb="stops-grabbing")
    async def async_stops_grabbing(self, c: ECACharacter) -> None:
        """
        stops-grabbing is triggered when the player releases the object with both hands.
            Resets the  state and notifies the system of the interaction ending.
        Argument:
            -c:The character releasing the object.
        """
        _LOGGER.info(f"Performed stops_grabbing action - {c}")


class ECAHighlight(ECAEntity):
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
        return {"color": self.color, "on": self.on, **super_extra_attributes}

    @eca_script_action(verb="changes", variable="color", modifier="to")
    async def async_changes(self, c: dict) -> None:
        """
        ChangesColor changes the color of the outline.
        Argument:
            -c:
        """
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb="turns")
    async def async_turns(self, on: ECABoolean) -> None:
        """
        TurnsOn turns the highlight on or off.
        Argument:
            -on:
        """
        _LOGGER.info(f"Performed turns action - {on}")


class ECASound(ECAEntity):
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

    def __init__(
        self,
        source: str,
        volume: float,
        maxVolume: float,
        currentTime: float,
        playing: ECABoolean,
        paused: ECABoolean,
        stopped: ECABoolean,
        **kwargs: dict,
    ) -> None:
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
            **super_extra_attributes,
        }

    @eca_script_action(verb="plays")
    async def async_plays(self) -> None:
        """
        Plays starts the audio playback.
            Updates the state variables playing, stopped, and paused to reflect that playback is active.
        """
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb="pauses")
    async def async_pauses(self) -> None:
        """
        Pauses pauses the audio playback.
            Maintains the current playback time (currentTime) for resuming later (by calling Plays).
        """
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb="stops")
    async def async_stops(self) -> None:
        """
        Stops stops the audio playback and resets the playback time (currentTime) to the beginning.
        """
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb="changes", variable="volume", modifier="to")
    async def async_changes_volume(self, v: float) -> None:
        """
        ChangesVolume changes the volume of the audio to a given value.
            Ensures the value remains within the range of 0 to
        Argument:
            -v:The new volume value.
        """
        _LOGGER.info(f"Performed changes_volume action - {v}")

    @eca_script_action(verb="changes", variable="source", modifier="to")
    async def async_changes_source(self, newSource: str) -> None:
        """
        ChangesSource changes the audio filename source to the given filename.
            Validates the path and dynamically loads the audio for playback.
        Argument:
            -newSource:The new audio filename.
        """
        _LOGGER.info(f"Performed changes_source action - {newSource}")


########## DO NOT DELETE IT
CURRENT_MODULE = sys.modules[__name__]
