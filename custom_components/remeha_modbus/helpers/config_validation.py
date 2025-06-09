"""Helpers for config validation that are not in the HA helpers."""

import struct
from enum import Enum, StrEnum

import voluptuous as vol


def str_enum(enum: type[StrEnum]) -> vol.In:
    """Create a validator for the given StrEnum."""

    return vol.In([e.value for e in enum])


def enum_names(enum: type[Enum]) -> vol.In:
    """Create a validator for the given Enum."""

    return vol.In([e.name for e in enum])


def struct_format(struct_format: str | bytes) -> str | bytes:
    """Create a validator for the given struct format."""

    try:
        struct.calcsize(struct_format)
    except struct.error as e:
        raise vol.InInvalid(f"Invalid struct format {struct_format}") from e

    return struct_format
