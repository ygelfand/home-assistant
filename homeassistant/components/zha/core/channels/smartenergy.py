"""Smart energy channels module for Zigbee Home Automation."""
import logging

import zigpy.zcl.clusters.smartenergy as smartenergy

from homeassistant.const import LENGTH_FEET, TIME_HOURS, TIME_SECONDS
from homeassistant.core import callback

from .. import registries, typing as zha_typing
from ..const import REPORT_CONFIG_DEFAULT
from .base import ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Calendar.cluster_id)
class Calendar(ZigbeeChannel):
    """Calendar channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.DeviceManagement.cluster_id)
class DeviceManagement(ZigbeeChannel):
    """Device Management channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Drlc.cluster_id)
class Drlc(ZigbeeChannel):
    """Demand Response and Load Control channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.EnergyManagement.cluster_id)
class EnergyManagement(ZigbeeChannel):
    """Energy Management channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Events.cluster_id)
class Events(ZigbeeChannel):
    """Event channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.KeyEstablishment.cluster_id)
class KeyEstablishment(ZigbeeChannel):
    """Key Establishment channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.MduPairing.cluster_id)
class MduPairing(ZigbeeChannel):
    """Pairing channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Messaging.cluster_id)
class Messaging(ZigbeeChannel):
    """Messaging channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Metering.cluster_id)
class Metering(ZigbeeChannel):
    """Metering channel."""

    REPORT_CONFIG = [{"attr": "instantaneous_demand", "config": REPORT_CONFIG_DEFAULT}]

    unit_of_measure_map = {
        0x00: "kW",
        0x01: f"m³/{TIME_HOURS}",
        0x02: f"{LENGTH_FEET}³/{TIME_HOURS}",
        0x03: f"ccf/{TIME_HOURS}",
        0x04: f"US gal/{TIME_HOURS}",
        0x05: f"IMP gal/{TIME_HOURS}",
        0x06: f"BTU/{TIME_HOURS}",
        0x07: f"l/{TIME_HOURS}",
        0x08: "kPa",
        0x09: "kPa",
        0x0A: f"mcf/{TIME_HOURS}",
        0x0B: "unitless",
        0x0C: f"MJ/{TIME_SECONDS}",
    }

    def __init__(
        self, cluster: zha_typing.ZigpyClusterType, ch_pool: zha_typing.ChannelPoolType
    ) -> None:
        """Initialize Metering."""
        super().__init__(cluster, ch_pool)
        self._divisor = 1
        self._multiplier = 1
        self._unit_enum = None
        self._format_spec = None

    async def async_configure(self):
        """Configure channel."""
        await self.fetch_config(False)
        await super().async_configure()

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.fetch_config(True)
        await super().async_initialize(from_cache)

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from Metering cluster."""
        if None in (self._multiplier, self._divisor, self._format_spec):
            return
        super().attribute_updated(attrid, value * self._multiplier / self._divisor)

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return self.unit_of_measure_map.get(self._unit_enum & 0x7F, "unknown")

    async def fetch_config(self, from_cache):
        """Fetch config from device and updates format specifier."""
        results = await self.get_attributes(
            ["divisor", "multiplier", "unit_of_measure", "demand_formatting"],
            from_cache=from_cache,
        )

        self._divisor = results.get("divisor", self._divisor)
        self._multiplier = results.get("multiplier", self._multiplier)
        self._unit_enum = results.get("unit_of_measure", 0x7F)  # default to unknown

        fmting = results.get(
            "demand_formatting", 0xF9
        )  # 1 digit to the right, 15 digits to the left

        r_digits = int(fmting & 0x07)  # digits to the right of decimal point
        l_digits = (fmting >> 3) & 0x0F  # digits to the left of decimal point
        if l_digits == 0:
            l_digits = 15
        width = r_digits + l_digits + (1 if r_digits > 0 else 0)

        if fmting & 0x80:
            self._format_spec = "{:" + str(width) + "." + str(r_digits) + "f}"
        else:
            self._format_spec = "{:0" + str(width) + "." + str(r_digits) + "f}"

    def formatter_function(self, value):
        """Return formatted value for display."""
        return self._format_spec.format(value).lstrip()


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Prepayment.cluster_id)
class Prepayment(ZigbeeChannel):
    """Prepayment channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Price.cluster_id)
class Price(ZigbeeChannel):
    """Price channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Tunneling.cluster_id)
class Tunneling(ZigbeeChannel):
    """Tunneling channel."""
