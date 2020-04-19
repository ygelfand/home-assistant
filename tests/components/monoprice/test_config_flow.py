"""Test the Monoprice 6-Zone Amplifier config flow."""
from asynctest import patch
from serial import SerialException

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.monoprice.const import (
    CONF_SOURCE_1,
    CONF_SOURCE_4,
    CONF_SOURCE_5,
    CONF_SOURCES,
    DOMAIN,
)
from homeassistant.const import CONF_PORT

from tests.common import MockConfigEntry

CONFIG = {
    CONF_PORT: "/test/port",
    CONF_SOURCE_1: "one",
    CONF_SOURCE_4: "four",
    CONF_SOURCE_5: "    ",
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.monoprice.config_flow.get_async_monoprice",
        return_value=True,
    ), patch(
        "homeassistant.components.monoprice.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.monoprice.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == CONFIG[CONF_PORT]
    assert result2["data"] == {
        CONF_PORT: CONFIG[CONF_PORT],
        CONF_SOURCES: {"1": CONFIG[CONF_SOURCE_1], "4": CONFIG[CONF_SOURCE_4]},
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.monoprice.config_flow.get_async_monoprice",
        side_effect=SerialException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_generic_exception(hass):
    """Test we handle cannot generic exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.monoprice.config_flow.get_async_monoprice",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {CONF_PORT: "/test/port", CONF_SOURCES: {"4": "four"}}

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        # unique_id="abcde12345",
        data=conf,
        # options={CONF_SHOW_ON_MAP: True},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.monoprice.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SOURCE_1: "one", CONF_SOURCE_4: "", CONF_SOURCE_5: "five"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options[CONF_SOURCES] == {"1": "one", "5": "five"}
