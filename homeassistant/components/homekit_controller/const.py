"""Constants for the homekit_controller component."""
DOMAIN = "homekit_controller"

KNOWN_DEVICES = f"{DOMAIN}-devices"
CONTROLLER = f"{DOMAIN}-controller"
ENTITY_MAP = f"{DOMAIN}-entity-map"

HOMEKIT_DIR = ".homekit"
PAIRING_FILE = "pairing.json"

# Mapping from Homekit type to component.
HOMEKIT_ACCESSORY_DISPATCH = {
    "lightbulb": "light",
    "outlet": "switch",
    "switch": "switch",
    "thermostat": "climate",
    "security-system": "alarm_control_panel",
    "garage-door-opener": "cover",
    "window": "cover",
    "window-covering": "cover",
    "lock-mechanism": "lock",
    "contact": "binary_sensor",
    "motion": "binary_sensor",
    "carbon-dioxide": "sensor",
    "humidity": "sensor",
    "light": "sensor",
    "temperature": "sensor",
    "battery": "sensor",
    "smoke": "binary_sensor",
    "leak": "binary_sensor",
    "fan": "fan",
    "fanv2": "fan",
    "air-quality": "air_quality",
    "occupancy": "binary_sensor",
    "television": "media_player",
    "valve": "switch",
}
