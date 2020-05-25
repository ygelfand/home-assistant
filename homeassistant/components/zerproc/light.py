"""Zerproc light platform."""
from datetime import timedelta
import logging
from typing import Callable, List

import pyzerproc

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    Light,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_ZERPROC = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

DISCOVERY_INTERVAL = timedelta(seconds=60)

PARALLEL_UPDATES = 0


def connect_lights(lights: List[pyzerproc.Light]) -> List[pyzerproc.Light]:
    """Attempt to connect to lights, and return the connected lights."""
    connected = []
    for light in lights:
        try:
            light.connect(auto_reconnect=True)
            connected.append(light)
        except pyzerproc.ZerprocException:
            _LOGGER.debug("Unable to connect to '%s'", light.address, exc_info=True)

    return connected


def discover_entities(hass: HomeAssistant) -> List[Entity]:
    """Attempt to discover new lights."""
    lights = pyzerproc.discover()

    # Filter out already discovered lights
    new_lights = [
        light for light in lights if light.address not in hass.data[DOMAIN]["addresses"]
    ]

    entities = []
    for light in connect_lights(new_lights):
        # Double-check the light hasn't been added in another thread
        if light.address not in hass.data[DOMAIN]["addresses"]:
            hass.data[DOMAIN]["addresses"].add(light.address)
            entities.append(ZerprocLight(light))

    return entities


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Abode light devices."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "addresses" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["addresses"] = set()

    warned = False

    async def discover(*args):
        """Wrap discovery to include params."""
        nonlocal warned
        try:
            entities = await hass.async_add_executor_job(discover_entities, hass)
            async_add_entities(entities, update_before_add=True)
            warned = False
        except pyzerproc.ZerprocException:
            if warned is False:
                _LOGGER.warning("Error discovering Zerproc lights", exc_info=True)
                warned = True

    # Initial discovery
    hass.async_create_task(discover())

    # Perform recurring discovery of new devices
    async_track_time_interval(hass, discover, DISCOVERY_INTERVAL)


class ZerprocLight(Light):
    """Representation of an Zerproc Light."""

    def __init__(self, light):
        """Initialize a Zerproc light."""
        self._light = light
        self._name = None
        self._is_on = None
        self._hs_color = None
        self._brightness = None
        self._available = True

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self.on_hass_shutdown
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self.hass.async_add_executor_job(self._light.disconnect)

    def on_hass_shutdown(self, event):
        """Execute when Home Assistant is shutting down."""
        self._light.disconnect()

    @property
    def name(self):
        """Return the display name of this light."""
        return self._light.name

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._light.address

    @property
    def device_info(self):
        """Device info for this light."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Zerproc",
        }

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ZERPROC

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color."""
        return self._hs_color

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        if ATTR_BRIGHTNESS in kwargs or ATTR_HS_COLOR in kwargs:
            default_hs = (0, 0) if self._hs_color is None else self._hs_color
            hue_sat = kwargs.get(ATTR_HS_COLOR, default_hs)

            default_brightness = 255 if self._brightness is None else self._brightness
            brightness = kwargs.get(ATTR_BRIGHTNESS, default_brightness)

            rgb = color_util.color_hsv_to_RGB(*hue_sat, brightness / 255 * 100)
            self._light.set_color(*rgb)
        else:
            self._light.turn_on()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.turn_off()

    def update(self):
        """Fetch new state data for this light."""
        try:
            state = self._light.get_state()
        except pyzerproc.ZerprocException:
            if self._available:
                _LOGGER.warning("Unable to connect to %s", self.entity_id)
            self._available = False
            return
        if self._available is False:
            _LOGGER.info("Reconnected to %s", self.entity_id)
            self._available = True
        self._is_on = state.is_on
        hsv = color_util.color_RGB_to_hsv(*state.color)
        self._hs_color = hsv[:2]
        self._brightness = int(round((hsv[2] / 100) * 255))
