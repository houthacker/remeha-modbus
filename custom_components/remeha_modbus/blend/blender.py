"""Blender super class."""

import abc


class Blender(metaclass=abc.ABCMeta):
    """A `Blender` integrates `remeha_modbus` with another integration."""

    @classmethod
    def __subclasshook__(cls, subclass):
        """Return whether `subclass` is a duck=typed subclass of a `Blender`."""
        return (
            hasattr(subclass, "blend")
            and callable(subclass.blend)
            and hasattr(subclass, "unblend")
            and callable(subclass.unblend)
        )

    @abc.abstractmethod
    def blend(self) -> None:
        """async-friendly method to create the blend between the two integrations.

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
