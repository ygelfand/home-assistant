"""Support for the Abode Security System locks."""
import logging

import abodepy.helpers.constants as CONST

from homeassistant.components.lock import LockDevice

from . import AbodeDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode lock devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device in data.abode.get_devices(generic_type=CONST.TYPE_LOCK):
        entities.append(AbodeLock(data, device))

    async_add_entities(entities)


class AbodeLock(AbodeDevice, LockDevice):
    """Representation of an Abode lock."""

    def lock(self, **kwargs):
        """Lock the device."""
        self._device.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._device.unlock()

    @property
    def is_locked(self):
        """Return true if device is on."""
        return self._device.is_locked
