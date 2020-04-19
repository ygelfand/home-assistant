"""Support for bandwidth sensors with UniFi clients."""
import logging

from homeassistant.components.unifi.config_flow import get_controller_from_config_entry
from homeassistant.const import DATA_MEGABYTES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Sensor platform doesn't support configuration through configuration.yaml."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for UniFi integration."""
    controller = get_controller_from_config_entry(hass, config_entry)
    sensors = {}

    option_allow_bandwidth_sensors = controller.option_allow_bandwidth_sensors

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    @callback
    def items_added():
        """Update the values of the controller."""
        nonlocal option_allow_bandwidth_sensors

        if not option_allow_bandwidth_sensors:
            return

        add_entities(controller, async_add_entities, sensors)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_update, items_added)
    )

    @callback
    def items_removed(mac_addresses: set) -> None:
        """Items have been removed from the controller."""
        remove_entities(controller, mac_addresses, sensors, entity_registry)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_remove, items_removed)
    )

    @callback
    def options_updated():
        """Update the values of the controller."""
        nonlocal option_allow_bandwidth_sensors

        if option_allow_bandwidth_sensors != controller.option_allow_bandwidth_sensors:
            option_allow_bandwidth_sensors = controller.option_allow_bandwidth_sensors

            if option_allow_bandwidth_sensors:
                items_added()

            else:
                for sensor in sensors.values():
                    hass.async_create_task(sensor.async_remove())

                sensors.clear()

    controller.listeners.append(
        async_dispatcher_connect(
            hass, controller.signal_options_update, options_updated
        )
    )

    items_added()


@callback
def add_entities(controller, async_add_entities, sensors):
    """Add new sensor entities from the controller."""
    new_sensors = []

    for client_id in controller.api.clients:
        for direction, sensor_class in (
            ("rx", UniFiRxBandwidthSensor),
            ("tx", UniFiTxBandwidthSensor),
        ):
            item_id = f"{direction}-{client_id}"

            if item_id in sensors:
                continue

            sensors[item_id] = sensor_class(
                controller.api.clients[client_id], controller
            )
            new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors)


@callback
def remove_entities(controller, mac_addresses, sensors, entity_registry):
    """Remove select sensor entities."""
    for mac in mac_addresses:

        for direction in ("rx", "tx"):
            item_id = f"{direction}-{mac}"

            if item_id not in sensors:
                continue

            entity = sensors.pop(item_id)
            controller.hass.async_create_task(entity.async_remove())


class UniFiRxBandwidthSensor(UniFiClient):
    """Receiving bandwidth sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_rx_bytes / 1000000
        return self.client.raw.get("rx_bytes", 0) / 1000000

    @property
    def name(self):
        """Return the name of the client."""
        name = self.client.name or self.client.hostname
        return f"{name} RX"

    @property
    def unique_id(self):
        """Return a unique identifier for this bandwidth sensor."""
        return f"rx-{self.client.mac}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return DATA_MEGABYTES


class UniFiTxBandwidthSensor(UniFiRxBandwidthSensor):
    """Transmitting bandwidth sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_tx_bytes / 1000000
        return self.client.raw.get("tx_bytes", 0) / 1000000

    @property
    def name(self):
        """Return the name of the client."""
        name = self.client.name or self.client.hostname
        return f"{name} TX"

    @property
    def unique_id(self):
        """Return a unique identifier for this bandwidth sensor."""
        return f"tx-{self.client.mac}"
