"""Vera tests."""
import pyvera as pv

from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock


async def test_scene(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_scene = MagicMock(spec=pv.VeraScene)  # type: pv.VeraScene
    vera_scene.scene_id = 1
    vera_scene.name = "dev1"
    entity_id = "scene.dev1_1"

    await vera_component_factory.configure_component(
        hass=hass, controller_config=new_simple_controller_config(scenes=(vera_scene,)),
    )

    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
