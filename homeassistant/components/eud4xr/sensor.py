import logging
import sys

import voluptuous as vol

from homeassistant.const import CONF_SENSORS
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import *
from .eca_classes import ECABoolean, ECAColor, ECAPosition, ECARotation, ECAScale
from .entity import ECAEntity
from .utils import MappedClasses, eca_script_action

_LOGGER = logging.getLogger(__name__)

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

NOTIFICATION_ACTION_FROM_UNITY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM_UNITY_ID): cv.string,
        vol.Required(CONF_SERVICE_UPDATE_FROM_UNITY_VERB): cv.string,
        vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_VARIABLE): cv.string,
        vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_MODIFIER): cv.string,
        vol.Optional(CONF_SERVICE_UPDATE_FROM_UNITY_PARAMETERS): dict,
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
        ECA_SCRIPTS = MappedClasses.mapping_classes(CURRENT_MODULE, hass)

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


class ECAObject(ECAEntity):
    def __init__(
        self,
        position: dict,
        rotation: dict,
        scale: dict,
        visible: str,
        active: str,
        isInsideCamera: str,
        **kwargs: dict,
    ) -> None:
        super().__init__(**kwargs)
        self._position = position
        self._rotation = rotation
        self._scale = scale
        self._visible = visible
        self._active = active
        self._isInsideCamera = isInsideCamera
        self._attr_should_poll = False

    @property
    def position(self) -> dict:
        return self._position

    @property
    def rotation(self) -> dict:
        return self._rotation

    @property
    def scale(self) -> dict:
        return self._scale

    @property
    def visible(self) -> str:
        return self._visible

    @property
    def active(self) -> str:
        return self._active

    @property
    def isInsideCamera(self) -> str:
        return self._isInsideCamera

    @property
    def extra_state_attributes(self):
        super_extra_attributes = super().extra_state_attributes
        return {
            "position": self.position,
            "rotation": self.rotation,
            "scale": self.scale,
            "visible": self.visible,
            "active": self.active,
            "isInsideCamera": self.isInsideCamera,
            **super_extra_attributes,
        }

    @eca_script_action("moves to")
    async def async_moves_to(self, newPos: ECAPosition) -> None:
        print(f"Performed moves_to action: {newPos} - {type(newPos)}")

    @eca_script_action("moves on")
    async def async_moves_on(self, path: list[ECAPosition]) -> None:
        print(f"Performed moves_on action: {path} - {type(path)}")

    @eca_script_action("rotates around")
    async def async_rotates_around(self, newRot: ECARotation) -> None:
        print(f"Performed rotates around action - {newRot}")

    @eca_script_action("looks to")
    async def async_looks_to(self, obj: ECAEntity) -> None:
        print(f"Performed looks_to action - {obj} - {type(obj)}")

    @eca_script_action("scales to")
    async def async_scales_to(self, newScale: ECAScale) -> None:
        print(f"Performed scales_to action - {newScale} - {type(newScale)}")

    @eca_script_action("restores original settings")
    async def async_restores_original_settings(self) -> None:
        print(f"Performed restores_original_settings action")

    @eca_script_action("shows")
    async def async_shows(self) -> None:
        print("Performed shows action")

    @eca_script_action("hides")
    async def async_hides(self) -> None:
        print("Performed hides action")

    @eca_script_action("activates")
    async def async_activates(self) -> None:
        print("Performed activates action")

    @eca_script_action("deactivates")
    async def async_deactivates(self) -> None:
        print("Performed deactivates action")

    @eca_script_action("changes", "visible")
    async def async_shows_hides(self, yesNo: ECABoolean) -> None:
        print("Performed shows hides")

    @eca_script_action("changes", "active")
    async def async_activates_deactivates(self, yesNo: ECABoolean) -> None:
        print(f"Performed activates deaactivates action: {yesNo}")


class Behaviour(ECAEntity):
    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {**super_extra_attributes}




class Vehicle(ECAEntity):

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
    async def async_wears(self, m: 'Mannequin') -> None:
        _LOGGER.info(f"Performed wears action - {m}")

    @eca_script_action(verb = "unwears")
    async def async_unwears(self, m: 'Mannequin') -> None:
        _LOGGER.info(f"Performed unwears action - {m}")

    @eca_script_action(verb = "wears")
    async def async_wears(self, c: object) -> None:
        _LOGGER.info(f"Performed wears action - {c}")

    @eca_script_action(verb = "unwears")
    async def async_unwears(self, c: object) -> None:
        _LOGGER.info(f"Performed unwears action - {c}")


class Electronic(ECAEntity):

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
        _LOGGER.info(f"Performed turns action - {on}")


class Food(ECAEntity):

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
    async def async_eats(self, c: object) -> None:
        _LOGGER.info(f"Performed eats action - {c}")


class Weapon(ECAEntity):

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
        _LOGGER.info(f"Performed stabs action - {obj}")

    @eca_script_action(verb = "slices")
    async def async_slices(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed slices action - {obj}")


class Firearm(ECAEntity):

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
        _LOGGER.info(f"Performed recharges action - {charge}")

    @eca_script_action(verb = "fires")
    async def async_fires(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed fires action - {obj}")

    @eca_script_action(verb = "aims")
    async def async_aims(self, obj: ECAObject) -> None:
        _LOGGER.info(f"Performed aims action - {obj}")


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
    async def async_blocks(self, weapon: Weapon) -> None:
        _LOGGER.info(f"Performed blocks action - {weapon}")


class Interaction(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
             **super_extra_attributes
        }


class Bounds(ECAEntity):

    def __init__(self, scale: float, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._scale = scale
        self._attr_should_poll = False

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
             "scale": self.scale,
             **super_extra_attributes
        }

    @eca_script_action(verb = "scales-to")
    async def async_scales_to(self, newScale: float) -> None:
        _LOGGER.info(f"Performed scales_to action - {newScale}")


class Button(ECAEntity):

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
    async def async_pushes(self, c: object) -> None:
        _LOGGER.info(f"Performed pushes action - {c}")


class ECACamera(ECAEntity):

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
        _LOGGER.info(f"Performed zooms_in action - {amount}")

    @eca_script_action(verb = "zooms-out")
    async def async_zooms_out(self, amount: float) -> None:
        _LOGGER.info(f"Performed zooms_out action - {amount}")

    @eca_script_action(verb = "changes", variable_name = "POV", modifier_string = "to")
    async def async_changes(self, pov: str) -> None:
        _LOGGER.info(f"Performed changes action - {pov}")


class ECALight(ECAEntity):

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
        _LOGGER.info(f"Performed turns action - {newStatus}")

    @eca_script_action(verb = "increases", variable_name = "intensity", modifier_string = "by")
    async def async_increases(self, amount: float) -> None:
        _LOGGER.info(f"Performed increases action - {amount}")

    @eca_script_action(verb = "decreases", variable_name = "intensity", modifier_string = "by")
    async def async_decreases(self, amount: float) -> None:
        _LOGGER.info(f"Performed decreases action - {amount}")

    @eca_script_action(verb = "sets", variable_name = "intensity", modifier_string = "to")
    async def async_sets(self, i: float) -> None:
        _LOGGER.info(f"Performed sets action - {i}")

    @eca_script_action(verb = "changes", variable_name = "color", modifier_string = "to")
    async def async_changes(self, inputColor: ECAColor) -> None:
        _LOGGER.info(f"Performed changes action - {inputColor}")


class ECAText(ECAEntity):

    def __init__(self, content: str, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._content = content
        self._attr_should_poll = False

    @property
    def content(self) -> str:
        return self._content

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
             "content": self.content,
             **super_extra_attributes
        }

    @eca_script_action(verb = "changes", variable_name = "content", modifier_string = "to")
    async def async_changes(self, c: str) -> None:
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb = "appends")
    async def async_appends(self, t: str) -> None:
        _LOGGER.info(f"Performed appends action - {t}")

    @eca_script_action(verb = "deletes")
    async def async_deletes(self, t: str) -> None:
        _LOGGER.info(f"Performed deletes action - {t}")


class ECAVideo(ECAEntity):

    def __init__(self, source: str, volume: float, maxVolume: float, duration: float, current_time: float, playing: ECABoolean, paused: ECABoolean, stopped: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._source = source
        self._volume = volume
        self._maxVolume = maxVolume
        self._duration = duration
        self._current_time = current_time
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
    def duration(self) -> float:
        return self._duration

    @property
    def current_time(self) -> float:
        return self._current_time

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
             "duration": self.duration,
             "current_time": self.current_time,
             "playing": self.playing,
             "paused": self.paused,
             "stopped": self.stopped,
             **super_extra_attributes
        }

    @eca_script_action(verb = "plays")
    async def async_plays(self) -> None:
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb = "pauses")
    async def async_pauses(self) -> None:
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "changes", variable_name = "volume", modifier_string = "to")
    async def async_changes(self, v: float) -> None:
        _LOGGER.info(f"Performed changes action - {v}")

    @eca_script_action(verb = "changes", variable_name = "current-time", modifier_string = "to")
    async def async_changes(self, c: float) -> None:
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb = "changes", variable_name = "source", modifier_string = "to")
    async def async_changes(self, newSource: str) -> None:
        _LOGGER.info(f"Performed changes action - {newSource}")


class Environment(ECAEntity):

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
        _LOGGER.info(f"Performed interacts_with action - {o}")

    @eca_script_action(verb = "stops-interacting with")
    async def async_stops_interacting_with(self, o: Interactable) -> None:
        _LOGGER.info(f"Performed stops_interacting_with action - {o}")

    @eca_script_action(verb = "jumps to")
    async def async_jumps_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed jumps_to action - {p}")

    @eca_script_action(verb = "jumps on")
    async def async_jumps_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed jumps_on action - {p}")

    @eca_script_action(verb = "starts-animation")
    async def async_starts_animation(self, s: str) -> None:
        _LOGGER.info(f"Performed starts_animation action - {s}")


class Animal(ECAEntity):

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
        _LOGGER.info(f"Performed speaks action - {s}")


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
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")


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
    async def async_flies_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed flies_to action - {p}")

    @eca_script_action(verb = "flies on")
    async def async_flies_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed flies_on action - {p}")

    @eca_script_action(verb = "runs to")
    async def async_runs_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


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
    async def async_flies_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed flies_to action - {p}")

    @eca_script_action(verb = "flies on")
    async def async_flies_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed flies_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


class Human(ECAEntity):

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
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


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


class Robot(ECAEntity):

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
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "swims to")
    async def async_swims_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed swims_to action - {p}")

    @eca_script_action(verb = "swims on")
    async def async_swims_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed swims_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


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
    async def async_runs_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed runs_to action - {p}")

    @eca_script_action(verb = "runs on")
    async def async_runs_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed runs_on action - {p}")

    @eca_script_action(verb = "walks to")
    async def async_walks_to(self, p: ECAPosition) -> None:
        _LOGGER.info(f"Performed walks_to action - {p}")

    @eca_script_action(verb = "walks on")
    async def async_walks_on(self, p: List[ECAPosition]) -> None:
        _LOGGER.info(f"Performed walks_on action - {p}")


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


class Container(ECAEntity):

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
        _LOGGER.info(f"Performed inserts action - {o}")

    @eca_script_action(verb = "removes")
    async def async_removes(self, o: object) -> None:
        _LOGGER.info(f"Performed removes action - {o}")

    @eca_script_action(verb = "empties")
    async def async_empties(self) -> None:
        _LOGGER.info(f"Performed empties action")


class Counter(ECAEntity):

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

    @eca_script_action(verb = "changes", variable_name = "count", modifier_string = "to")
    async def async_changes(self, amount: float) -> None:
        _LOGGER.info(f"Performed changes action - {amount}")


class Highlight(ECAEntity):

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

    @eca_script_action(verb = "changes", variable_name = "color", modifier_string = "to")
    async def async_changes(self, c: dict) -> None:
        _LOGGER.info(f"Performed changes action - {c}")

    @eca_script_action(verb = "turns")
    async def async_turns(self, on: ECABoolean) -> None:
        _LOGGER.info(f"Performed turns action - {on}")


class Interactable(ECAEntity):

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
             **super_extra_attributes
        }


class Keypad(ECAEntity):

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
        _LOGGER.info(f"Performed inserts action - {input}")

    @eca_script_action(verb = "adds")
    async def async_adds(self, input: str) -> None:
        _LOGGER.info(f"Performed adds action - {input}")

    @eca_script_action(verb = "resets")
    async def async_resets(self) -> None:
        _LOGGER.info(f"Performed resets action")


class Lock(ECAEntity):

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
        _LOGGER.info(f"Performed opens action")

    @eca_script_action(verb = "closes")
    async def async_closes(self) -> None:
        _LOGGER.info(f"Performed closes action")


class Particle(ECAEntity):

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
        _LOGGER.info(f"Performed turns action - {on}")


class Placeholder(ECAEntity):

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

    @eca_script_action(verb = "changes", variable_name = "mesh", modifier_string = "to")
    async def async_changes(self, meshName: str) -> None:
        _LOGGER.info(f"Performed changes action - {meshName}")


class Sound(ECAEntity):

    def __init__(self, source: str, volume: float, maxVolume: float, duration: float, currentTime: float, playing: ECABoolean, paused: ECABoolean, stopped: ECABoolean, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._source = source
        self._volume = volume
        self._maxVolume = maxVolume
        self._duration = duration
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
    def duration(self) -> float:
        return self._duration

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
             "duration": self.duration,
             "currentTime": self.currentTime,
             "playing": self.playing,
             "paused": self.paused,
             "stopped": self.stopped,
             **super_extra_attributes
        }

    @eca_script_action(verb = "plays")
    async def async_plays(self) -> None:
        _LOGGER.info(f"Performed plays action")

    @eca_script_action(verb = "pauses")
    async def async_pauses(self) -> None:
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "changes", variable_name = "volume", modifier_string = "to")
    async def async_changes_volume(self, v: float) -> None:
        _LOGGER.info(f"Performed changes action - {v}")

    @eca_script_action(verb = "changes", variable_name = "source", modifier_string = "to")
    async def async_changes_source(self, newSource: str) -> None:
        _LOGGER.info(f"Performed changes action - {newSource}")


class Switch(ECAEntity):

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
        _LOGGER.info(f"Performed turns action - {on}")


class Timer(ECAEntity):

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

    @eca_script_action(verb = "changes", variable_name = "duration", modifier_string = "to")
    async def async_changes(self, amount: float) -> None:
        _LOGGER.info(f"Performed changes action - {amount}")

    @eca_script_action(verb = "changes", variable_name = "current-time", modifier_string = "to")
    async def async_changes(self, amount: float) -> None:
        _LOGGER.info(f"Performed changes action - {amount}")

    @eca_script_action(verb = "starts")
    async def async_starts(self) -> None:
        _LOGGER.info(f"Performed starts action")

    @eca_script_action(verb = "stops")
    async def async_stops(self) -> None:
        _LOGGER.info(f"Performed stops action")

    @eca_script_action(verb = "pauses")
    async def async_pauses(self) -> None:
        _LOGGER.info(f"Performed pauses action")

    @eca_script_action(verb = "elapses-timer")
    async def async_elapses_timer(self, seconds: int) -> None:
        _LOGGER.info(f"Performed elapses_timer action - {seconds}")

    @eca_script_action(verb = "reaches")
    async def async_reaches(self, seconds: int) -> None:
        _LOGGER.info(f"Performed reaches action - {seconds}")

    @eca_script_action(verb = "resets")
    async def async_resets(self) -> None:
        _LOGGER.info(f"Performed resets action")


class Transition(ECAEntity):

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
        _LOGGER.info(f"Performed teleports_to action - {reference}")


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
    async def async_triggers(self, action: dict) -> None:
        _LOGGER.info(f"Performed triggers action - {action}")


class ClothingCategories(ECAEntity):

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

    def __init__(self, **kwargs: dict) -> None:
        super().__init__(**kwargs)
        self._attr_should_poll = False

    @property
    def extra_state_attributes(self) -> dict:
        super_extra_attributes = super().extra_state_attributes
        return {
             **super_extra_attributes
        }


CURRENT_MODULE = sys.modules[__name__]
