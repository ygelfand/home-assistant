"""The tests for the Recorder component."""
# pylint: disable=protected-access
from datetime import datetime, timedelta
import unittest

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import Events, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import MATCH_ALL
from homeassistant.core import ATTR_NOW, EVENT_TIME_CHANGED, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import wait_recording_done

from tests.async_mock import patch
from tests.common import get_test_home_assistant, init_recorder_component


class TestRecorder(unittest.TestCase):
    """Test the recorder module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass)
        self.hass.start()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_saving_state(self):
        """Test saving and restoring a state."""
        entity_id = "test.recorder"
        state = "restoring_from_db"
        attributes = {"test_attr": 5, "test_attr_10": "nice"}

        self.hass.states.set(entity_id, state, attributes)

        wait_recording_done(self.hass)

        with session_scope(hass=self.hass) as session:
            db_states = list(session.query(States))
            assert len(db_states) == 1
            assert db_states[0].event_id > 0
            state = db_states[0].to_native()

        assert state == self.hass.states.get(entity_id)

    def test_saving_event(self):
        """Test saving and restoring an event."""
        event_type = "EVENT_TEST"
        event_data = {"test_attr": 5, "test_attr_10": "nice"}

        events = []

        @callback
        def event_listener(event):
            """Record events from eventbus."""
            if event.event_type == event_type:
                events.append(event)

        self.hass.bus.listen(MATCH_ALL, event_listener)

        self.hass.bus.fire(event_type, event_data)

        wait_recording_done(self.hass)

        assert len(events) == 1
        event = events[0]

        self.hass.data[DATA_INSTANCE].block_till_done()

        with session_scope(hass=self.hass) as session:
            db_events = list(session.query(Events).filter_by(event_type=event_type))
            assert len(db_events) == 1
            db_event = db_events[0].to_native()

        assert event.event_type == db_event.event_type
        assert event.data == db_event.data
        assert event.origin == db_event.origin

        # Recorder uses SQLite and stores datetimes as integer unix timestamps
        assert event.time_fired.replace(microsecond=0) == db_event.time_fired.replace(
            microsecond=0
        )


@pytest.fixture
def hass_recorder():
    """Home Assistant fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Set up with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


def _add_entities(hass, entity_ids):
    """Add entities."""
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    for idx, entity_id in enumerate(entity_ids):
        hass.states.set(entity_id, f"state{idx}", attributes)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        return [st.to_native() for st in session.query(States)]


def _add_events(hass, events):
    with session_scope(hass=hass) as session:
        session.query(Events).delete(synchronize_session=False)
    for event_type in events:
        hass.bus.fire(event_type)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        return [ev.to_native() for ev in session.query(Events)]


# pylint: disable=redefined-outer-name,invalid-name
def test_saving_state_include_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"include": {"domains": "test2"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert hass.states.get("test2.recorder") == states[0]


def test_saving_state_incl_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"include": {"entities": "test2.recorder"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert hass.states.get("test2.recorder") == states[0]


def test_saving_event_exclude_event_type(hass_recorder):
    """Test saving and restoring an event."""
    hass = hass_recorder({"exclude": {"event_types": "test"}})
    events = _add_events(hass, ["test", "test2"])
    assert len(events) == 1
    assert events[0].event_type == "test2"


def test_saving_state_exclude_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"exclude": {"domains": "test"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert hass.states.get("test2.recorder") == states[0]


def test_saving_state_exclude_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"exclude": {"entities": "test.recorder"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert hass.states.get("test2.recorder") == states[0]


def test_saving_state_exclude_domain_include_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"include": {"entities": "test.recorder"}, "exclude": {"domains": "test"}}
    )
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 2


def test_saving_state_include_domain_exclude_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"exclude": {"entities": "test.recorder"}, "include": {"domains": "test"}}
    )
    states = _add_entities(hass, ["test.recorder", "test2.recorder", "test.ok"])
    assert len(states) == 1
    assert hass.states.get("test.ok") == states[0]
    assert hass.states.get("test.ok").state == "state2"


def test_recorder_setup_failure():
    """Test some exceptions."""
    hass = get_test_home_assistant()

    with patch.object(Recorder, "_setup_connection") as setup, patch(
        "homeassistant.components.recorder.time.sleep"
    ):
        setup.side_effect = ImportError("driver not found")
        rec = Recorder(
            hass,
            auto_purge=True,
            keep_days=7,
            commit_interval=1,
            uri="sqlite://",
            db_max_retries=10,
            db_retry_wait=3,
            include={},
            exclude={},
        )
        rec.start()
        rec.join()

    hass.stop()


async def test_defaults_set(hass):
    """Test the config defaults are set."""
    recorder_config = None

    async def mock_setup(hass, config):
        """Mock setup."""
        nonlocal recorder_config
        recorder_config = config["recorder"]
        return True

    with patch("homeassistant.components.recorder.async_setup", side_effect=mock_setup):
        assert await async_setup_component(hass, "history", {})

    assert recorder_config is not None
    assert recorder_config["auto_purge"]
    assert recorder_config["purge_keep_days"] == 10


def test_auto_purge(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder()

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    test_time = tz.localize(datetime(2020, 1, 1, 4, 12, 0))

    with patch(
        "homeassistant.components.recorder.purge.purge_old_data"
    ) as purge_old_data:
        for delta in (-1, 0, 1):
            hass.bus.fire(
                EVENT_TIME_CHANGED, {ATTR_NOW: test_time + timedelta(seconds=delta)}
            )
            hass.block_till_done()
            hass.data[DATA_INSTANCE].block_till_done()

        assert len(purge_old_data.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)
