"""Errors for the remeha_modbus integration."""

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pymodbus import ModbusException


class RemehaModbusError(HomeAssistantError):
    """Base error for remeha_modbus integration."""


class ScenarioExecutionError(RemehaModbusError):
    """Exception to indicate an error occurred while executing a scenario."""


class ParseError(RemehaModbusError):
    """Exception to indicate something went wrong during parsing.

    Mostly used in scenario contexts where state fields are parsed into
    remeha_modbus domain objects.
    """


class EntityNotFoundError(RemehaModbusError):
    """Exception to indicate an entity related to a Remeha Modbus API object could not be found."""


class IncorrectEntityPlatformError(RemehaModbusError):
    """Exception to indicate an entity was processed in some way, but its platform is incorrect."""


class InvalidClimateContext(RemehaModbusError):
    """Exception to indicate an operation was attempted that is invalid in a given climate context."""


class AutoSchedulingError(RemehaModbusError):
    """Exception to indicate an error occurred while auto scheduling."""


class RemehaIncorrectServiceCall(ServiceValidationError):
    """Exception to indicate that a service has been used incorrectly."""


class RemehaServiceError(RemehaModbusError):
    """Exception to indicate that a service call failed, although it was used correctly."""


class MissingExternalComponent(RemehaModbusError):
    """Exception to indicate that a component is missing which is required for some action."""


class DiscoveryTableCorruptedError(ModbusException):
    """Exception to indicate the modbus discovery table seems corrupted.

    This happens for example if the number of devices is 0 or None.
    This can be fixed by calling the `force_system_rediscovery` service.
    """
