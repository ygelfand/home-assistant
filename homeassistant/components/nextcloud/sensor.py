"""Summary data from Nextcoud."""
import logging

from homeassistant.helpers.entity import Entity

from . import DOMAIN, SENSORS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nextcloud sensors."""
    if discovery_info is None:
        return
    sensors = []
    for name in hass.data[DOMAIN]:
        if name in SENSORS:
            sensors.append(NextcloudSensor(name))
    add_entities(sensors, True)


class NextcloudSensor(Entity):
    """Represents a Nextcloud sensor."""

    def __init__(self, item):
        """Initialize the Nextcloud sensor."""
        self._name = item
        self._state = None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:cloud"

    @property
    def name(self):
        """Return the name for this sensor."""
        return self._name

    @property
    def state(self):
        """Return the state for this sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return f"{self.hass.data[DOMAIN]['instance']}#{self._name}"

    def update(self):
        """Update the sensor."""
        self._state = self.hass.data[DOMAIN][self._name]
