"""Tests for the config_validation helpers."""

import pytest
import voluptuous as vol

from custom_components.remeha_modbus.helpers.config_validation import struct_format


def test_struct_format():
    """Test the struct_format schema helper."""

    assert struct_format("=HH") == "=HH"

    with pytest.raises(expected_exception=vol.Invalid):
        struct_format("abc")
