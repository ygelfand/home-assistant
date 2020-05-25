"""Test the zerproc lights."""
from asynctest import patch
import pytest
import pyzerproc

from homeassistant import setup
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    SCAN_INTERVAL,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
)
from homeassistant.components.zerproc.light import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
async def mock_light(hass):
    """Create a mock light entity."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_entry = MockConfigEntry(domain=DOMAIN)
    mock_entry.add_to_hass(hass)

    light = pyzerproc.Light("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")

    mock_state = pyzerproc.LightState(False, (0, 0, 0))

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        return_value=[light],
    ), patch.object(light, "connect"), patch.object(
        light, "get_state", return_value=mock_state
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return light


async def test_init(hass):
    """Test platform setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_entry = MockConfigEntry(domain=DOMAIN)
    mock_entry.add_to_hass(hass)

    mock_light_1 = pyzerproc.Light("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")
    mock_light_2 = pyzerproc.Light("11:22:33:44:55:66", "LEDBlue-33445566")

    mock_state_1 = pyzerproc.LightState(False, (0, 0, 0))
    mock_state_2 = pyzerproc.LightState(True, (0, 80, 255))

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        return_value=[mock_light_1, mock_light_2],
    ), patch.object(mock_light_1, "connect"), patch.object(
        mock_light_2, "connect"
    ), patch.object(
        mock_light_1, "get_state", return_value=mock_state_1
    ), patch.object(
        mock_light_2, "get_state", return_value=mock_state_2
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("light.ledblue_ccddeeff")
    assert state.state == STATE_OFF
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
        ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
    }

    state = hass.states.get("light.ledblue_33445566")
    assert state.state == STATE_ON
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "LEDBlue-33445566",
        ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
        ATTR_BRIGHTNESS: 255,
        ATTR_HS_COLOR: (221.176, 100.0),
        ATTR_RGB_COLOR: (0, 80, 255),
        ATTR_XY_COLOR: (0.138, 0.08),
    }

    with patch.object(hass.loop, "stop"), patch.object(
        mock_light_1, "disconnect"
    ) as mock_disconnect_1, patch.object(
        mock_light_2, "disconnect"
    ) as mock_disconnect_2:
        await hass.async_stop()

    assert mock_disconnect_1.called
    assert mock_disconnect_2.called


async def test_discovery_exception(hass):
    """Test platform setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_entry = MockConfigEntry(domain=DOMAIN)
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        side_effect=pyzerproc.ZerprocException("TEST"),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # The exception should be captured and no entities should be added
    assert len(hass.data[DOMAIN]["addresses"]) == 0


async def test_connect_exception(hass):
    """Test platform setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_entry = MockConfigEntry(domain=DOMAIN)
    mock_entry.add_to_hass(hass)

    mock_light = pyzerproc.Light("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        return_value=[mock_light],
    ), patch.object(
        mock_light, "connect", side_effect=pyzerproc.ZerprocException("TEST")
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # The exception should be captured and no entities should be added
    assert len(hass.data[DOMAIN]["addresses"]) == 0


async def test_light_turn_on(hass, mock_light):
    """Test ZerprocLight turn_on."""
    utcnow = dt_util.utcnow()
    with patch.object(mock_light, "turn_on") as mock_turn_on:
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: "light.ledblue_ccddeeff"},
            blocking=True,
        )
        await hass.async_block_till_done()
    mock_turn_on.assert_called()

    with patch.object(mock_light, "set_color") as mock_set_color:
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_BRIGHTNESS: 25},
            blocking=True,
        )
        await hass.async_block_till_done()
    mock_set_color.assert_called_with(25, 25, 25)

    # Make sure no discovery calls are made while we emulate time passing
    with patch("homeassistant.components.zerproc.light.pyzerproc.discover"):
        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(True, (175, 150, 220)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_BRIGHTNESS: 25},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(19, 17, 25)

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_HS_COLOR: (50, 50)},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(220, 201, 110)

        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(True, (75, 75, 75)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_HS_COLOR: (50, 50)},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(75, 68, 37)

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {
                    ATTR_ENTITY_ID: "light.ledblue_ccddeeff",
                    ATTR_BRIGHTNESS: 200,
                    ATTR_HS_COLOR: (75, 75),
                },
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(162, 200, 50)


async def test_light_turn_off(hass, mock_light):
    """Test ZerprocLight turn_on."""
    with patch.object(mock_light, "turn_off") as mock_turn_off:
        await hass.services.async_call(
            "light",
            "turn_off",
            {ATTR_ENTITY_ID: "light.ledblue_ccddeeff"},
            blocking=True,
        )
        await hass.async_block_till_done()
    mock_turn_off.assert_called()


async def test_light_update(hass, mock_light):
    """Test ZerprocLight update."""
    utcnow = dt_util.utcnow()

    state = hass.states.get("light.ledblue_ccddeeff")
    assert state.state == STATE_OFF
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
        ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
    }

    # Make sure no discovery calls are made while we emulate time passing
    with patch("homeassistant.components.zerproc.light.pyzerproc.discover"):
        # Test an exception during discovery
        with patch.object(
            mock_light, "get_state", side_effect=pyzerproc.ZerprocException("TEST")
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        state = hass.states.get("light.ledblue_ccddeeff")
        assert state.state == STATE_UNAVAILABLE
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
            ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
        }

        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(False, (200, 128, 100)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        state = hass.states.get("light.ledblue_ccddeeff")
        assert state.state == STATE_OFF
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
            ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
        }

        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(True, (175, 150, 220)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        state = hass.states.get("light.ledblue_ccddeeff")
        assert state.state == STATE_ON
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
            ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
            ATTR_BRIGHTNESS: 220,
            ATTR_HS_COLOR: (261.429, 31.818),
            ATTR_RGB_COLOR: (202, 173, 255),
            ATTR_XY_COLOR: (0.291, 0.232),
        }
