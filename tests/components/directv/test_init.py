"""Tests for the DirecTV integration."""
from homeassistant.components.directv.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.components.directv import MOCK_CONFIG, mock_connection, setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker

# pylint: disable=redefined-outer-name


async def test_setup(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the DirecTV setup from configuration."""
    mock_connection(aioclient_mock)
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)


async def test_config_entry_not_ready(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the DirecTV configuration entry not ready."""
    entry = await setup_integration(hass, aioclient_mock, setup_error=True)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the DirecTV configuration entry unloading."""
    entry = await setup_integration(hass, aioclient_mock)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_NOT_LOADED
