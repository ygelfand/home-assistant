"""Base class for iRobot devices."""
import asyncio
import logging

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STOP,
    StateVacuumDevice,
)
from homeassistant.helpers.entity import Entity

from . import roomba_reported_state
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLEANING_TIME = "cleaning_time"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_ERROR = "error"
ATTR_POSITION = "position"
ATTR_SOFTWARE_VERSION = "software_version"

# Commonly supported features
SUPPORT_IROBOT = (
    SUPPORT_BATTERY
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_SEND_COMMAND
    | SUPPORT_START
    | SUPPORT_STATE
    | SUPPORT_STOP
    | SUPPORT_LOCATE
)

STATE_MAP = {
    "": STATE_IDLE,
    "charge": STATE_DOCKED,
    "hmMidMsn": STATE_CLEANING,  # Recharging at the middle of a cycle
    "hmPostMsn": STATE_RETURNING,  # Cycle finished
    "hmUsrDock": STATE_RETURNING,
    "pause": STATE_PAUSED,
    "run": STATE_CLEANING,
    "stop": STATE_IDLE,
    "stuck": STATE_ERROR,
}


class IRobotEntity(Entity):
    """Base class for iRobot Entities."""

    def __init__(self, roomba, blid):
        """Initialize the iRobot handler."""
        self.vacuum = roomba
        self._blid = blid
        vacuum_state = roomba_reported_state(roomba)
        self._name = vacuum_state.get("name")
        self._version = vacuum_state.get("softwareVer")
        self._sku = vacuum_state.get("sku")

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def robot_unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return f"roomba_{self._blid}"

    @property
    def unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return self.robot_unique_id

    @property
    def device_info(self):
        """Return the device info of the vacuum cleaner."""
        return {
            "identifiers": {(DOMAIN, self.robot_unique_id)},
            "manufacturer": "iRobot",
            "name": str(self._name),
            "sw_version": self._version,
            "model": self._sku,
        }

    async def async_added_to_hass(self):
        """Register callback function."""
        self.vacuum.register_on_message_callback(self.on_message)

    def on_message(self, json_data):
        """Update state on message change."""
        self.schedule_update_ha_state()


class IRobotVacuum(IRobotEntity, StateVacuumDevice):
    """Base class for iRobot robots."""

    def __init__(self, roomba, blid):
        """Initialize the iRobot handler."""
        super().__init__(roomba, blid)
        self.vacuum_state = roomba_reported_state(roomba)
        self._cap_position = self.vacuum_state.get("cap", {}).get("pose") == 1

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_IROBOT

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return None

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return []

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.vacuum_state.get("batPct")

    @property
    def state(self):
        """Return the state of the vacuum cleaner."""
        clean_mission_status = self.vacuum_state.get("cleanMissionStatus", {})
        cycle = clean_mission_status.get("cycle")
        phase = clean_mission_status.get("phase")
        try:
            state = STATE_MAP[phase]
        except KeyError:
            return STATE_ERROR
        if cycle != "none" and state != STATE_CLEANING and state != STATE_RETURNING:
            state = STATE_PAUSED
        return state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Always available, otherwise setup will fail

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        state = self.vacuum_state

        # Roomba software version
        software_version = state.get("softwareVer")

        # Error message in plain english
        error_msg = "None"
        if hasattr(self.vacuum, "error_message"):
            error_msg = self.vacuum.error_message

        # Set properties that are to appear in the GUI
        state_attrs = {ATTR_SOFTWARE_VERSION: software_version}

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self.state == STATE_CLEANING:
            # Get clean mission status
            mission_state = state.get("cleanMissionStatus", {})
            cleaning_time = mission_state.get("mssnM")
            cleaned_area = mission_state.get("sqft")  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if cleaned_area and self.hass.config.units.is_metric:
                cleaned_area = round(cleaned_area * 0.0929)
            state_attrs[ATTR_CLEANING_TIME] = cleaning_time
            state_attrs[ATTR_CLEANED_AREA] = cleaned_area

        # Skip error attr if there is none
        if error_msg and error_msg != "None":
            state_attrs[ATTR_ERROR] = error_msg

        # Not all Roombas expose position data
        # https://github.com/koalazak/dorita980/issues/48
        if self._cap_position:
            pos_state = state.get("pose", {})
            position = None
            pos_x = pos_state.get("point", {}).get("x")
            pos_y = pos_state.get("point", {}).get("y")
            theta = pos_state.get("theta")
            if all(item is not None for item in [pos_x, pos_y, theta]):
                position = f"({pos_x}, {pos_y}, {theta})"
            state_attrs[ATTR_POSITION] = position

        return state_attrs

    def on_message(self, json_data):
        """Update state on message change."""
        _LOGGER.debug("Got new state from the vacuum: %s", json_data)
        self.vacuum_state = roomba_reported_state(self.vacuum)
        self.schedule_update_ha_state()

    async def async_start(self):
        """Start or resume the cleaning task."""
        if self.state == STATE_PAUSED:
            await self.hass.async_add_executor_job(self.vacuum.send_command, "resume")
        else:
            await self.hass.async_add_executor_job(self.vacuum.send_command, "start")

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "stop")

    async def async_pause(self):
        """Pause the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "pause")

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        if self.state == STATE_CLEANING:
            await self.async_pause()
            for _ in range(0, 10):
                if self.state == STATE_PAUSED:
                    break
                await asyncio.sleep(1)
        await self.hass.async_add_executor_job(self.vacuum.send_command, "dock")

    async def async_locate(self, **kwargs):
        """Located vacuum."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "find")

    async def async_send_command(self, command, params=None, **kwargs):
        """Send raw command."""
        _LOGGER.debug("async_send_command %s (%s), %s", command, params, kwargs)
        await self.hass.async_add_executor_job(
            self.vacuum.send_command, command, params
        )
