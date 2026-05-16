"""Blender abstract super class."""

import abc
import inspect
from enum import Enum


class BlenderState(Enum):
    """Enumerate the states a `Blender` can be in."""

    INITIAL = 1
    """The initial state, just after the `Blender` has been created."""

    STARTING = 2
    """The `Blender` is subscribing to relevant events and must not be disturbed."""

    STARTED = 3
    """The `Blender` ha successfully subscribed to relevant events and is running."""

    STOPPING = 4
    """The `Blender` is unsubscribing from all events and must not be disturbed."""

    STOPPED = 5
    """The `Blender` has unsubscribed from all relevant events and will not execute ant scenarios anymore."""


class Blender(metaclass=abc.ABCMeta):
    """A `Blender` integrates `remeha-modbus` with another integration."""

    @classmethod
    def __subclasshook__(cls, subclass):
        """Return whether `subclass` is a duck-typed subclass of a `Blender`."""
        return (
            hasattr(subclass, "async_bootstrap")
            and inspect.iscoroutinefunction(subclass.async_bootstrap)
            and hasattr(subclass, "unblend")
            and inspect.ismethod(subclass.unblend)
        )

    @abc.abstractmethod
    async def async_blend(self) -> None:
        """Ssetup the blend between the two integrations.

        To blend two integrations, implementations can for example subscribe to certain
        events.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def unblend(self) -> None:
        """async-friendly method to remove the blend between the two integrations.

        To unblend two integrations, implementations can for example unsubscribe from
        previously created subscriptions.
        """
        raise NotImplementedError


class Scenario(metaclass=abc.ABCMeta):
    """A `Scenario` implements a `Blender` use case."""

    @classmethod
    def __subclasshook__(cls, subclass):
        """Return whether `subclass` is a duck-typed subclass of a `Scenario`."""
        return hasattr(subclass, "async_execute") and inspect.iscoroutinefunction(
            subclass.async_execute
        )

    @abc.abstractmethod
    async def async_execute(self) -> None:
        """Execute this scenario.

        Any exceptions raised by implementations are documented there.
        """

        raise NotImplementedError
