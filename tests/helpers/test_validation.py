"""Test validation helper."""

import pytest

from custom_components.remeha_modbus.helpers import validation


def test_require_not_none():
    """Test the require_not_none method."""

    assert validation.require_not_none("test") == "test"

    with pytest.raises(expected_exception=ValueError, match="Require a value, but got None"):
        validation.require_not_none(None)

    with pytest.raises(expected_exception=ValueError, match="Custom error message"):
        validation.require_not_none(None, "Custom error message")
