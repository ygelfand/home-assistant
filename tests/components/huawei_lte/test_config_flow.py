"""Tests for the Huawei LTE config flow."""

from huawei_lte_api.enums.client import ResponseCodeEnum
from huawei_lte_api.enums.user import LoginErrorEnum, LoginStateEnum, PasswordTypeEnum
from requests_mock import ANY
from requests.exceptions import ConnectionError
import pytest

from homeassistant import data_entry_flow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_URL
from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.huawei_lte.config_flow import ConfigFlowHandler
from homeassistant.components.ssdp import (
    ATTR_HOST,
    ATTR_MANUFACTURER,
    ATTR_MANUFACTURERURL,
    ATTR_MODEL_NAME,
    ATTR_MODEL_NUMBER,
    ATTR_NAME,
    ATTR_PORT,
    ATTR_PRESENTATIONURL,
    ATTR_SERIAL,
    ATTR_ST,
    ATTR_UDN,
    ATTR_UPNP_DEVICE_TYPE,
)

from tests.common import MockConfigEntry


FIXTURE_USER_INPUT = {
    CONF_URL: "http://192.168.1.1/",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}


@pytest.fixture
def flow(hass):
    """Get flow to test."""
    flow = ConfigFlowHandler()
    flow.hass = hass
    flow.context = {}
    return flow


async def test_show_set_form(flow):
    """Test that the setup form is served."""
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_urlize_plain_host(flow, requests_mock):
    """Test that plain host or IP gets converted to a URL."""
    requests_mock.request(ANY, ANY, exc=ConnectionError())
    host = "192.168.100.1"
    user_input = {**FIXTURE_USER_INPUT, CONF_URL: host}
    result = await flow.async_step_user(user_input=user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert user_input[CONF_URL] == f"http://{host}/"


async def test_already_configured(flow):
    """Test we reject already configured devices."""
    MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, title="Already configured"
    ).add_to_hass(flow.hass)

    # Tweak URL a bit to check that doesn't fail duplicate detection
    result = await flow.async_step_user(
        user_input={
            **FIXTURE_USER_INPUT,
            CONF_URL: FIXTURE_USER_INPUT[CONF_URL].replace("http", "HTTP"),
        }
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error(flow, requests_mock):
    """Test we show user form on connection error."""

    requests_mock.request(ANY, ANY, exc=ConnectionError())
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "unknown_connection_error"}


@pytest.fixture
def login_requests_mock(requests_mock):
    """Set up a requests_mock with base mocks for login tests."""
    requests_mock.request(
        ANY, FIXTURE_USER_INPUT[CONF_URL], text='<meta name="csrf_token" content="x"/>'
    )
    requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/state-login",
        text=(
            f"<response><State>{LoginStateEnum.LOGGED_OUT}</State>"
            f"<password_type>{PasswordTypeEnum.SHA256}</password_type></response>"
        ),
    )
    return requests_mock


@pytest.mark.parametrize(
    ("code", "errors"),
    (
        (LoginErrorEnum.USERNAME_WRONG, {CONF_USERNAME: "incorrect_username"}),
        (LoginErrorEnum.PASSWORD_WRONG, {CONF_PASSWORD: "incorrect_password"}),
        (
            LoginErrorEnum.USERNAME_PWD_WRONG,
            {CONF_USERNAME: "incorrect_username_or_password"},
        ),
        (LoginErrorEnum.USERNAME_PWD_ORERRUN, {"base": "login_attempts_exceeded"}),
        (ResponseCodeEnum.ERROR_SYSTEM_UNKNOWN, {"base": "response_error"}),
    ),
)
async def test_login_error(flow, login_requests_mock, code, errors):
    """Test we show user form with appropriate error on response failure."""
    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        text=f"<error><code>{code}</code><message/></error>",
    )
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors


async def test_success(flow, login_requests_mock):
    """Test successful flow provides entry creation data."""
    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        text=f"<response>OK</response>",
    )
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_ssdp(flow):
    """Test SSDP discovery initiates config properly."""
    url = "http://192.168.100.1/"
    result = await flow.async_step_ssdp(
        discovery_info={
            ATTR_ST: "upnp:rootdevice",
            ATTR_PORT: 60957,
            ATTR_HOST: "192.168.100.1",
            ATTR_MANUFACTURER: "Huawei",
            ATTR_MANUFACTURERURL: "http://www.huawei.com/",
            ATTR_MODEL_NAME: "Huawei router",
            ATTR_MODEL_NUMBER: "12345678",
            ATTR_NAME: "Mobile Wi-Fi",
            ATTR_PRESENTATIONURL: url,
            ATTR_SERIAL: "00000000",
            ATTR_UDN: "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        }
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert flow.context[CONF_URL] == url
