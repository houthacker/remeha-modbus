"""Errors for the remeha_modbus integration."""

from homeassistant.exceptions import HomeAssistantError


class RemehaModbusError(HomeAssistantError):
    """Base error for remeha_modbus integration."""


class InvalidClimateContext(RemehaModbusError):
    """Exception to indicate an operation was attempted that is invalid in a given climate context."""
