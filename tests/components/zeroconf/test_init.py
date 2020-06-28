"""Test Zeroconf component setup process."""
import pytest
from zeroconf import InterfaceChoice, ServiceInfo, ServiceStateChange

from homeassistant.components import zeroconf
from homeassistant.components.zeroconf import CONF_DEFAULT_INTERFACE
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.generated import zeroconf as zc_gen
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

NON_UTF8_VALUE = b"ABCDEF\x8a"
NON_ASCII_KEY = b"non-ascii-key\x8a"
PROPERTIES = {
    b"macaddress": b"ABCDEF012345",
    b"non-utf8-value": NON_UTF8_VALUE,
    NON_ASCII_KEY: None,
}

HOMEKIT_STATUS_UNPAIRED = b"1"
HOMEKIT_STATUS_PAIRED = b"0"


@pytest.fixture
def mock_zeroconf():
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc:
        yield mock_zc.return_value


def service_update_mock(zeroconf, services, handlers):
    """Call service update handler."""
    for service in services:
        handlers[0](zeroconf, service, f"name.{service}", ServiceStateChange.Added)


def get_service_info_mock(service_type, name):
    """Return service info for get_service_info."""
    return ServiceInfo(
        service_type,
        name,
        addresses=[b"\n\x00\x00\x14"],
        port=80,
        weight=0,
        priority=0,
        server="name.local.",
        properties=PROPERTIES,
    )


def get_homekit_info_mock(model, pairing_status):
    """Return homekit info for get_service_info for an homekit device."""

    def mock_homekit_info(service_type, name):
        return ServiceInfo(
            service_type,
            name,
            addresses=[b"\n\x00\x00\x14"],
            port=80,
            weight=0,
            priority=0,
            server="name.local.",
            properties={b"md": model.encode(), b"sf": pairing_status},
        )

    return mock_homekit_info


async def test_setup(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_service_info_mock
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    expected_flow_calls = 0
    for matching_components in zc_gen.ZEROCONF.values():
        expected_flow_calls += len(matching_components)
    assert len(mock_config_flow.mock_calls) == expected_flow_calls

    # Test instance is set.
    assert "zeroconf" in hass.data
    assert await hass.components.zeroconf.async_get_instance() is mock_zeroconf


async def test_setup_with_default_interface(hass, mock_zeroconf):
    """Test default interface config."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ):
        mock_zeroconf.get_service_info.side_effect = get_service_info_mock
        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {CONF_DEFAULT_INTERFACE: True}}
        )

    assert mock_zeroconf.called_with(interface_choice=InterfaceChoice.Default)


async def test_setup_without_default_interface(hass, mock_zeroconf):
    """Test without default interface config."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ):
        mock_zeroconf.get_service_info.side_effect = get_service_info_mock
        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {CONF_DEFAULT_INTERFACE: False}}
        )

    assert mock_zeroconf.called_with()


async def test_homekit_match_partial_space(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock(
            "LIFX bulb", HOMEKIT_STATUS_UNPAIRED
        )
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "lifx"


async def test_homekit_match_partial_dash(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock(
            "Rachio-fa46ba", HOMEKIT_STATUS_UNPAIRED
        )
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "rachio"


async def test_homekit_match_full(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock(
            "BSB002", HOMEKIT_STATUS_UNPAIRED
        )
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    homekit_mock = get_homekit_info_mock("BSB002", HOMEKIT_STATUS_UNPAIRED)
    info = homekit_mock("_hap._tcp.local.", "BSB002._hap._tcp.local.")
    import pprint

    pprint.pprint(["homekit", info])
    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "hue"


async def test_homekit_already_paired(hass, mock_zeroconf):
    """Test that an already paired device is sent to homekit_controller."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock(
            "tado", HOMEKIT_STATUS_PAIRED
        )
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "tado"
    assert mock_config_flow.mock_calls[1][1][0] == "homekit_controller"


async def test_homekit_invalid_paring_status(hass, mock_zeroconf):
    """Test that missing paring data is not sent to homekit_controller."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock(
            "tado", b"invalid"
        )
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "tado"


async def test_info_from_service_non_utf8(hass):
    """Test info_from_service handles non UTF-8 property keys and values correctly."""
    service_type = "_test._tcp.local."
    info = zeroconf.info_from_service(
        get_service_info_mock(service_type, f"test.{service_type}")
    )
    raw_info = info["properties"].pop("_raw", False)
    assert raw_info
    assert len(raw_info) == len(PROPERTIES) - 1
    assert NON_ASCII_KEY not in raw_info
    assert len(info["properties"]) <= len(raw_info)
    assert "non-utf8-value" not in info["properties"]
    assert raw_info["non-utf8-value"] is NON_UTF8_VALUE


async def test_get_instance(hass, mock_zeroconf):
    """Test we get an instance."""
    assert await hass.components.zeroconf.async_get_instance() is mock_zeroconf
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_zeroconf.ha_close.mock_calls) == 1
