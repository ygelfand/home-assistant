"""The Internet Printing Protocol (IPP) integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from pyipp import IPP, IPPError, Printer as IPPPrinter

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    CONF_BASE_PATH,
    DOMAIN,
)

PLATFORMS = [SENSOR_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the IPP component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IPP from a config entry."""

    # Create IPP instance for this entry
    coordinator = IPPDataUpdateCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        base_path=entry.data[CONF_BASE_PATH],
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class IPPDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching IPP data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        base_path: str,
        tls: bool,
        verify_ssl: bool,
    ):
        """Initialize global IPP data updater."""
        self.ipp = IPP(
            host=host,
            port=port,
            base_path=base_path,
            tls=tls,
            verify_ssl=verify_ssl,
            session=async_get_clientsession(hass, verify_ssl),
        )

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> IPPPrinter:
        """Fetch data from IPP."""
        try:
            return await self.ipp.printer()
        except IPPError as error:
            raise UpdateFailed(f"Invalid response from API: {error}")


class IPPEntity(Entity):
    """Defines a base IPP entity."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: IPPDataUpdateCoordinator,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the IPP entity."""
        self._device_id = None
        self._enabled_default = enabled_default
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self.coordinator = coordinator

        if coordinator.data.info.uuid is not None:
            self._device_id = coordinator.data.info.uuid
        elif coordinator.data.info.serial is not None:
            self._device_id = coordinator.data.info.serial

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update an IPP entity."""
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this IPP device."""
        if self._device_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: self.coordinator.data.info.name,
            ATTR_MANUFACTURER: self.coordinator.data.info.manufacturer,
            ATTR_MODEL: self.coordinator.data.info.model,
            ATTR_SOFTWARE_VERSION: self.coordinator.data.info.version,
        }
