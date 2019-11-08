"""Support to embed Plex."""
import asyncio
import logging

import plexapi.exceptions
from plexwebsocket import PlexWebsocket
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import (
    CONF_USE_EPISODE_ART,
    CONF_SHOW_ALL_CONTROLS,
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DISPATCHERS,
    DOMAIN as PLEX_DOMAIN,
    PLATFORMS,
    PLEX_MEDIA_PLAYER_OPTIONS,
    PLEX_SERVER_CONFIG,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
    WEBSOCKETS,
)
from .server import PlexServer

MEDIA_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USE_EPISODE_ART, default=False): cv.boolean,
        vol.Optional(CONF_SHOW_ALL_CONTROLS, default=False): cv.boolean,
    }
)

SERVER_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(CONF_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_TOKEN): cv.string,
            vol.Optional(CONF_SERVER): cv.string,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
            vol.Optional(MP_DOMAIN, default={}): MEDIA_PLAYER_SCHEMA,
        },
        cv.has_at_least_one_key(CONF_HOST, CONF_TOKEN),
    )
)

CONFIG_SCHEMA = vol.Schema({PLEX_DOMAIN: SERVER_CONFIG_SCHEMA}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__package__)


def setup(hass, config):
    """Set up the Plex component."""
    hass.data.setdefault(PLEX_DOMAIN, {SERVERS: {}, DISPATCHERS: {}, WEBSOCKETS: {}})

    plex_config = config.get(PLEX_DOMAIN, {})
    if plex_config:
        _setup_plex(hass, plex_config)

    return True


def _setup_plex(hass, config):
    """Pass configuration to a config flow."""
    server_config = dict(config)
    if MP_DOMAIN in server_config:
        hass.data.setdefault(PLEX_MEDIA_PLAYER_OPTIONS, server_config.pop(MP_DOMAIN))
    if CONF_HOST in server_config:
        prefix = "https" if server_config.pop(CONF_SSL) else "http"
        server_config[
            CONF_URL
        ] = f"{prefix}://{server_config.pop(CONF_HOST)}:{server_config.pop(CONF_PORT)}"
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            PLEX_DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=server_config,
        )
    )


async def async_setup_entry(hass, entry):
    """Set up Plex from a config entry."""
    server_config = entry.data[PLEX_SERVER_CONFIG]

    if MP_DOMAIN not in entry.options:
        options = dict(entry.options)
        options.setdefault(
            MP_DOMAIN,
            hass.data.get(PLEX_MEDIA_PLAYER_OPTIONS) or MEDIA_PLAYER_SCHEMA({}),
        )
        hass.config_entries.async_update_entry(entry, options=options)

    plex_server = PlexServer(hass, server_config, entry.options)
    try:
        await hass.async_add_executor_job(plex_server.connect)
    except requests.exceptions.ConnectionError as error:
        _LOGGER.error(
            "Plex server (%s) could not be reached: [%s]",
            server_config[CONF_URL],
            error,
        )
        return False
    except (
        plexapi.exceptions.BadRequest,
        plexapi.exceptions.Unauthorized,
        plexapi.exceptions.NotFound,
    ) as error:
        _LOGGER.error(
            "Login to %s failed, verify token and SSL settings: [%s]",
            entry.data[CONF_SERVER],
            error,
        )
        return False

    _LOGGER.debug(
        "Connected to: %s (%s)", plex_server.friendly_name, plex_server.url_in_use
    )
    server_id = plex_server.machine_identifier
    hass.data[PLEX_DOMAIN][SERVERS][server_id] = plex_server

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(async_options_updated)

    unsub = async_dispatcher_connect(
        hass,
        PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id),
        plex_server.update_platforms,
    )
    hass.data[PLEX_DOMAIN][DISPATCHERS].setdefault(server_id, [])
    hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    def update_plex():
        async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

    session = async_get_clientsession(hass)
    verify_ssl = server_config.get(CONF_VERIFY_SSL)
    websocket = PlexWebsocket(
        plex_server.plex_server, update_plex, session=session, verify_ssl=verify_ssl
    )
    hass.loop.create_task(websocket.listen())
    hass.data[PLEX_DOMAIN][WEBSOCKETS][server_id] = websocket

    def close_websocket_session(_):
        websocket.close()

    unsub = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, close_websocket_session
    )
    hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    server_id = entry.data[CONF_SERVER_IDENTIFIER]

    websocket = hass.data[PLEX_DOMAIN][WEBSOCKETS].pop(server_id)
    websocket.close()

    dispatchers = hass.data[PLEX_DOMAIN][DISPATCHERS].pop(server_id)
    for unsub in dispatchers:
        unsub()

    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, platform)
        for platform in PLATFORMS
    ]
    await asyncio.gather(*tasks)

    hass.data[PLEX_DOMAIN][SERVERS].pop(server_id)

    return True


async def async_options_updated(hass, entry):
    """Triggered by config entry options updates."""
    server_id = entry.data[CONF_SERVER_IDENTIFIER]
    hass.data[PLEX_DOMAIN][SERVERS][server_id].options = entry.options
