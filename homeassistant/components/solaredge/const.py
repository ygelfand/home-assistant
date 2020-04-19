"""Constants for the SolarEdge Monitoring API."""
from datetime import timedelta

from homeassistant.const import ENERGY_WATT_HOUR, POWER_WATT

DOMAIN = "solaredge"

# Config for solaredge monitoring api requests.
CONF_SITE_ID = "site_id"

DEFAULT_NAME = "SolarEdge"

OVERVIEW_UPDATE_DELAY = timedelta(minutes=10)
DETAILS_UPDATE_DELAY = timedelta(hours=12)
INVENTORY_UPDATE_DELAY = timedelta(hours=12)
POWER_FLOW_UPDATE_DELAY = timedelta(minutes=10)

SCAN_INTERVAL = timedelta(minutes=10)

# Supported overview sensor types:
# Key: ['json_key', 'name', unit, icon, default]
SENSOR_TYPES = {
    "lifetime_energy": [
        "lifeTimeData",
        "Lifetime energy",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        False,
    ],
    "energy_this_year": [
        "lastYearData",
        "Energy this year",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        False,
    ],
    "energy_this_month": [
        "lastMonthData",
        "Energy this month",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        False,
    ],
    "energy_today": [
        "lastDayData",
        "Energy today",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        False,
    ],
    "current_power": [
        "currentPower",
        "Current Power",
        POWER_WATT,
        "mdi:solar-power",
        True,
    ],
    "site_details": [None, "Site details", None, None, False],
    "meters": ["meters", "Meters", None, None, False],
    "sensors": ["sensors", "Sensors", None, None, False],
    "gateways": ["gateways", "Gateways", None, None, False],
    "batteries": ["batteries", "Batteries", None, None, False],
    "inverters": ["inverters", "Inverters", None, None, False],
    "power_consumption": ["LOAD", "Power Consumption", None, "mdi:flash", False],
    "solar_power": ["PV", "Solar Power", None, "mdi:solar-power", False],
    "grid_power": ["GRID", "Grid Power", None, "mdi:power-plug", False],
    "storage_power": ["STORAGE", "Storage Power", None, "mdi:car-battery", False],
}
