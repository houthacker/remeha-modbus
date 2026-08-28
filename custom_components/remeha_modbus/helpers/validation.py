"""Validation helper functions."""

import struct
from enum import StrEnum
from typing import TypeVar

import voluptuous as vol

T = TypeVar("T")


def require_not_none[T](value: T, message: str = "Require a value, but got None", *args) -> T:
    """Require a value to be not `None`.

    Args:
        value (T): The value to test.
        message: str: A percent-format string containing the message.
        *args: Any

    Raises:
        ValueError if the value is `None`.

    """

    if value is not None:
        return value

    raise ValueError(message, args)


def str_enum(enum: type[StrEnum]) -> vol.In:
    """Create a validator for the given StrEnum."""

    return vol.In([e.value for e in enum])


def struct_format(struct_format: str | bytes) -> str | bytes:
    """Create a validator for the given struct format."""

    try:
        struct.calcsize(struct_format)
    except struct.error as e:
        raise vol.InInvalid(f"Invalid struct format {struct_format}") from e

    return struct_format
