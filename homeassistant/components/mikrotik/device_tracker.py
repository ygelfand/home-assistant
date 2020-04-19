"""Support for Mikrotik routers as device tracker."""
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from .const import ATTR_MANUFACTURER, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Mikrotik component."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    tracked = {}

    registry = await entity_registry.async_get_registry(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER
        ):

            if (
                entity.unique_id in hub.api.devices
                or entity.unique_id not in hub.api.all_devices
            ):
                continue
            hub.api.restore_device(entity.unique_id)

    @callback
    def update_hub():
        """Update the status of the device."""
        update_items(hub, async_add_entities, tracked)

    async_dispatcher_connect(hass, hub.signal_update, update_hub)

    update_hub()


@callback
def update_items(hub, async_add_entities, tracked):
    """Update tracked device state from the hub."""
    new_tracked = []
    for mac, device in hub.api.devices.items():
        if mac not in tracked:
            tracked[mac] = MikrotikHubTracker(device, hub)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikHubTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, device, hub):
        """Initialize the tracked device."""
        self.device = device
        self.hub = hub
        self.unsub_dispatcher = None

    @property
    def is_connected(self):
        """Return true if the client is connected to the network."""
        if (
            self.device.last_seen
            and (dt_util.utcnow() - self.device.last_seen)
            < self.hub.option_detection_time
        ):
            return True
        return False

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return self.device.name

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.device.mac

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.hub.available

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.is_connected:
            return self.device.attrs
        return None

    @property
    def device_info(self):
        """Return a client description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.device.mac)},
            "manufacturer": ATTR_MANUFACTURER,
            "identifiers": {(DOMAIN, self.device.mac)},
            "name": self.name,
            "via_device": (DOMAIN, self.hub.serial_num),
        }
        return info

    async def async_added_to_hass(self):
        """Client entity created."""
        _LOGGER.debug("New network device tracker %s (%s)", self.name, self.unique_id)
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, self.hub.signal_update, self.async_write_ha_state
        )

    async def async_update(self):
        """Synchronize state with hub."""
        _LOGGER.debug(
            "Updating Mikrotik tracked client %s (%s)", self.entity_id, self.unique_id
        )
        await self.hub.request_update()

    async def will_remove_from_hass(self):
        """Disconnect from dispatcher."""
        if self.unsub_dispatcher:
            self.unsub_dispatcher()
