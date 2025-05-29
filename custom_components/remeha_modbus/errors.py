"""Errors for the remeha_modbus integration."""

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


class RemehaModbusError(HomeAssistantError):
    """Base error for remeha_modbus integration."""


class InvalidClimateContext(RemehaModbusError):
    """Exception to indicate an operation was attempted that is invalid in a given climate context."""


class AutoSchedulingError(RemehaModbusError):
    """Exception to indicate an error occurred while auto scheduling."""


class RemehaIncorrectServiceCall(ServiceValidationError):
    """Exception to indicate that a service has been used incorrectly."""


class RemehaServiceException(RemehaModbusError):
    """Exception to indicate that a service call failed, although it was used correctly."""
