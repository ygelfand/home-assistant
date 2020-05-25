"""Support for Spider thermostats."""

import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import DOMAIN as SPIDER_DOMAIN

SUPPORT_FAN = ["Auto", "Low", "Medium", "High", "Boost 10", "Boost 20", "Boost 30"]

SUPPORT_HVAC = [HVAC_MODE_HEAT, HVAC_MODE_COOL]

HA_STATE_TO_SPIDER = {
    HVAC_MODE_COOL: "Cool",
    HVAC_MODE_HEAT: "Heat",
    HVAC_MODE_OFF: "Idle",
}

SPIDER_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_SPIDER.items()}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Spider thermostat."""
    if discovery_info is None:
        return

    devices = [
        SpiderThermostat(hass.data[SPIDER_DOMAIN]["controller"], device)
        for device in hass.data[SPIDER_DOMAIN]["thermostats"]
    ]
    add_entities(devices, True)


class SpiderThermostat(ClimateEntity):
    """Representation of a thermostat."""

    def __init__(self, api, thermostat):
        """Initialize the thermostat."""
        self.api = api
        self.thermostat = thermostat

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supports = SUPPORT_TARGET_TEMPERATURE

        if self.thermostat.has_fan_mode:
            supports |= SUPPORT_FAN_MODE

        return supports

    @property
    def unique_id(self):
        """Return the id of the thermostat, if any."""
        return self.thermostat.id

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self.thermostat.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat.current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.thermostat.target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.thermostat.temperature_steps

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.thermostat.minimum_temperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.thermostat.maximum_temperature

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return SPIDER_STATE_TO_HA[self.thermostat.operation_mode]

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return SUPPORT_HVAC

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self.thermostat.set_temperature(temperature)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        self.thermostat.set_operation_mode(HA_STATE_TO_SPIDER.get(hvac_mode))

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.thermostat.current_fan_speed

    def set_fan_mode(self, fan_mode):
        """Set fan mode."""
        self.thermostat.set_fan_speed(fan_mode)

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return SUPPORT_FAN

    def update(self):
        """Get the latest data."""
        self.thermostat = self.api.get_thermostat(self.unique_id)
