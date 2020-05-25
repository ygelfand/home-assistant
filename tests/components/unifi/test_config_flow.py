"""Test UniFi config flow."""
import aiounifi

from homeassistant import data_entry_flow
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CONTROLLER,
    CONF_DETECTION_TIME,
    CONF_IGNORE_WIRED_BUG,
    CONF_POE_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .test_controller import setup_unifi_integration

from tests.async_mock import patch
from tests.common import MockConfigEntry

CLIENTS = [{"mac": "00:00:00:00:00:01"}]

DEVICES = [
    {
        "board_rev": 21,
        "device_id": "mock-id",
        "ip": "10.0.1.1",
        "last_seen": 0,
        "mac": "00:00:00:00:01:01",
        "model": "U7PG2",
        "name": "access_point",
        "state": 1,
        "type": "uap",
        "version": "4.0.80.10875",
        "wlan_overrides": [
            {
                "name": "SSID 3",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "name": "",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
        ],
    }
]

WLANS = [
    {"name": "SSID 1"},
    {"name": "SSID 2", "name_combine_enabled": False, "name_combine_suffix": "_IOT"},
]


async def test_flow_works(hass, aioclient_mock, mock_discovery):
    """Test config flow."""
    mock_discovery.return_value = "1"
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_USERNAME: "", CONF_PASSWORD: ""}) == {
        CONF_HOST: "unifi",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 8443,
        CONF_VERIFY_SSL: False,
    }

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": "application/json"},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [{"desc": "Site name", "name": "site_id", "role": "admin"}],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Site name"
    assert result["data"] == {
        CONF_CONTROLLER: {
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_SITE_ID: "site_id",
            CONF_VERIFY_SSL: True,
        }
    }


async def test_flow_works_multiple_sites(hass, aioclient_mock):
    """Test config flow works when finding multiple sites."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": "application/json"},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"name": "default", "role": "admin", "desc": "site name"},
                {"name": "site2", "role": "admin", "desc": "site2 name"},
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "site"
    assert result["data_schema"]({"site": "site name"})
    assert result["data_schema"]({"site": "site2 name"})


async def test_flow_fails_site_already_configured(hass, aioclient_mock):
    """Test config flow."""
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN, data={"controller": {"host": "1.2.3.4", "site": "site_id"}}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": "application/json"},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [{"desc": "Site name", "name": "site_id", "role": "admin"}],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_fails_user_credentials_faulty(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    with patch("aiounifi.Controller.login", side_effect=aiounifi.errors.Unauthorized):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "faulty_credentials"}


async def test_flow_fails_controller_unavailable(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    with patch("aiounifi.Controller.login", side_effect=aiounifi.errors.RequestError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "service_unavailable"}


async def test_flow_fails_unknown_problem(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    with patch("aiounifi.Controller.login", side_effect=Exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_advanced_option_flow(hass):
    """Test advanced config flow options."""
    controller = await setup_unifi_integration(
        hass, clients_response=CLIENTS, devices_response=DEVICES, wlans_response=WLANS
    )

    result = await hass.config_entries.options.async_init(
        controller.config_entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_tracker"
    assert set(
        result["data_schema"].schema[CONF_SSID_FILTER].options.keys()
    ).intersection(("SSID 1", "SSID 2", "SSID 2_IOT", "SSID 3"))

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_WIRED_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3"],
            CONF_DETECTION_TIME: 100,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "client_control"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]], CONF_POE_CLIENTS: False},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "statistics_sensors"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ALLOW_BANDWIDTH_SENSORS: True}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_WIRED_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3"],
        CONF_DETECTION_TIME: 100,
        CONF_IGNORE_WIRED_BUG: False,
        CONF_POE_CLIENTS: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
        CONF_ALLOW_BANDWIDTH_SENSORS: True,
    }


async def test_simple_option_flow(hass):
    """Test simple config flow options."""
    controller = await setup_unifi_integration(
        hass, clients_response=CLIENTS, wlans_response=WLANS
    )

    result = await hass.config_entries.options.async_init(
        controller.config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "simple_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
    }
