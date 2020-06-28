"""The tests for the Rfxtrx light platform."""
import unittest

import pytest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, mock_component


@pytest.mark.skipif("os.environ.get('RFXTRX') != 'RUN'")
class TestLightRfxtrx(unittest.TestCase):
    """Test the Rfxtrx light platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, "rfxtrx")
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS.clear()
        rfxtrx_core.RFX_DEVICES.clear()
        if rfxtrx_core.DATA_RFXOBJECT in self.hass.data:
            self.hass.data[rfxtrx_core.DATA_RFXOBJECT].close_connection()
        self.hass.stop()

    def test_valid_config(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIRE_EVENT: True,
                        }
                    },
                }
            },
        )

        assert setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            "signal_repetitions": 3,
                        }
                    },
                }
            },
        )

    def test_default_config(self):
        """Test with 0 switches."""
        assert setup_component(
            self.hass, "light", {"light": {"platform": "rfxtrx", "devices": {}}}
        )
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

    def test_one_light(self):
        """Test with 1 light."""
        assert setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "rfxtrx",
                    "devices": {"0b1100cd0213c7f210010f51": {"name": "Test"}},
                }
            },
        )

        import RFXtrx as rfxtrxmod

        self.hass.data[rfxtrx_core.DATA_RFXOBJECT] = rfxtrxmod.Core(
            "", transport_protocol=rfxtrxmod.DummyTransport
        )

        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        entity = rfxtrx_core.RFX_DEVICES["213c7f2_16"]
        entity.hass = self.hass
        assert "Test" == entity.name
        assert "off" == entity.state
        assert entity.assumed_state
        assert entity.signal_repetitions == 1
        assert not entity.should_fire_event
        assert not entity.should_poll

        assert not entity.is_on

        entity.turn_on()
        assert entity.is_on
        assert entity.brightness == 255

        entity.turn_off()
        assert not entity.is_on
        assert entity.brightness == 0

        entity.turn_on(brightness=100)
        assert entity.is_on
        assert entity.brightness == 100

        entity.turn_on(brightness=10)
        assert entity.is_on
        assert entity.brightness == 10

        entity.turn_on(brightness=255)
        assert entity.is_on
        assert entity.brightness == 255

        entity.turn_off()
        assert "Test" == entity.name
        assert "off" == entity.state

        entity.turn_on()
        assert "on" == entity.state

        entity.turn_off()
        assert "off" == entity.state

        entity.turn_on(brightness=100)
        assert "on" == entity.state

        entity.turn_on(brightness=10)
        assert "on" == entity.state

        entity.turn_on(brightness=255)
        assert "on" == entity.state

    def test_several_lights(self):
        """Test with 3 lights."""
        assert setup_component(
            self.hass,
            "light",
            {
                "light": {
                    "platform": "rfxtrx",
                    "signal_repetitions": 3,
                    "devices": {
                        "0b1100cd0213c7f230010f71": {"name": "Test"},
                        "0b1100100118cdea02010f70": {"name": "Bath"},
                        "0b1100101118cdea02010f70": {"name": "Living"},
                    },
                }
            },
        )

        assert 3 == len(rfxtrx_core.RFX_DEVICES)
        device_num = 0
        for id in rfxtrx_core.RFX_DEVICES:
            entity = rfxtrx_core.RFX_DEVICES[id]
            assert entity.signal_repetitions == 3
            if entity.name == "Living":
                device_num = device_num + 1
                assert "off" == entity.state
                assert "<Entity Living: off>" == entity.__str__()
            elif entity.name == "Bath":
                device_num = device_num + 1
                assert "off" == entity.state
                assert "<Entity Bath: off>" == entity.__str__()
            elif entity.name == "Test":
                device_num = device_num + 1
                assert "off" == entity.state
                assert "<Entity Test: off>" == entity.__str__()

        assert 3 == device_num

    def test_discover_light(self):
        """Test with discovery of lights."""
        assert setup_component(
            self.hass,
            "light",
            {"light": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0b11009e00e6116202020070")
        event.data = bytearray(b"\x0b\x11\x00\x9e\x00\xe6\x11b\x02\x02\x00p")

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = rfxtrx_core.RFX_DEVICES["0e61162_2"]
        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        assert "<Entity 0b11009e00e6116202020070: on>" == entity.__str__()

        event = rfxtrx_core.get_rfx_object("0b11009e00e6116201010070")
        event.data = bytearray(b"\x0b\x11\x00\x9e\x00\xe6\x11b\x01\x01\x00p")

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 1 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0b1100120118cdea02020070")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x12, 0x01, 0x18, 0xCD, 0xEA, 0x02, 0x02, 0x00, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = rfxtrx_core.RFX_DEVICES["118cdea_2"]
        assert 2 == len(rfxtrx_core.RFX_DEVICES)
        assert "<Entity 0b1100120118cdea02020070: on>" == entity.__str__()

        # trying to add a sensor
        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        # trying to add a switch
        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x01, 0x0F, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a rollershutter
        event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

    def test_discover_light_noautoadd(self):
        """Test with discover of light when auto add is False."""
        assert setup_component(
            self.hass,
            "light",
            {"light": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0b1100120118cdea02020070")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x12, 0x01, 0x18, 0xCD, 0xEA, 0x02, 0x02, 0x00, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0b1100120118cdea02010070")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x12, 0x01, 0x18, 0xCD, 0xEA, 0x02, 0x01, 0x00, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0b1100120118cdea02020070")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x12, 0x01, 0x18, 0xCD, 0xEA, 0x02, 0x02, 0x00, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a switch
        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x01, 0x0F, 0x70]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a rollershutter
        event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)
