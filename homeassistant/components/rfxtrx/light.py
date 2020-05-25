"""Support for RFXtrx lights."""
import logging

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DEVICES,
    CONF_FIRE_EVENT,
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    RECEIVED_EVT_SUBSCRIBERS,
    RfxtrxDevice,
    apply_received_command,
    get_devices_from_config,
    get_new_device,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
                }
            )
        },
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
        vol.Optional(
            CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS
        ): vol.Coerce(int),
    }
)

SUPPORT_RFXTRX = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RFXtrx platform."""
    lights = get_devices_from_config(config, RfxtrxLight)
    add_entities(lights)

    def light_update(event):
        """Handle light updates from the RFXtrx gateway."""
        if (
            not isinstance(event.device, rfxtrxmod.LightingDevice)
            or not event.device.known_to_be_dimmable
        ):
            return

        new_device = get_new_device(event, config, RfxtrxLight)
        if new_device:
            add_entities([new_device])

        apply_received_command(event)

    # Subscribe to main RFXtrx events
    if light_update not in RECEIVED_EVT_SUBSCRIBERS:
        RECEIVED_EVT_SUBSCRIBERS.append(light_update)


class RfxtrxLight(RfxtrxDevice, LightEntity, RestoreEntity):
    """Representation of a RFXtrx light."""

    async def async_added_to_hass(self):
        """Restore RFXtrx device state (ON/OFF)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_ON

        # Restore the brightness of dimmable devices
        if (
            old_state is not None
            and old_state.attributes.get(ATTR_BRIGHTNESS) is not None
        ):
            self._brightness = int(old_state.attributes[ATTR_BRIGHTNESS])

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_RFXTRX

    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            self._brightness = 255
            self._send_command("turn_on")
        else:
            self._brightness = brightness
            _brightness = brightness * 100 // 255
            self._send_command("dim", _brightness)
