"""Config flow for Plex."""
import copy
import logging

from aiohttp import web_response
import plexapi.exceptions
from plexauth import PlexAuth
import requests.exceptions
import voluptuous as vol

from homeassistant.components.http.view import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_URL, CONF_TOKEN, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.util.json import load_json

from .const import (  # pylint: disable=unused-import
    AUTH_CALLBACK_NAME,
    AUTH_CALLBACK_PATH,
    CONF_CLIENT_IDENTIFIER,
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    CONF_USE_EPISODE_ART,
    CONF_SHOW_ALL_CONTROLS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLEX_CONFIG_FILE,
    PLEX_SERVER_CONFIG,
    X_PLEX_DEVICE_NAME,
    X_PLEX_VERSION,
    X_PLEX_PRODUCT,
    X_PLEX_PLATFORM,
)
from .errors import NoServersFound, ServerNotSpecified
from .server import PlexServer

_LOGGER = logging.getLogger(__package__)


@callback
def configured_servers(hass):
    """Return a set of the configured Plex servers."""
    return set(
        entry.data[CONF_SERVER_IDENTIFIER]
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


class PlexFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Plex config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PlexOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Plex flow."""
        self.current_login = {}
        self.available_servers = None
        self.plexauth = None
        self.token = None
        self.client_id = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return self.async_show_form(step_id="start_website_auth")

    async def async_step_start_website_auth(self, user_input=None):
        """Show a form before starting external authentication."""
        return await self.async_step_plex_website_auth()

    async def async_step_server_validate(self, server_config):
        """Validate a provided configuration."""
        errors = {}
        self.current_login = server_config

        plex_server = PlexServer(self.hass, server_config)
        try:
            await self.hass.async_add_executor_job(plex_server.connect)

        except NoServersFound:
            errors["base"] = "no_servers"
        except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
            _LOGGER.error("Invalid credentials provided, config not created")
            errors["base"] = "faulty_credentials"
        except (plexapi.exceptions.NotFound, requests.exceptions.ConnectionError):
            server_identifier = (
                server_config.get(CONF_URL) or plex_server.server_choice or "Unknown"
            )
            _LOGGER.error("Plex server could not be reached: %s", server_identifier)
            errors["base"] = "not_found"

        except ServerNotSpecified as available_servers:
            self.available_servers = available_servers.args[0]
            return await self.async_step_select_server()

        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting to Plex server: %s", error)
            return self.async_abort(reason="unknown")

        if errors:
            return self.async_show_form(step_id="start_website_auth", errors=errors)

        server_id = plex_server.machine_identifier

        for entry in self._async_current_entries():
            if entry.data[CONF_SERVER_IDENTIFIER] == server_id:
                return self.async_abort(reason="already_configured")

        url = plex_server.url_in_use
        token = server_config.get(CONF_TOKEN)

        entry_config = {CONF_URL: url}
        if self.client_id:
            entry_config[CONF_CLIENT_IDENTIFIER] = self.client_id
        if token:
            entry_config[CONF_TOKEN] = token
        if url.startswith("https"):
            entry_config[CONF_VERIFY_SSL] = server_config.get(
                CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
            )

        _LOGGER.debug("Valid config created for %s", plex_server.friendly_name)

        return self.async_create_entry(
            title=plex_server.friendly_name,
            data={
                CONF_SERVER: plex_server.friendly_name,
                CONF_SERVER_IDENTIFIER: server_id,
                PLEX_SERVER_CONFIG: entry_config,
            },
        )

    async def async_step_select_server(self, user_input=None):
        """Use selected Plex server."""
        config = dict(self.current_login)
        if user_input is not None:
            config[CONF_SERVER] = user_input[CONF_SERVER]
            return await self.async_step_server_validate(config)

        configured = configured_servers(self.hass)
        available_servers = [
            name
            for (name, server_id) in self.available_servers
            if server_id not in configured
        ]

        if not available_servers:
            return self.async_abort(reason="all_configured")
        if len(available_servers) == 1:
            config[CONF_SERVER] = available_servers[0]
            return await self.async_step_server_validate(config)

        return self.async_show_form(
            step_id="select_server",
            data_schema=vol.Schema(
                {vol.Required(CONF_SERVER): vol.In(available_servers)}
            ),
            errors={},
        )

    async def async_step_discovery(self, discovery_info):
        """Set default host and port from discovery."""
        if self._async_current_entries() or self._async_in_progress():
            # Skip discovery if a config already exists or is in progress.
            return self.async_abort(reason="already_configured")

        json_file = self.hass.config.path(PLEX_CONFIG_FILE)
        file_config = await self.hass.async_add_executor_job(load_json, json_file)

        if file_config:
            host_and_port, host_config = file_config.popitem()
            prefix = "https" if host_config[CONF_SSL] else "http"

            server_config = {
                CONF_URL: f"{prefix}://{host_and_port}",
                CONF_TOKEN: host_config[CONF_TOKEN],
                CONF_VERIFY_SSL: host_config["verify"],
            }
            _LOGGER.info("Imported legacy config, file can be removed: %s", json_file)
            return await self.async_step_server_validate(server_config)

        return self.async_abort(reason="discovery_no_file")

    async def async_step_import(self, import_config):
        """Import from Plex configuration."""
        _LOGGER.debug("Imported Plex configuration")
        return await self.async_step_server_validate(import_config)

    async def async_step_plex_website_auth(self):
        """Begin external auth flow on Plex website."""
        self.hass.http.register_view(PlexAuthorizationCallbackView)
        payload = {
            "X-Plex-Device-Name": X_PLEX_DEVICE_NAME,
            "X-Plex-Version": X_PLEX_VERSION,
            "X-Plex-Product": X_PLEX_PRODUCT,
            "X-Plex-Device": self.hass.config.location_name,
            "X-Plex-Platform": X_PLEX_PLATFORM,
            "X-Plex-Model": "Plex OAuth",
        }
        session = async_get_clientsession(self.hass)
        self.plexauth = PlexAuth(payload, session)
        await self.plexauth.initiate_auth()
        forward_url = f"{self.hass.config.api.base_url}{AUTH_CALLBACK_PATH}?flow_id={self.flow_id}"
        auth_url = self.plexauth.auth_url(forward_url)
        return self.async_external_step(step_id="obtain_token", url=auth_url)

    async def async_step_obtain_token(self, user_input=None):
        """Obtain token after external auth completed."""
        token = await self.plexauth.token(10)

        if not token:
            return self.async_external_step_done(next_step_id="timed_out")

        self.token = token
        self.client_id = self.plexauth.client_identifier
        return self.async_external_step_done(next_step_id="use_external_token")

    async def async_step_timed_out(self, user_input=None):
        """Abort flow when time expires."""
        return self.async_abort(reason="token_request_timeout")

    async def async_step_use_external_token(self, user_input=None):
        """Continue server validation with external token."""
        server_config = {CONF_TOKEN: self.token}
        return await self.async_step_server_validate(server_config)


class PlexOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Plex options."""

    def __init__(self, config_entry):
        """Initialize Plex options flow."""
        self.options = copy.deepcopy(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Plex options."""
        return await self.async_step_plex_mp_settings()

    async def async_step_plex_mp_settings(self, user_input=None):
        """Manage the Plex media_player options."""
        if user_input is not None:
            self.options[MP_DOMAIN][CONF_USE_EPISODE_ART] = user_input[
                CONF_USE_EPISODE_ART
            ]
            self.options[MP_DOMAIN][CONF_SHOW_ALL_CONTROLS] = user_input[
                CONF_SHOW_ALL_CONTROLS
            ]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="plex_mp_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USE_EPISODE_ART,
                        default=self.options[MP_DOMAIN][CONF_USE_EPISODE_ART],
                    ): bool,
                    vol.Required(
                        CONF_SHOW_ALL_CONTROLS,
                        default=self.options[MP_DOMAIN][CONF_SHOW_ALL_CONTROLS],
                    ): bool,
                }
            ),
        )


class PlexAuthorizationCallbackView(HomeAssistantView):
    """Handle callback from external auth."""

    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME
    requires_auth = False

    async def get(self, request):
        """Receive authorization confirmation."""
        hass = request.app["hass"]
        await hass.config_entries.flow.async_configure(
            flow_id=request.query["flow_id"], user_input=None
        )

        return web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! This window can be closed",
        )
