"""Helpers for config validation that are not in the HA helpers."""

from enum import StrEnum

import voluptuous as vol


def str_enum(enum: type[StrEnum]) -> vol.In:
    """Create a validator for the given StrEnum."""

    return vol.In([e.value for e in enum])
