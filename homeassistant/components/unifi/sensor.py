"""Support for bandwidth sensors with UniFi clients."""
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import DATA_MEGABYTES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as UNIFI_DOMAIN
from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)

RX_SENSOR = "rx"
TX_SENSOR = "tx"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Sensor platform doesn't support configuration through configuration.yaml."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for UniFi integration."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {RX_SENSOR: set(), TX_SENSOR: set()}

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Update the values of the controller."""
        if controller.option_allow_bandwidth_sensors:
            add_entities(controller, async_add_entities, clients)

    for signal in (controller.signal_update, controller.signal_options_update):
        controller.listeners.append(async_dispatcher_connect(hass, signal, items_added))

    items_added()


@callback
def add_entities(controller, async_add_entities, clients):
    """Add new sensor entities from the controller."""
    sensors = []

    for mac in clients:
        for sensor_class in (UniFiRxBandwidthSensor, UniFiTxBandwidthSensor):
            if mac in controller.entities[DOMAIN][sensor_class.TYPE]:
                continue

            client = controller.api.clients[mac]
            sensors.append(sensor_class(client, controller))

    if sensors:
        async_add_entities(sensors)


class UniFiBandwidthSensor(UniFiClient):
    """UniFi bandwidth sensor base class."""

    DOMAIN = DOMAIN

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.upper()}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return DATA_MEGABYTES

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_bandwidth_sensors:
            await self.remove_item({self.client.mac})


class UniFiRxBandwidthSensor(UniFiBandwidthSensor):
    """Receiving bandwidth sensor."""

    TYPE = RX_SENSOR

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_rx_bytes / 1000000
        return self.client.rx_bytes / 1000000


class UniFiTxBandwidthSensor(UniFiBandwidthSensor):
    """Transmitting bandwidth sensor."""

    TYPE = TX_SENSOR

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_tx_bytes / 1000000
        return self.client.tx_bytes / 1000000
