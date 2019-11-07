"""Support for Vivotek IP Cameras."""

import logging

import voluptuous as vol
from libpyvivotek import VivotekCamera

from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.components.camera import PLATFORM_SCHEMA, SUPPORT_STREAM, Camera
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_FRAMERATE = "framerate"

CONF_STREAM_PATH = "stream_path"

DEFAULT_CAMERA_BRAND = "Vivotek"
DEFAULT_NAME = "Vivotek Camera"
DEFAULT_EVENT_0_KEY = "event_i0_enable"
DEFAULT_STREAM_SOURCE = "live.sdp"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_FRAMERATE, default=2): cv.positive_int,
        vol.Optional(CONF_STREAM_PATH, default=DEFAULT_STREAM_SOURCE): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Vivotek IP Camera."""
    creds = f"{config[CONF_USERNAME]}:{config[CONF_PASSWORD]}"
    args = dict(
        config=config,
        cam=VivotekCamera(
            host=config[CONF_IP_ADDRESS],
            port=(443 if config[CONF_SSL] else 80),
            verify_ssl=config[CONF_VERIFY_SSL],
            usr=config[CONF_USERNAME],
            pwd=config[CONF_PASSWORD],
        ),
        stream_source=f"rtsp://{creds}@{config[CONF_IP_ADDRESS]}:554/{config[CONF_STREAM_PATH]}",
    )
    add_entities([VivotekCam(**args)], True)


class VivotekCam(Camera):
    """A Vivotek IP camera."""

    def __init__(self, config, cam, stream_source):
        """Initialize a Vivotek camera."""
        super().__init__()

        self._cam = cam
        self._frame_interval = 1 / config[CONF_FRAMERATE]
        self._motion_detection_enabled = False
        self._model_name = None
        self._name = config[CONF_NAME]
        self._stream_source = stream_source

    @property
    def supported_features(self):
        """Return supported features for this camera."""
        return SUPPORT_STREAM

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    def camera_image(self):
        """Return bytes of camera image."""
        return self._cam.snapshot()

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    async def stream_source(self):
        """Return the source of the stream."""
        return self._stream_source

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        response = self._cam.set_param(DEFAULT_EVENT_0_KEY, 0)
        self._motion_detection_enabled = int(response) == 1

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        response = self._cam.set_param(DEFAULT_EVENT_0_KEY, 1)
        self._motion_detection_enabled = int(response) == 1

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_CAMERA_BRAND

    @property
    def model(self):
        """Return the camera model."""
        return self._model_name

    def update(self):
        """Update entity status."""
        self._model_name = self._cam.model_name
