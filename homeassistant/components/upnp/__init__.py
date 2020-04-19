"""Open ports in your router for Home Assistant and provide statistics."""
from ipaddress import ip_address
from operator import itemgetter
from typing import Mapping

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import get_local_ip

from .const import (
    CONF_ENABLE_PORT_MAPPING,
    CONF_ENABLE_SENSORS,
    CONF_HASS,
    CONF_LOCAL_IP,
    CONF_PORTS,
    DOMAIN,
    LOGGER as _LOGGER,
)
from .device import Device

NOTIFICATION_ID = "upnp_notification"
NOTIFICATION_TITLE = "UPnP/IGD Setup"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ENABLE_PORT_MAPPING, default=False): cv.boolean,
                vol.Optional(CONF_ENABLE_SENSORS, default=True): cv.boolean,
                vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string),
                vol.Optional(CONF_PORTS, default={}): vol.Schema(
                    {vol.Any(CONF_HASS, cv.port): vol.Any(CONF_HASS, cv.port)}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _substitute_hass_ports(ports: Mapping, hass_port: int = None) -> Mapping:
    """
    Substitute 'hass' for the hass_port.

    This triggers a warning when hass_port is None.
    """
    ports = ports.copy()

    # substitute 'hass' for hass_port, both keys and values
    if CONF_HASS in ports:
        if hass_port is None:
            _LOGGER.warning(
                "Could not determine Home Assistant http port, "
                "not setting up port mapping from %s to %s. "
                "Enable the http-component.",
                CONF_HASS,
                ports[CONF_HASS],
            )
        else:
            ports[hass_port] = ports[CONF_HASS]
        del ports[CONF_HASS]

    for port in ports:
        if ports[port] == CONF_HASS:
            if hass_port is None:
                _LOGGER.warning(
                    "Could not determine Home Assistant http port, "
                    "not setting up port mapping from %s to %s. "
                    "Enable the http-component.",
                    port,
                    ports[port],
                )
                del ports[port]
            else:
                ports[port] = hass_port

    return ports


async def async_discover_and_construct(
    hass: HomeAssistantType, udn: str = None, st: str = None
) -> Device:
    """Discovery devices and construct a Device for one."""
    # pylint: disable=invalid-name
    discovery_infos = await Device.async_discover(hass)
    if not discovery_infos:
        _LOGGER.info("No UPnP/IGD devices discovered")
        return None

    if udn:
        # get the discovery info with specified UDN
        _LOGGER.debug("Discovery_infos: %s", discovery_infos)
        filtered = [di for di in discovery_infos if di["udn"] == udn]
        if st:
            _LOGGER.debug("Filtering on ST: %s", st)
            filtered = [di for di in discovery_infos if di["st"] == st]
        if not filtered:
            _LOGGER.warning(
                'Wanted UPnP/IGD device with UDN "%s" not found, ' "aborting", udn
            )
            return None
        # ensure we're always taking the latest
        filtered = sorted(filtered, key=itemgetter("st"), reverse=True)
        discovery_info = filtered[0]
    else:
        # get the first/any
        discovery_info = discovery_infos[0]
        if len(discovery_infos) > 1:
            device_name = discovery_info.get(
                "usn", discovery_info.get("ssdp_description", "")
            )
            _LOGGER.info("Detected multiple UPnP/IGD devices, using: %s", device_name)

    ssdp_description = discovery_info["ssdp_description"]
    return await Device.async_create_device(hass, ssdp_description)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up UPnP component."""
    conf_default = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
    conf = config.get(DOMAIN, conf_default)
    local_ip = await hass.async_add_executor_job(get_local_ip)
    hass.data[DOMAIN] = {
        "config": conf,
        "devices": {},
        "local_ip": conf.get(CONF_LOCAL_IP, local_ip),
        "ports": conf.get(CONF_PORTS),
    }

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up UPnP/IGD device from a config entry."""
    domain_data = hass.data[DOMAIN]
    conf = domain_data["config"]

    # discover and construct
    udn = config_entry.data.get("udn")
    st = config_entry.data.get("st")  # pylint: disable=invalid-name
    device = await async_discover_and_construct(hass, udn, st)
    if not device:
        _LOGGER.info("Unable to create UPnP/IGD, aborting")
        raise ConfigEntryNotReady

    # 'register'/save UDN + ST
    hass.data[DOMAIN]["devices"][device.udn] = device
    hass.config_entries.async_update_entry(
        entry=config_entry,
        data={**config_entry.data, "udn": device.udn, "st": device.device_type},
    )

    # create device registry entry
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_UPNP, device.udn)},
        identifiers={(DOMAIN, device.udn)},
        name=device.name,
        manufacturer=device.manufacturer,
        model=device.model_name,
    )

    # set up sensors
    if conf.get(CONF_ENABLE_SENSORS):
        _LOGGER.debug("Enabling sensors")

        # register sensor setup handlers
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
        )

    # set up port mapping
    if conf.get(CONF_ENABLE_PORT_MAPPING):
        _LOGGER.debug("Enabling port mapping")
        local_ip = domain_data[CONF_LOCAL_IP]
        ports = conf.get(CONF_PORTS, {})

        hass_port = None
        if hasattr(hass, "http"):
            hass_port = hass.http.server_port

        ports = _substitute_hass_ports(ports, hass_port=hass_port)
        await device.async_add_port_mappings(ports, local_ip)

    # set up port mapping deletion on stop-hook
    async def delete_port_mapping(event):
        """Delete port mapping on quit."""
        _LOGGER.debug("Deleting port mappings")
        await device.async_delete_port_mappings()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, delete_port_mapping)

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload a UPnP/IGD device from a config entry."""
    udn = config_entry.data["udn"]
    device = hass.data[DOMAIN]["devices"][udn]

    # remove port mapping
    _LOGGER.debug("Deleting port mappings")
    await device.async_delete_port_mappings()

    # remove sensors
    _LOGGER.debug("Deleting sensors")
    return await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
