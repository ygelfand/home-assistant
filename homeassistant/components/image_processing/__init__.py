"""Provides functionality to interact with image processing services."""
import asyncio
from datetime import timedelta
import logging
from typing import Tuple

from PIL import ImageDraw
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import ENTITY_SERVICE_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.async_ import run_callback_threadsafe

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "image_processing"
SCAN_INTERVAL = timedelta(seconds=10)

DEVICE_CLASSES = [
    "alpr",  # Automatic license plate recognition
    "face",  # Face
    "ocr",  # OCR
]

SERVICE_SCAN = "scan"

EVENT_DETECT_FACE = "image_processing.detect_face"

ATTR_AGE = "age"
ATTR_CONFIDENCE = "confidence"
ATTR_FACES = "faces"
ATTR_GENDER = "gender"
ATTR_GLASSES = "glasses"
ATTR_MOTION = "motion"
ATTR_TOTAL_FACES = "total_faces"

CONF_SOURCE = "source"
CONF_CONFIDENCE = "confidence"

DEFAULT_TIMEOUT = 10
DEFAULT_CONFIDENCE = 80

SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_domain("camera"),
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SOURCE): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
        vol.Optional(CONF_CONFIDENCE, default=DEFAULT_CONFIDENCE): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
    }
)
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)


def draw_box(
    draw: ImageDraw,
    box: Tuple[float, float, float, float],
    img_width: int,
    img_height: int,
    text: str = "",
    color: Tuple[int, int, int] = (255, 255, 0),
) -> None:
    """
    Draw a bounding box on and image.

    The bounding box is defined by the tuple (y_min, x_min, y_max, x_max)
    where the coordinates are floats in the range [0.0, 1.0] and
    relative to the width and height of the image.

    For example, if an image is 100 x 200 pixels (height x width) and the bounding
    box is `(0.1, 0.2, 0.5, 0.9)`, the upper-left and bottom-right coordinates of
    the bounding box will be `(40, 10)` to `(180, 50)` (in (x,y) coordinates).
    """

    line_width = 3
    font_height = 8
    y_min, x_min, y_max, x_max = box
    (left, right, top, bottom) = (
        x_min * img_width,
        x_max * img_width,
        y_min * img_height,
        y_max * img_height,
    )
    draw.line(
        [(left, top), (left, bottom), (right, bottom), (right, top), (left, top)],
        width=line_width,
        fill=color,
    )
    if text:
        draw.text(
            (left + line_width, abs(top - line_width - font_height)), text, fill=color
        )


async def async_setup(hass, config):
    """Set up the image processing."""
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    await component.async_setup(config)

    async def async_scan_service(service):
        """Service handler for scan."""
        image_entities = await component.async_extract_from_service(service)

        update_tasks = []
        for entity in image_entities:
            entity.async_set_context(service.context)
            update_tasks.append(entity.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks)

    hass.services.async_register(
        DOMAIN, SERVICE_SCAN, async_scan_service, schema=ENTITY_SERVICE_SCHEMA
    )

    return True


class ImageProcessingEntity(Entity):
    """Base entity class for image processing."""

    timeout = DEFAULT_TIMEOUT

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return None

    @property
    def confidence(self):
        """Return minimum confidence for do some things."""
        return None

    def process_image(self, image):
        """Process image."""
        raise NotImplementedError()

    def async_process_image(self, image):
        """Process image.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.process_image, image)

    async def async_update(self):
        """Update image and process it.

        This method is a coroutine.
        """
        camera = self.hass.components.camera
        image = None

        try:
            image = await camera.async_get_image(
                self.camera_entity, timeout=self.timeout
            )

        except HomeAssistantError as err:
            _LOGGER.error("Error on receive image from entity: %s", err)
            return

        # process image data
        await self.async_process_image(image.content)


class ImageProcessingFaceEntity(ImageProcessingEntity):
    """Base entity class for face image processing."""

    def __init__(self):
        """Initialize base face identify/verify entity."""
        self.faces = []
        self.total_faces = 0

    @property
    def state(self):
        """Return the state of the entity."""
        confidence = 0
        state = None

        # No confidence support
        if not self.confidence:
            return self.total_faces

        # Search high confidence
        for face in self.faces:
            if ATTR_CONFIDENCE not in face:
                continue

            f_co = face[ATTR_CONFIDENCE]
            if f_co > confidence:
                confidence = f_co
                for attr in [ATTR_NAME, ATTR_MOTION]:
                    if attr in face:
                        state = face[attr]
                        break

        return state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return "face"

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {ATTR_FACES: self.faces, ATTR_TOTAL_FACES: self.total_faces}

        return attr

    def process_faces(self, faces, total):
        """Send event with detected faces and store data."""
        run_callback_threadsafe(
            self.hass.loop, self.async_process_faces, faces, total
        ).result()

    @callback
    def async_process_faces(self, faces, total):
        """Send event with detected faces and store data.

        known are a dict in follow format:
         [
           {
              ATTR_CONFIDENCE: 80,
              ATTR_NAME: 'Name',
              ATTR_AGE: 12.0,
              ATTR_GENDER: 'man',
              ATTR_MOTION: 'smile',
              ATTR_GLASSES: 'sunglasses'
           },
         ]

        This method must be run in the event loop.
        """
        # Send events
        for face in faces:
            if ATTR_CONFIDENCE in face and self.confidence:
                if face[ATTR_CONFIDENCE] < self.confidence:
                    continue

            face.update({ATTR_ENTITY_ID: self.entity_id})
            self.hass.async_add_job(self.hass.bus.async_fire, EVENT_DETECT_FACE, face)

        # Update entity store
        self.faces = faces
        self.total_faces = total
