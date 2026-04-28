"""Utilities for handling the various scheduler blending scenarios."""

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.template import integration_entities
from pydantic import TypeAdapter

from custom_components.remeha_modbus.const import DOMAIN, SchedulerState


def to_scheduler_state(state: State) -> SchedulerState:
    """Convert the given state to a `SchedulerState` instance.

    Args:
        state (State): The state to convert.

    Returns:
        The scheduler state.

    Raises:
        ValidationError: if `state` cannot be converted to a `SchedulerState`.

    """

    validator = TypeAdapter(SchedulerState)
    return validator.validate_python(dict(state.as_dict()))


def links_exclusively_to_remeha_climate(
    hass: HomeAssistant, scheduler_state: SchedulerState
) -> bool:
    """Determine whether the given scheduler state links to a single remeha climate only.

    Args:
        hass (HomeAssistant): The current Home Assistant instance.
        scheduler_state (SchedulerState): The scheduler state to examine.

    Returns:
        `True` if the given state exclusively links to a `remeha_modbus` entity, `False` otherwise.

    """

    linked_entities: list[str] = scheduler_state["attributes"]["entities"]
    if linked_entities is not None and len(linked_entities) == 1:
        return linked_entities[0] in integration_entities(hass=hass, entry_name=DOMAIN)

    return False
