"""Sensor for displaying the number of result from Flume."""
from datetime import timedelta
import logging

from pyflume import FlumeData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEFAULT_NAME,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_TYPE,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the platform into a config entry."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flume sensor."""

    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]

    flume_auth = flume_domain_data[FLUME_AUTH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = flume_domain_data[FLUME_DEVICES]

    config = config_entry.data
    name = config.get(CONF_NAME, DEFAULT_NAME)

    flume_entity_list = []
    for device in flume_devices.device_list:
        if device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR:
            continue

        device_id = device[KEY_DEVICE_ID]
        device_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]
        device_friendly_name = f"{name} {device_name}"
        flume_device = FlumeData(
            flume_auth,
            device_id,
            SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )
        flume_entity_list.append(
            FlumeSensor(flume_device, device_friendly_name, device_id)
        )

    if flume_entity_list:
        async_add_entities(flume_entity_list)


class FlumeSensor(Entity):
    """Representation of the Flume sensor."""

    def __init__(self, flume_device, name, device_id):
        """Initialize the Flume sensor."""
        self._flume_device = flume_device
        self._name = name
        self._device_id = device_id
        self._undo_track_sensor = None
        self._available = False
        self._state = None

    @property
    def device_info(self):
        """Device info for the flume sensor."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "Flume, Inc.",
            "model": "Flume Smart Water Monitor",
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        # This is in gallons per SCAN_INTERVAL
        return "gal/m"

    @property
    def available(self):
        """Device is available."""
        return self._available

    @property
    def unique_id(self):
        """Device unique ID."""
        return self._device_id

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating flume sensor: %s", self._name)
        try:
            self._flume_device.update_force()
        except Exception as ex:  # pylint: disable=broad-except
            if self._available:
                _LOGGER.error("Update of flume sensor %s failed: %s", self._name, ex)
            self._available = False
            return
        _LOGGER.debug("Successful update of flume sensor: %s", self._name)
        self._state = self._flume_device.value
        self._available = True

    async def async_added_to_hass(self):
        """Request an update when added."""
        # We do ask for an update with async_add_entities()
        # because it will update disabled entities
        self.async_schedule_update_ha_state()
