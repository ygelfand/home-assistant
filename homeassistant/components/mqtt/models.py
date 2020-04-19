"""Modesl used by multiple MQTT modules."""
from typing import Callable, Union

import attr

PublishPayloadType = Union[str, bytes, int, float, None]


@attr.s(slots=True, frozen=True)
class Message:
    """MQTT Message."""

    topic = attr.ib(type=str)
    payload = attr.ib(type=PublishPayloadType)
    qos = attr.ib(type=int)
    retain = attr.ib(type=bool)
    subscribed_topic = attr.ib(type=str, default=None)


MessageCallbackType = Callable[[Message], None]
