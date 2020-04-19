"""Config flow to configure Coolmaster."""

from pycoolmasternet import CoolMasterNet
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PORT

# pylint: disable=unused-import
from .const import AVAILABLE_MODES, CONF_SUPPORTED_MODES, DEFAULT_PORT, DOMAIN

MODES_SCHEMA = {vol.Required(mode, default=True): bool for mode in AVAILABLE_MODES}

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, **MODES_SCHEMA})


async def _validate_connection(hass: core.HomeAssistant, host):
    cool = CoolMasterNet(host, port=DEFAULT_PORT)
    devices = await hass.async_add_executor_job(cool.devices)
    return bool(devices)


class CoolmasterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Coolmaster config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @core.callback
    def _async_get_entry(self, data):
        supported_modes = [
            key for (key, value) in data.items() if key in AVAILABLE_MODES and value
        ]
        return self.async_create_entry(
            title=data[CONF_HOST],
            data={
                CONF_HOST: data[CONF_HOST],
                CONF_PORT: DEFAULT_PORT,
                CONF_SUPPORTED_MODES: supported_modes,
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        host = user_input[CONF_HOST]

        try:
            result = await _validate_connection(self.hass, host)
            if not result:
                errors["base"] = "no_units"
        except (ConnectionRefusedError, TimeoutError):
            errors["base"] = "connection_error"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self._async_get_entry(user_input)
