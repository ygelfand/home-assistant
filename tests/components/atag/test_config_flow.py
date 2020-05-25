"""Tests for the Atag config flow."""
from pyatag import AtagException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.atag import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_EMAIL, CONF_HOST, CONF_PORT

from tests.async_mock import PropertyMock, patch
from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_EMAIL: "test@domain.com",
    CONF_PORT: 10000,
}
FIXTURE_COMPLETE_ENTRY = FIXTURE_USER_INPUT.copy()
FIXTURE_COMPLETE_ENTRY[CONF_DEVICE] = "device_identifier"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass):
    """Test that only one Atag configuration is allowed."""
    MockConfigEntry(domain="atag", data=FIXTURE_USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error(hass):
    """Test we show user form on Atag connection error."""

    with patch(
        "homeassistant.components.atag.config_flow.AtagOne.authorize",
        side_effect=AtagException(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}


async def test_full_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch("homeassistant.components.atag.AtagOne.authorize",), patch(
        "homeassistant.components.atag.AtagOne.update",
    ), patch(
        "homeassistant.components.atag.AtagOne.id",
        new_callable=PropertyMock(return_value="device_identifier"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == FIXTURE_COMPLETE_ENTRY[CONF_DEVICE]
        assert result["data"] == FIXTURE_COMPLETE_ENTRY
