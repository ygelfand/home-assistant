"""Generic device for the HomematicIP Cloud component."""
import logging
from typing import Any, Dict, Optional

from homematicip.aio.device import AsyncDevice
from homematicip.aio.group import AsyncGroup

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as HMIPC_DOMAIN
from .hap import HomematicipHAP

_LOGGER = logging.getLogger(__name__)

ATTR_MODEL_TYPE = "model_type"
ATTR_LOW_BATTERY = "low_battery"
ATTR_CONFIG_PENDING = "config_pending"
ATTR_DUTY_CYCLE_REACHED = "duty_cycle_reached"
ATTR_ID = "id"
ATTR_IS_GROUP = "is_group"
# RSSI HAP -> Device
ATTR_RSSI_DEVICE = "rssi_device"
# RSSI Device -> HAP
ATTR_RSSI_PEER = "rssi_peer"
ATTR_SABOTAGE = "sabotage"
ATTR_GROUP_MEMBER_UNREACHABLE = "group_member_unreachable"
ATTR_DEVICE_OVERHEATED = "device_overheated"
ATTR_DEVICE_OVERLOADED = "device_overloaded"
ATTR_DEVICE_UNTERVOLTAGE = "device_undervoltage"
ATTR_EVENT_DELAY = "event_delay"

DEVICE_ATTRIBUTE_ICONS = {
    "lowBat": "mdi:battery-outline",
    "sabotage": "mdi:shield-alert",
    "dutyCycle": "mdi:alert",
    "deviceOverheated": "mdi:alert",
    "deviceOverloaded": "mdi:alert",
    "deviceUndervoltage": "mdi:alert",
    "configPending": "mdi:alert-circle",
}

DEVICE_ATTRIBUTES = {
    "modelType": ATTR_MODEL_TYPE,
    "sabotage": ATTR_SABOTAGE,
    "dutyCycle": ATTR_DUTY_CYCLE_REACHED,
    "rssiDeviceValue": ATTR_RSSI_DEVICE,
    "rssiPeerValue": ATTR_RSSI_PEER,
    "deviceOverheated": ATTR_DEVICE_OVERHEATED,
    "deviceOverloaded": ATTR_DEVICE_OVERLOADED,
    "deviceUndervoltage": ATTR_DEVICE_UNTERVOLTAGE,
    "configPending": ATTR_CONFIG_PENDING,
    "eventDelay": ATTR_EVENT_DELAY,
    "id": ATTR_ID,
}

GROUP_ATTRIBUTES = {
    "modelType": ATTR_MODEL_TYPE,
    "lowBat": ATTR_LOW_BATTERY,
    "sabotage": ATTR_SABOTAGE,
    "dutyCycle": ATTR_DUTY_CYCLE_REACHED,
    "configPending": ATTR_CONFIG_PENDING,
    "unreach": ATTR_GROUP_MEMBER_UNREACHABLE,
}


class HomematicipGenericDevice(Entity):
    """Representation of an HomematicIP generic device."""

    def __init__(self, hap: HomematicipHAP, device, post: Optional[str] = None) -> None:
        """Initialize the generic device."""
        self._hap = hap
        self._home = hap.home
        self._device = device
        self.post = post
        # Marker showing that the HmIP device hase been removed.
        self.hmip_device_removed = False
        _LOGGER.info("Setting up %s (%s)", self.name, self._device.modelType)

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device specific attributes."""
        # Only physical devices should be HA devices.
        if isinstance(self._device, AsyncDevice):
            return {
                "identifiers": {
                    # Serial numbers of Homematic IP device
                    (HMIPC_DOMAIN, self._device.id)
                },
                "name": self._device.label,
                "manufacturer": self._device.oem,
                "model": self._device.modelType,
                "sw_version": self._device.firmwareVersion,
                "via_device": (HMIPC_DOMAIN, self._device.homeId),
            }
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hap.hmip_device_by_entity_id[self.entity_id] = self._device
        self._device.on_update(self._async_device_changed)
        self._device.on_remove(self._async_device_removed)

    @callback
    def _async_device_changed(self, *args, **kwargs) -> None:
        """Handle device state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Event %s (%s)", self.name, self._device.modelType)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device Changed Event for %s (%s) not fired. Entity is disabled.",
                self.name,
                self._device.modelType,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""

        # Only go further if the device/entity should be removed from registries
        # due to a removal of the HmIP device.

        if self.hmip_device_removed:
            try:
                del self._hap.hmip_device_by_entity_id[self.entity_id]
                await self.async_remove_from_registries()
            except KeyError as err:
                _LOGGER.debug("Error removing HMIP entity from registry: %s", err)

    async def async_remove_from_registries(self) -> None:
        """Remove entity/device from registry."""

        # Remove callback from device.
        self._device.remove_callback(self._async_device_changed)
        self._device.remove_callback(self._async_device_removed)

        if not self.registry_entry:
            return

        device_id = self.registry_entry.device_id
        if device_id:
            # Remove from device registry.
            device_registry = await dr.async_get_registry(self.hass)
            if device_id in device_registry.devices:
                # This will also remove associated entities from entity registry.
                device_registry.async_remove_device(device_id)
        else:
            # Remove from entity registry.
            # Only relevant for entities that do not belong to a device.
            entity_id = self.registry_entry.entity_id
            if entity_id:
                entity_registry = await er.async_get_registry(self.hass)
                if entity_id in entity_registry.entities:
                    entity_registry.async_remove(entity_id)

    @callback
    def _async_device_removed(self, *args, **kwargs) -> None:
        """Handle hmip device removal."""
        # Set marker showing that the HmIP device hase been removed.
        self.hmip_device_removed = True
        self.hass.async_create_task(self.async_remove())

    @property
    def name(self) -> str:
        """Return the name of the generic device."""
        name = self._device.label
        if name and self._home.name:
            name = f"{self._home.name} {name}"
        if name and self.post:
            name = f"{name} {self.post}"
        return name

    def _get_label_by_channel(self, channel: int) -> str:
        """Return the name of the channel."""
        name = self._device.functionalChannels[channel].label
        if name and self._home.name:
            name = f"{self._home.name} {name}"
        return name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Device available."""
        return not self._device.unreach

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.__class__.__name__}_{self._device.id}"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon."""
        for attr, icon in DEVICE_ATTRIBUTE_ICONS.items():
            if getattr(self._device, attr, None):
                return icon

        return None

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the generic device."""
        state_attr = {}

        if isinstance(self._device, AsyncDevice):
            for attr, attr_key in DEVICE_ATTRIBUTES.items():
                attr_value = getattr(self._device, attr, None)
                if attr_value:
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = False

        if isinstance(self._device, AsyncGroup):
            for attr, attr_key in GROUP_ATTRIBUTES.items():
                attr_value = getattr(self._device, attr, None)
                if attr_value:
                    state_attr[attr_key] = attr_value

            state_attr[ATTR_IS_GROUP] = True

        return state_attr
