"""Nuki.io lock platform."""
from abc import ABC, abstractmethod
from datetime import timedelta
import logging

from pynuki import NukiBridge
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.lock import PLATFORM_SCHEMA, SUPPORT_OPEN, LockEntity
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import extract_entity_ids

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 20

ATTR_BATTERY_CRITICAL = "battery_critical"
ATTR_NUKI_ID = "nuki_id"
ATTR_UNLATCH = "unlatch"

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=5)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

NUKI_DATA = "nuki"

SERVICE_LOCK_N_GO = "lock_n_go"

ERROR_STATES = (0, 254, 255)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_TOKEN): cv.string,
    }
)

LOCK_N_GO_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_UNLATCH, default=False): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nuki lock platform."""
    bridge = NukiBridge(
        config[CONF_HOST], config[CONF_TOKEN], config[CONF_PORT], DEFAULT_TIMEOUT,
    )

    devices = [NukiLockEntity(lock) for lock in bridge.locks]

    def service_handler(service):
        """Service handler for nuki services."""
        entity_ids = extract_entity_ids(hass, service)
        unlatch = service.data[ATTR_UNLATCH]

        for lock in devices:
            if lock.entity_id not in entity_ids:
                continue
            lock.lock_n_go(unlatch=unlatch)

    hass.services.register(
        DOMAIN, SERVICE_LOCK_N_GO, service_handler, schema=LOCK_N_GO_SERVICE_SCHEMA,
    )

    devices.extend([NukiOpenerEntity(opener) for opener in bridge.openers])

    add_entities(devices)


class NukiDeviceEntity(LockEntity, ABC):
    """Representation of a Nuki device."""

    def __init__(self, nuki_device):
        """Initialize the lock."""
        self._nuki_device = nuki_device
        self._available = nuki_device.state not in ERROR_STATES

    @property
    def name(self):
        """Return the name of the lock."""
        return self._nuki_device.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._nuki_device.nuki_id

    @property
    @abstractmethod
    def is_locked(self):
        """Return true if lock is locked."""

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_BATTERY_CRITICAL: self._nuki_device.battery_critical,
            ATTR_NUKI_ID: self._nuki_device.nuki_id,
        }
        return data

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update the nuki lock properties."""
        for level in (False, True):
            try:
                self._nuki_device.update(aggressive=level)
            except RequestException:
                _LOGGER.warning("Network issues detect with %s", self.name)
                self._available = False
                continue

            # If in error state, we force an update and repoll data
            self._available = self._nuki_device.state not in ERROR_STATES
            if self._available:
                break

    @abstractmethod
    def lock(self, **kwargs):
        """Lock the device."""

    @abstractmethod
    def unlock(self, **kwargs):
        """Unlock the device."""

    @abstractmethod
    def open(self, **kwargs):
        """Open the door latch."""


class NukiLockEntity(NukiDeviceEntity):
    """Representation of a Nuki lock."""

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._nuki_device.is_locked

    def lock(self, **kwargs):
        """Lock the device."""
        self._nuki_device.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._nuki_device.unlock()

    def open(self, **kwargs):
        """Open the door latch."""
        self._nuki_device.unlatch()

    def lock_n_go(self, unlatch=False, **kwargs):
        """Lock and go.

        This will first unlock the door, then wait for 20 seconds (or another
        amount of time depending on the lock settings) and relock.
        """
        self._nuki_device.lock_n_go(unlatch, kwargs)


class NukiOpenerEntity(NukiDeviceEntity):
    """Representation of a Nuki opener."""

    @property
    def is_locked(self):
        """Return true if ring-to-open is enabled."""
        return not self._nuki_device.is_rto_activated

    def lock(self, **kwargs):
        """Disable ring-to-open."""
        self._nuki_device.deactivate_rto()

    def unlock(self, **kwargs):
        """Enable ring-to-open."""
        self._nuki_device.activate_rto()

    def open(self, **kwargs):
        """Buzz open the door."""
        self._nuki_device.electric_strike_actuation()
