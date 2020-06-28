"""Support for Synology DSM sensors."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DISKS,
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.helpers.temperature import display_temp
from homeassistant.helpers.typing import HomeAssistantType

from . import SynologyDSMDeviceEntity, SynologyDSMEntity
from .const import (
    CONF_VOLUMES,
    DOMAIN,
    STORAGE_DISK_SENSORS,
    STORAGE_VOL_SENSORS,
    SYNO_API,
    TEMP_SENSORS_KEYS,
    UTILISATION_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS Sensor."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    entities = [
        SynoDSMUtilSensor(api, sensor_type, UTILISATION_SENSORS[sensor_type])
        for sensor_type in UTILISATION_SENSORS
    ]

    # Handle all volumes
    if api.storage.volumes_ids:
        for volume in entry.data.get(CONF_VOLUMES, api.storage.volumes_ids):
            entities += [
                SynoDSMStorageSensor(
                    api, sensor_type, STORAGE_VOL_SENSORS[sensor_type], volume
                )
                for sensor_type in STORAGE_VOL_SENSORS
            ]

    # Handle all disks
    if api.storage.disks_ids:
        for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids):
            entities += [
                SynoDSMStorageSensor(
                    api, sensor_type, STORAGE_DISK_SENSORS[sensor_type], disk
                )
                for sensor_type in STORAGE_DISK_SENSORS
            ]

    async_add_entities(entities)


class SynoDSMUtilSensor(SynologyDSMEntity):
    """Representation a Synology Utilisation sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.utilisation, self.entity_type)
        if callable(attr):
            attr = attr()
        if attr is None:
            return None

        # Data (RAM)
        if self._unit == DATA_MEGABYTES:
            return round(attr / 1024.0 ** 2, 1)

        # Network
        if self._unit == DATA_RATE_KILOBYTES_PER_SECOND:
            return round(attr / 1024.0, 1)

        return attr

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.utilisation)


class SynoDSMStorageSensor(SynologyDSMDeviceEntity):
    """Representation a Synology Storage sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.storage, self.entity_type)(self._device_id)
        if attr is None:
            return None

        # Data (disk space)
        if self._unit == DATA_TERABYTES:
            return round(attr / 1024.0 ** 4, 2)

        # Temperature
        if self.entity_type in TEMP_SENSORS_KEYS:
            return display_temp(self.hass, attr, TEMP_CELSIUS, PRECISION_TENTHS)

        return attr
