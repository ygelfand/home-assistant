"""Config flow for Zerproc."""
import logging

import pyzerproc

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    try:
        devices = await hass.async_add_executor_job(pyzerproc.discover)
        return len(devices) > 0
    except pyzerproc.ZerprocException:
        _LOGGER.error("Unable to discover nearby Zerproc devices", exc_info=True)
        return False


config_entry_flow.register_discovery_flow(
    DOMAIN, "Zerproc", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
