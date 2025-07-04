"""ABC for scenario implementations."""

import abc
import inspect


class Scenario(metaclass=abc.ABCMeta):
    """A `Scenario` implements a `Blender` use case."""

    @classmethod
    def __subclasshook__(cls, subclass):
        """Return whether `subclass` is a duck=typed subclass of a `Scenario`."""
        return hasattr(subclass, "async_execute") and inspect.iscoroutinefunction(
            subclass.async_execute
        )

    @abc.abstractmethod
    async def async_execute(self) -> None:
        """Execute this scenario.

        Any exceptions raised by implementations are documented there.
        """

        raise NotImplementedError
