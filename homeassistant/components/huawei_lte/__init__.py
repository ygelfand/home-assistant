"""Support for Huawei LTE routers."""

from collections import defaultdict
from datetime import timedelta
from functools import partial
from urllib.parse import urlparse
import ipaddress
import logging
from typing import Any, Callable, Dict, List, Set, Tuple

import voluptuous as vol
import attr
from getmac import get_mac_address
from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection
from huawei_lte_api.exceptions import (
    ResponseErrorLoginRequiredException,
    ResponseErrorNotSupportedException,
)
from requests.exceptions import Timeout
from url_normalize import url_normalize

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_URL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
    dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from .const import (
    ALL_KEYS,
    CONNECTION_TIMEOUT,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    KEY_DEVICE_BASIC_INFORMATION,
    KEY_DEVICE_INFORMATION,
    KEY_DEVICE_SIGNAL,
    KEY_DIALUP_MOBILE_DATASWITCH,
    KEY_MONITORING_TRAFFIC_STATISTICS,
    KEY_WLAN_HOST_LIST,
    UPDATE_OPTIONS_SIGNAL,
    UPDATE_SIGNAL,
)


_LOGGER = logging.getLogger(__name__)

# dicttoxml (used by huawei-lte-api) has uselessly verbose INFO level.
# https://github.com/quandyfactory/dicttoxml/issues/60
logging.getLogger("dicttoxml").setLevel(logging.WARNING)

DEFAULT_NAME_TEMPLATE = "Huawei {} {}"

SCAN_INTERVAL = timedelta(seconds=10)

NOTIFY_SCHEMA = vol.Any(
    None,
    vol.Schema(
        {
            vol.Optional(CONF_RECIPIENT): vol.Any(
                None, vol.All(cv.ensure_list, [cv.string])
            )
        }
    ),
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_URL): cv.url,
                        vol.Optional(CONF_USERNAME): cv.string,
                        vol.Optional(CONF_PASSWORD): cv.string,
                        vol.Optional(NOTIFY_DOMAIN): NOTIFY_SCHEMA,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@attr.s
class Router:
    """Class for router state."""

    connection: Connection = attr.ib()
    url: str = attr.ib()
    mac: str = attr.ib()
    signal_update: CALLBACK_TYPE = attr.ib()

    data: Dict[str, Any] = attr.ib(init=False, factory=dict)
    subscriptions: Dict[str, Set[str]] = attr.ib(
        init=False,
        factory=lambda: defaultdict(set, ((x, {"initial_scan"}) for x in ALL_KEYS)),
    )
    unload_handlers: List[CALLBACK_TYPE] = attr.ib(init=False, factory=list)
    client: Client

    def __attrs_post_init__(self):
        """Set up internal state on init."""
        self.client = Client(self.connection)

    @property
    def device_name(self) -> str:
        """Get router device name."""
        for key, item in (
            (KEY_DEVICE_BASIC_INFORMATION, "devicename"),
            (KEY_DEVICE_INFORMATION, "DeviceName"),
        ):
            try:
                return self.data[key][item]
            except (KeyError, TypeError):
                pass
        return DEFAULT_DEVICE_NAME

    @property
    def device_connections(self) -> Set[Tuple[str, str]]:
        """Get router connections for device registry."""
        return {(dr.CONNECTION_NETWORK_MAC, self.mac)}

    def update(self) -> None:
        """Update router data."""

        def get_data(key: str, func: Callable[[None], Any]) -> None:
            if not self.subscriptions[key]:
                return
            _LOGGER.debug("Getting %s for subscribers %s", key, self.subscriptions[key])
            try:
                self.data[key] = func()
            except ResponseErrorNotSupportedException:
                _LOGGER.info(
                    "%s not supported by device, excluding from future updates", key
                )
                self.subscriptions.pop(key)
            except ResponseErrorLoginRequiredException:
                _LOGGER.info(
                    "%s requires authorization, excluding from future updates", key
                )
                self.subscriptions.pop(key)
            finally:
                _LOGGER.debug("%s=%s", key, self.data.get(key))

        get_data(KEY_DEVICE_INFORMATION, self.client.device.information)
        if self.data.get(KEY_DEVICE_INFORMATION):
            # Full information includes everything in basic
            self.subscriptions.pop(KEY_DEVICE_BASIC_INFORMATION, None)
        get_data(KEY_DEVICE_BASIC_INFORMATION, self.client.device.basic_information)
        get_data(KEY_DEVICE_SIGNAL, self.client.device.signal)
        get_data(KEY_DIALUP_MOBILE_DATASWITCH, self.client.dial_up.mobile_dataswitch)
        get_data(
            KEY_MONITORING_TRAFFIC_STATISTICS, self.client.monitoring.traffic_statistics
        )
        get_data(KEY_WLAN_HOST_LIST, self.client.wlan.host_list)

        self.signal_update()

    def cleanup(self, *_) -> None:
        """Clean up resources."""

        self.subscriptions.clear()

        for handler in self.unload_handlers:
            handler()
        self.unload_handlers.clear()

        if not isinstance(self.connection, AuthorizedConnection):
            return
        try:
            self.client.user.logout()
        except ResponseErrorNotSupportedException:
            _LOGGER.debug("Logout not supported by device", exc_info=True)
        except ResponseErrorLoginRequiredException:
            _LOGGER.debug("Logout not supported when not logged in", exc_info=True)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning("Logout error", exc_info=True)


@attr.s
class HuaweiLteData:
    """Shared state."""

    hass_config: dict = attr.ib()
    # Our YAML config, keyed by router URL
    config: Dict[str, Dict[str, Any]] = attr.ib()
    routers: Dict[str, Router] = attr.ib(init=False, factory=dict)


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up Huawei LTE component from config entry."""
    url = config_entry.data[CONF_URL]

    # Override settings from YAML config, but only if they're changed in it
    # Old values are stored as *_from_yaml in the config entry
    yaml_config = hass.data[DOMAIN].config.get(url)
    if yaml_config:
        # Config values
        new_data = {}
        for key in CONF_USERNAME, CONF_PASSWORD:
            if key in yaml_config:
                value = yaml_config[key]
                if value != config_entry.data.get(f"{key}_from_yaml"):
                    new_data[f"{key}_from_yaml"] = value
                    new_data[key] = value
        # Options
        new_options = {}
        yaml_recipient = yaml_config.get(NOTIFY_DOMAIN, {}).get(CONF_RECIPIENT)
        if yaml_recipient is not None and yaml_recipient != config_entry.options.get(
            f"{CONF_RECIPIENT}_from_yaml"
        ):
            new_options[f"{CONF_RECIPIENT}_from_yaml"] = yaml_recipient
            new_options[CONF_RECIPIENT] = yaml_recipient
        # Update entry if overrides were found
        if new_data or new_options:
            hass.config_entries.async_update_entry(
                config_entry,
                data={**config_entry.data, **new_data},
                options={**config_entry.options, **new_options},
            )

    # Get MAC address for use in unique ids. Being able to use something
    # from the API would be nice, but all of that seems to be available only
    # through authenticated calls (e.g. device_information.SerialNumber), and
    # we want this available and the same when unauthenticated too.
    host = urlparse(url).hostname
    try:
        if ipaddress.ip_address(host).version == 6:
            mode = "ip6"
        else:
            mode = "ip"
    except ValueError:
        mode = "hostname"
    mac = await hass.async_add_executor_job(partial(get_mac_address, **{mode: host}))

    def get_connection() -> Connection:
        """
        Set up a connection.

        Authorized one if username/pass specified (even if empty), unauthorized one otherwise.
        """
        username = config_entry.data.get(CONF_USERNAME)
        password = config_entry.data.get(CONF_PASSWORD)
        if username or password:
            connection = AuthorizedConnection(
                url, username=username, password=password, timeout=CONNECTION_TIMEOUT
            )
        else:
            connection = Connection(url, timeout=CONNECTION_TIMEOUT)
        return connection

    def signal_update() -> None:
        """Signal updates to data."""
        dispatcher_send(hass, UPDATE_SIGNAL, url)

    try:
        connection = await hass.async_add_executor_job(get_connection)
    except Timeout as ex:
        raise ConfigEntryNotReady from ex

    # Set up router and store reference to it
    router = Router(connection, url, mac, signal_update)
    hass.data[DOMAIN].routers[url] = router

    # Do initial data update
    await hass.async_add_executor_job(router.update)

    # Clear all subscriptions, enabled entities will push back theirs
    router.subscriptions.clear()

    # Set up device registry
    device_data = {}
    sw_version = None
    if router.data.get(KEY_DEVICE_INFORMATION):
        device_info = router.data[KEY_DEVICE_INFORMATION]
        serial_number = device_info.get("SerialNumber")
        if serial_number:
            device_data["identifiers"] = {(DOMAIN, serial_number)}
        sw_version = device_info.get("SoftwareVersion")
        if device_info.get("DeviceName"):
            device_data["model"] = device_info["DeviceName"]
    if not sw_version and router.data.get(KEY_DEVICE_BASIC_INFORMATION):
        sw_version = router.data[KEY_DEVICE_BASIC_INFORMATION].get("SoftwareVersion")
    if sw_version:
        device_data["sw_version"] = sw_version
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=router.device_connections,
        name=router.device_name,
        manufacturer="Huawei",
        **device_data,
    )

    # Forward config entry setup to platforms
    for domain in (DEVICE_TRACKER_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )
    # Notify doesn't support config entry setup yet, load with discovery for now
    await discovery.async_load_platform(
        hass,
        NOTIFY_DOMAIN,
        DOMAIN,
        {CONF_URL: url, CONF_RECIPIENT: config_entry.options.get(CONF_RECIPIENT)},
        hass.data[DOMAIN].hass_config,
    )

    # Add config entry options update listener
    router.unload_handlers.append(
        config_entry.add_update_listener(async_signal_options_update)
    )

    def _update_router(*_: Any) -> None:
        """
        Update router data.

        Separate passthrough function because lambdas don't work with track_time_interval.
        """
        router.update()

    # Set up periodic update
    router.unload_handlers.append(
        async_track_time_interval(hass, _update_router, SCAN_INTERVAL)
    )

    # Clean up at end
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, router.cleanup)

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload config entry."""

    # Forward config entry unload to platforms
    for domain in (DEVICE_TRACKER_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN):
        await hass.config_entries.async_forward_entry_unload(config_entry, domain)

    # Forget about the router and invoke its cleanup
    router = hass.data[DOMAIN].routers.pop(config_entry.data[CONF_URL])
    await hass.async_add_executor_job(router.cleanup)

    return True


async def async_setup(hass: HomeAssistantType, config) -> bool:
    """Set up Huawei LTE component."""

    # Arrange our YAML config to dict with normalized URLs as keys
    domain_config = {}
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = HuaweiLteData(hass_config=config, config=domain_config)
    for router_config in config.get(DOMAIN, []):
        domain_config[url_normalize(router_config.pop(CONF_URL))] = router_config

    for url, router_config in domain_config.items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_URL: url,
                    CONF_USERNAME: router_config.get(CONF_USERNAME),
                    CONF_PASSWORD: router_config.get(CONF_PASSWORD),
                },
            )
        )

    return True


async def async_signal_options_update(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Handle config entry options update."""
    async_dispatcher_send(hass, UPDATE_OPTIONS_SIGNAL, config_entry)


@attr.s
class HuaweiLteBaseEntity(Entity):
    """Huawei LTE entity base class."""

    router: Router = attr.ib()

    _available: bool = attr.ib(init=False, default=True)
    _unsub_handlers: List[Callable] = attr.ib(init=False, factory=list)

    @property
    def _entity_name(self) -> str:
        raise NotImplementedError

    @property
    def _device_unique_id(self) -> str:
        """Return unique ID for entity within a router."""
        raise NotImplementedError

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"{self.router.mac}-{self._device_unique_id}"

    @property
    def name(self) -> str:
        """Return entity name."""
        return DEFAULT_NAME_TEMPLATE.format(self.router.device_name, self._entity_name)

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._available

    @property
    def should_poll(self) -> bool:
        """Huawei LTE entities report their state without polling."""
        return False

    @property
    def device_info(self) -> Dict[str, Any]:
        """Get info for matching with parent router."""
        return {"connections": self.router.device_connections}

    async def async_update(self) -> None:
        """Update state."""
        raise NotImplementedError

    async def async_update_options(self, config_entry: ConfigEntry) -> None:
        """Update config entry options."""
        pass

    async def async_added_to_hass(self) -> None:
        """Connect to update signals."""
        self._unsub_handlers.append(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._async_maybe_update)
        )
        self._unsub_handlers.append(
            async_dispatcher_connect(
                self.hass, UPDATE_OPTIONS_SIGNAL, self._async_maybe_update_options
            )
        )

    async def _async_maybe_update(self, url: str) -> None:
        """Update state if the update signal comes from our router."""
        if url == self.router.url:
            self.async_schedule_update_ha_state(True)

    async def _async_maybe_update_options(self, config_entry: ConfigEntry) -> None:
        """Update options if the update signal comes from our router."""
        if config_entry.data[CONF_URL] == self.router.url:
            await self.async_update_options(config_entry)

    async def async_will_remove_from_hass(self) -> None:
        """Invoke unsubscription handlers."""
        for unsub in self._unsub_handlers:
            unsub()
        self._unsub_handlers.clear()
