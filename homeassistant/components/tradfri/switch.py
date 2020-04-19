"""Support for IKEA Tradfri switches."""
from homeassistant.components.switch import SwitchDevice

from .base_class import TradfriBaseDevice
from .const import CONF_GATEWAY_ID, KEY_API, KEY_GATEWAY


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Tradfri switches based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    api = hass.data[KEY_API][config_entry.entry_id]
    gateway = hass.data[KEY_GATEWAY][config_entry.entry_id]

    devices_commands = await api(gateway.get_devices())
    devices = await api(devices_commands)
    switches = [dev for dev in devices if dev.has_socket_control]
    if switches:
        async_add_entities(
            TradfriSwitch(switch, api, gateway_id) for switch in switches
        )


class TradfriSwitch(TradfriBaseDevice, SwitchDevice):
    """The platform class required by Home Assistant."""

    def __init__(self, device, api, gateway_id):
        """Initialize a switch."""
        super().__init__(device, api, gateway_id)
        self._unique_id = f"{gateway_id}-{device.id}"

    def _refresh(self, device):
        """Refresh the switch data."""
        super()._refresh(device)

        # Caching of switch control and switch object
        self._device_control = device.socket_control
        self._device_data = device.socket_control.sockets[0]

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device_data.state

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        await self._api(self._device_control.set_state(False))

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        await self._api(self._device_control.set_state(True))
