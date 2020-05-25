"""Support for Vera cover - curtains, rollershutters etc."""
import logging
from typing import Callable, List

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import VeraDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    controller_data = hass.data[DOMAIN]
    async_add_entities(
        [
            VeraCover(device, controller_data.controller)
            for device in controller_data.devices.get(PLATFORM_DOMAIN)
        ]
    )


class VeraCover(VeraDevice, CoverEntity):
    """Representation a Vera Cover."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        0 is closed, 100 is fully open.
        """
        position = self.vera_device.get_level()
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.vera_device.set_level(kwargs.get(ATTR_POSITION))
        self.schedule_update_ha_state()

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            return self.current_cover_position == 0

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.vera_device.open()
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.vera_device.close()
        self.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.vera_device.stop()
        self.schedule_update_ha_state()
