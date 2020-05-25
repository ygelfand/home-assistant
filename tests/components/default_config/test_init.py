"""Test the default_config init."""
import pytest

from homeassistant.setup import async_setup_component

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def recorder_url_mock():
    """Mock recorder url."""
    with patch("homeassistant.components.recorder.DEFAULT_URL", "sqlite://"):
        yield


async def test_setup(hass):
    """Test setup."""
    assert await async_setup_component(hass, "default_config", {"foo": "bar"})
