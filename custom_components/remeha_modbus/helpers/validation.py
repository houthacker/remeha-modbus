"""Validation helper functions."""

from typing import TypeVar

T = TypeVar("T")


def require_not_none(value: T) -> T:
    """Require a value to be not `None`.

    Args:
        value (T): The value to test.

    Raises:
        ValueError if the value is `None`.

    """

    if value is not None:
        return value

    raise ValueError("Require a value, bot got None.")
