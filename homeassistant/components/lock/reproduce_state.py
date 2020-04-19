"""Reproduce an Lock state."""
import asyncio
import logging
from typing import Iterable, Optional

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_LOCKED, STATE_UNLOCKED}


async def _async_reproduce_state(
    hass: HomeAssistantType, state: State, context: Optional[Context] = None
) -> None:
    """Reproduce a single state."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if state.state not in VALID_STATES:
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state:
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state == STATE_LOCKED:
        service = SERVICE_LOCK
    elif state.state == STATE_UNLOCKED:
        service = SERVICE_UNLOCK

    await hass.services.async_call(
        DOMAIN, service, service_data, context=context, blocking=True
    )


async def async_reproduce_states(
    hass: HomeAssistantType, states: Iterable[State], context: Optional[Context] = None
) -> None:
    """Reproduce Lock states."""
    await asyncio.gather(
        *(_async_reproduce_state(hass, state, context) for state in states)
    )
