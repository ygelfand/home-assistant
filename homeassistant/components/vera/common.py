"""Common vera code."""
import logging
from typing import DefaultDict, List, NamedTuple, Set

import pyvera as pv

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import call_later

_LOGGER = logging.getLogger(__name__)


class ControllerData(NamedTuple):
    """Controller data."""

    controller: pv.VeraController
    devices: DefaultDict[str, List[pv.VeraDevice]]
    scenes: List[pv.VeraScene]


def get_configured_platforms(controller_data: ControllerData) -> Set[str]:
    """Get configured platforms for a controller."""
    platforms = []
    for platform in controller_data.devices:
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(SCENE_DOMAIN)

    return set(platforms)


class SubscriptionRegistry(pv.AbstractSubscriptionRegistry):
    """Manages polling for data from vera."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the object."""
        super().__init__()
        self._hass = hass
        self._cancel_poll = None

    def start(self) -> None:
        """Start polling for data."""
        self.stop()
        self._schedule_poll(1)

    def stop(self) -> None:
        """Stop polling for data."""
        if self._cancel_poll:
            self._cancel_poll()
            self._cancel_poll = None

    def _schedule_poll(self, delay: float) -> None:
        self._cancel_poll = call_later(self._hass, delay, self._run_poll_server)

    def _run_poll_server(self, now) -> None:
        delay = 1

        # Long poll for changes. The downstream API instructs the endpoint to wait a
        # a minimum of 200ms before returning data and a maximum of 9s before timing out.
        if not self.poll_server_once():
            # If an error was encountered, wait a bit longer before trying again.
            delay = 60

        self._schedule_poll(delay)
