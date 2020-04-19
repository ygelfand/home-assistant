"""Tests for the Sonos Media Player platform."""
import pytest

from homeassistant.components.sonos import DOMAIN, media_player
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_async_setup_entry_hosts(hass, config_entry, config, soco):
    """Test static setup."""
    await setup_platform(hass, config_entry, config)

    entity = hass.data[media_player.DATA_SONOS].entities[0]
    assert entity.soco == soco


async def test_async_setup_entry_discover(hass, config_entry, discover):
    """Test discovery setup."""
    await setup_platform(hass, config_entry, {})

    entity = hass.data[media_player.DATA_SONOS].entities[0]
    assert entity.unique_id == "RINCON_test"


async def test_services(hass, config_entry, config, hass_read_only_user):
    """Test join/unjoin requires control access."""
    await setup_platform(hass, config_entry, config)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            media_player.SERVICE_JOIN,
            {"master": "media_player.bla", "entity_id": "media_player.blub"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
