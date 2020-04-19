"""The tests for Cover device actions."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.cover import DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a cover."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[0]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "open",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
        {
            "domain": DOMAIN,
            "type": "close",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_actions_tilt(hass, device_reg, entity_reg):
    """Test we get the expected actions from a cover."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[3]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "open",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
        {
            "domain": DOMAIN,
            "type": "close",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
        {
            "domain": DOMAIN,
            "type": "open_tilt",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
        {
            "domain": DOMAIN,
            "type": "close_tilt",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_actions_set_pos(hass, device_reg, entity_reg):
    """Test we get the expected actions from a cover."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[1]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "set_position",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_actions_set_tilt_pos(hass, device_reg, entity_reg):
    """Test we get the expected actions from a cover."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[2]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "open",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
        {
            "domain": DOMAIN,
            "type": "close",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
        {
            "domain": DOMAIN,
            "type": "set_tilt_position",
            "device_id": device_entry.id,
            "entity_id": ent.entity_id,
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_action_capabilities(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a cover action."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[0]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 2  # open, close
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        assert capabilities == {"extra_fields": []}


async def test_get_action_capabilities_set_pos(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a cover action."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[1]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_capabilities = {
        "extra_fields": [
            {
                "name": "position",
                "optional": True,
                "type": "integer",
                "default": 0,
                "valueMax": 100,
                "valueMin": 0,
            }
        ]
    }
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 1  # set_position
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        if action["type"] == "set_position":
            assert capabilities == expected_capabilities
        else:
            assert capabilities == {"extra_fields": []}


async def test_get_action_capabilities_set_tilt_pos(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a cover action."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[2]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    expected_capabilities = {
        "extra_fields": [
            {
                "name": "position",
                "optional": True,
                "type": "integer",
                "default": 0,
                "valueMax": 100,
                "valueMin": 0,
            }
        ]
    }
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 3  # open, close, set_tilt_position
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        if action["type"] == "set_tilt_position":
            assert capabilities == expected_capabilities
        else:
            assert capabilities == {"extra_fields": []}


async def test_action(hass):
    """Test for cover actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event_open"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "open",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_close"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "close",
                    },
                },
            ]
        },
    )

    open_calls = async_mock_service(hass, "cover", "open_cover")
    close_calls = async_mock_service(hass, "cover", "close_cover")

    hass.bus.async_fire("test_event_open")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 0

    hass.bus.async_fire("test_event_close")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1

    hass.bus.async_fire("test_event_stop")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1


async def test_action_tilt(hass):
    """Test for cover tilt actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event_open"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "open_tilt",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_close"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "close_tilt",
                    },
                },
            ]
        },
    )

    open_calls = async_mock_service(hass, "cover", "open_cover_tilt")
    close_calls = async_mock_service(hass, "cover", "close_cover_tilt")

    hass.bus.async_fire("test_event_open")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 0

    hass.bus.async_fire("test_event_close")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1

    hass.bus.async_fire("test_event_stop")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1


async def test_action_set_position(hass):
    """Test for cover set position actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_pos",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "set_position",
                        "position": 25,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_tilt_pos",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "set_tilt_position",
                        "position": 75,
                    },
                },
            ]
        },
    )

    cover_pos_calls = async_mock_service(hass, "cover", "set_cover_position")
    tilt_pos_calls = async_mock_service(hass, "cover", "set_cover_tilt_position")

    hass.bus.async_fire("test_event_set_pos")
    await hass.async_block_till_done()
    assert len(cover_pos_calls) == 1
    assert cover_pos_calls[0].data["position"] == 25
    assert len(tilt_pos_calls) == 0

    hass.bus.async_fire("test_event_set_tilt_pos")
    await hass.async_block_till_done()
    assert len(cover_pos_calls) == 1
    assert len(tilt_pos_calls) == 1
    assert tilt_pos_calls[0].data["tilt_position"] == 75
