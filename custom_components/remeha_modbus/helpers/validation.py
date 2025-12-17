"""Validation helper functions."""

from typing import TypeVar

T = TypeVar("T")


def require_not_none(value: T, message: str = "Require a value, but got None", *args) -> T:
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
