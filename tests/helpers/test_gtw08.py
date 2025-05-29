"""Test GTW-08 helper."""

from datetime import datetime
from typing import Final

from dateutil import tz

from custom_components.remeha_modbus.helpers.gtw08 import TimeOfDay


def test_time_of_day_encode():
    """Test that encoding and decoding a value returns the same value."""

    # Simulate an aware datetime coming from Home Assistant
    expected: Final[datetime] = datetime(
        year=2025,
        month=4,
        day=28,
        hour=18,
        minute=00,
        second=00,
        tzinfo=tz.gettz("Europe/Amsterdam"),
    )

    encoded = TimeOfDay.to_bytes(expected)
    assert encoded == b"\xc5\x00\x03\xdc\x3a\xf5"


def test_time_of_day_decode():
    """Test decoding a bytes object into a datetime."""

    expected: Final[datetime] = datetime(
        year=2025,
        month=4,
        day=28,
        hour=18,
        minute=00,
        second=00,
        tzinfo=tz.gettz("Europe/Amsterdam"),
    )

    byte_string: bytes = b"\xc5\x00\x03\xdc\x3a\xf5"
    assert TimeOfDay.from_bytes(byte_string, tz.gettz(name="Europe/Amsterdam")) == expected
