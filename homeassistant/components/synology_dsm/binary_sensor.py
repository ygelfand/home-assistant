"""Support for Synology DSM binary sensors."""
from typing import Dict

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISKS
from homeassistant.helpers.typing import HomeAssistantType

from . import SynologyDSMDeviceEntity, SynologyDSMEntity
from .const import (
    DOMAIN,
    SECURITY_BINARY_SENSORS,
    STORAGE_DISK_BINARY_SENSORS,
    SYNO_API,
)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS binary sensor."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    entities = [
        SynoDSMSecurityBinarySensor(
            api, sensor_type, SECURITY_BINARY_SENSORS[sensor_type]
        )
        for sensor_type in SECURITY_BINARY_SENSORS
    ]

    # Handle all disks
    if api.storage.disks_ids:
        for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids):
            entities += [
                SynoDSMStorageBinarySensor(
                    api, sensor_type, STORAGE_DISK_BINARY_SENSORS[sensor_type], disk
                )
                for sensor_type in STORAGE_DISK_BINARY_SENSORS
            ]

    async_add_entities(entities)


class SynoDSMSecurityBinarySensor(SynologyDSMEntity, BinarySensorEntity):
    """Representation a Synology Security binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return getattr(self._api.security, self.entity_type) != "safe"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.security)

    @property
    def device_state_attributes(self) -> Dict[str, str]:
        """Return security checks details."""
        return self._api.security.status_by_check


class SynoDSMStorageBinarySensor(SynologyDSMDeviceEntity, BinarySensorEntity):
    """Representation a Synology Storage binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the state."""
        attr = getattr(self._api.storage, self.entity_type)(self._device_id)
        if attr is None:
            return None
        return attr
