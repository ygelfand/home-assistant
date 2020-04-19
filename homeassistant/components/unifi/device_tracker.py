"""Track devices using UniFi controllers."""
import logging

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.components.unifi.config_flow import get_controller_from_config_entry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

from .const import ATTR_MANUFACTURER
from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)

CLIENT_CONNECTED_ATTRIBUTES = [
    "_is_guest_by_uap",
    "ap_mac",
    "authorized",
    "essid",
    "ip",
    "is_11r",
    "is_guest",
    "noted",
    "qos_policy_applied",
    "radio",
    "radio_proto",
    "vlan",
]

CLIENT_STATIC_ATTRIBUTES = [
    "hostname",
    "mac",
    "name",
    "oui",
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for UniFi component."""
    controller = get_controller_from_config_entry(hass, config_entry)
    tracked = {}

    option_track_clients = controller.option_track_clients
    option_track_devices = controller.option_track_devices
    option_track_wired_clients = controller.option_track_wired_clients
    option_ssid_filter = controller.option_ssid_filter

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Restore clients that is not a part of active clients list.
    for entity in entity_registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER_DOMAIN
            and "-" in entity.unique_id
        ):

            mac, _ = entity.unique_id.split("-", 1)

            if mac in controller.api.clients or mac not in controller.api.clients_all:
                continue

            client = controller.api.clients_all[mac]
            controller.api.clients.process_raw([client.raw])
            LOGGER.debug(
                "Restore disconnected client %s (%s)", entity.entity_id, client.mac,
            )

    @callback
    def items_added():
        """Update the values of the controller."""
        nonlocal option_track_clients
        nonlocal option_track_devices

        if not option_track_clients and not option_track_devices:
            return

        add_entities(controller, async_add_entities, tracked)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_update, items_added)
    )

    @callback
    def items_removed(mac_addresses: set) -> None:
        """Items have been removed from the controller."""
        remove_entities(controller, mac_addresses, tracked, entity_registry)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_remove, items_removed)
    )

    @callback
    def options_updated():
        """Manage entities affected by config entry options."""
        nonlocal option_track_clients
        nonlocal option_track_devices
        nonlocal option_track_wired_clients
        nonlocal option_ssid_filter

        update = False
        remove = set()

        for current_option, config_entry_option, tracker_class in (
            (option_track_clients, controller.option_track_clients, UniFiClientTracker),
            (option_track_devices, controller.option_track_devices, UniFiDeviceTracker),
        ):
            if current_option == config_entry_option:
                continue

            if config_entry_option:
                update = True
            else:
                for mac, entity in tracked.items():
                    if isinstance(entity, tracker_class):
                        remove.add(mac)

        if (
            controller.option_track_clients
            and option_track_wired_clients != controller.option_track_wired_clients
        ):

            if controller.option_track_wired_clients:
                update = True
            else:
                for mac, entity in tracked.items():
                    if isinstance(entity, UniFiClientTracker) and entity.is_wired:
                        remove.add(mac)

        if option_ssid_filter != controller.option_ssid_filter:
            update = True

            if controller.option_ssid_filter:
                for mac, entity in tracked.items():
                    if (
                        isinstance(entity, UniFiClientTracker)
                        and not entity.is_wired
                        and entity.client.essid not in controller.option_ssid_filter
                    ):
                        remove.add(mac)

        option_track_clients = controller.option_track_clients
        option_track_devices = controller.option_track_devices
        option_track_wired_clients = controller.option_track_wired_clients
        option_ssid_filter = controller.option_ssid_filter

        remove_entities(controller, remove, tracked, entity_registry)

        if update:
            items_added()

    controller.listeners.append(
        async_dispatcher_connect(
            hass, controller.signal_options_update, options_updated
        )
    )

    items_added()


@callback
def add_entities(controller, async_add_entities, tracked):
    """Add new tracker entities from the controller."""
    new_tracked = []

    for items, tracker_class, track in (
        (controller.api.clients, UniFiClientTracker, controller.option_track_clients),
        (controller.api.devices, UniFiDeviceTracker, controller.option_track_devices),
    ):
        if not track:
            continue

        for item_id in items:

            if item_id in tracked:
                continue

            if tracker_class is UniFiClientTracker:
                client = items[item_id]

                if not controller.option_track_wired_clients and client.is_wired:
                    continue

                if (
                    controller.option_ssid_filter
                    and not client.is_wired
                    and client.essid not in controller.option_ssid_filter
                ):
                    continue

            tracked[item_id] = tracker_class(items[item_id], controller)
            new_tracked.append(tracked[item_id])

    if new_tracked:
        async_add_entities(new_tracked)


@callback
def remove_entities(controller, mac_addresses, tracked, entity_registry):
    """Remove select tracked entities."""
    for mac in mac_addresses:

        if mac not in tracked:
            continue

        entity = tracked.pop(mac)
        controller.hass.async_create_task(entity.async_remove())


class UniFiClientTracker(UniFiClient, ScannerEntity):
    """Representation of a network client."""

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self.cancel_scheduled_update = None
        self.is_disconnected = None
        self.wired_bug = None
        if self.is_wired != self.client.is_wired:
            self.wired_bug = dt_util.utcnow() - self.controller.option_detection_time

    @property
    def is_connected(self):
        """Return true if the client is connected to the network.

        If connected to unwanted ssid return False.
        If is_wired and client.is_wired differ it means that the device is offline and UniFi bug shows device as wired.
        """

        @callback
        def _scheduled_update(now):
            """Scheduled callback for update."""
            self.is_disconnected = True
            self.cancel_scheduled_update = None
            self.async_write_ha_state()

        if (
            not self.is_wired
            and self.controller.option_ssid_filter
            and self.client.essid not in self.controller.option_ssid_filter
        ):
            return False

        if (self.is_wired and self.wired_connection) or (
            not self.is_wired and self.wireless_connection
        ):
            if self.cancel_scheduled_update:
                self.cancel_scheduled_update()
                self.cancel_scheduled_update = None

            self.is_disconnected = False

        if (self.is_wired and self.wired_connection is False) or (
            not self.is_wired and self.wireless_connection is False
        ):
            if not self.is_disconnected and not self.cancel_scheduled_update:
                self.cancel_scheduled_update = async_track_point_in_utc_time(
                    self.hass,
                    _scheduled_update,
                    dt_util.utcnow() + self.controller.option_detection_time,
                )

        if self.is_disconnected is not None:
            return not self.is_disconnected

        if self.is_wired != self.client.is_wired:
            if not self.wired_bug:
                self.wired_bug = dt_util.utcnow()
            since_last_seen = dt_util.utcnow() - self.wired_bug

        else:
            self.wired_bug = None

            # A client that has never been seen cannot be connected.
            if self.client.last_seen is None:
                return False

            since_last_seen = dt_util.utcnow() - dt_util.utc_from_timestamp(
                float(self.client.last_seen)
            )

        if since_last_seen < self.controller.option_detection_time:
            return True

        return False

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this client."""
        return f"{self.client.mac}-{self.controller.site}"

    @property
    def device_state_attributes(self):
        """Return the client state attributes."""
        attributes = {}

        attributes["is_wired"] = self.is_wired

        for variable in CLIENT_STATIC_ATTRIBUTES + CLIENT_CONNECTED_ATTRIBUTES:
            if variable in self.client.raw:
                if self.is_disconnected and variable in CLIENT_CONNECTED_ATTRIBUTES:
                    continue
                attributes[variable] = self.client.raw[variable]

        return attributes


class UniFiDeviceTracker(ScannerEntity):
    """Representation of a network infrastructure device."""

    def __init__(self, device, controller):
        """Set up tracked device."""
        self.device = device
        self.controller = controller

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        LOGGER.debug("New device %s (%s)", self.entity_id, self.device.mac)
        self.device.register_callback(self.async_update_callback)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_reachable, self.async_update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self.device.remove_callback(self.async_update_callback)

    @callback
    def async_update_callback(self):
        """Update the sensor's state."""
        LOGGER.debug("Updating device %s (%s)", self.entity_id, self.device.mac)

        self.async_write_ha_state()

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        if self.device.state == 1 and (
            dt_util.utcnow() - dt_util.utc_from_timestamp(float(self.device.last_seen))
            < self.controller.option_detection_time
        ):
            return True

        return False

    @property
    def source_type(self):
        """Return the source type of the device."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.name or self.device.model

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.device.mac

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return not self.device.disabled and self.controller.available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.device.mac)},
            "manufacturer": ATTR_MANUFACTURER,
            "model": self.device.model,
            "sw_version": self.device.version,
        }

        if self.device.name:
            info["name"] = self.device.name

        return info

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.device.state == 0:
            return {}

        attributes = {}

        if self.device.has_fan:
            attributes["fan_level"] = self.device.fan_level

        if self.device.overheating:
            attributes["overheating"] = self.device.overheating

        if self.device.upgradable:
            attributes["upgradable"] = self.device.upgradable

        return attributes

    @property
    def should_poll(self):
        """No polling needed."""
        return True
