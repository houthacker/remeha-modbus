"""Tests for the validation helper module."""

import pytest

from custom_components.remeha_modbus.helpers.validation import require_not_none


def test_require_not_none():
    """Test the require_not_none function."""

    assert require_not_none(1) == 1

    # Must return the same object
    d: dict = {"a": 1, "b": 2, "c": 3}
    assert require_not_none(d) is d

    with pytest.raises(expected_exception=ValueError):
        require_not_none(None)
