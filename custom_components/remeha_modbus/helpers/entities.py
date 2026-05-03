"""Helper methods for entity-related functionality."""

from homeassistant.components.switch.const import DOMAIN as SwitchPlatform
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from custom_components.remeha_modbus.const import DOMAIN, SWITCH_SCHEDULE_SYNC


def get_own_entity_by_unique_id(
    hass: HomeAssistant, platform_name: str, unique_id: str
) -> str | None:
    """Return a `remeha_modbus` entity by its `unique_id`.

    Args:
        hass: The HA instance
        platform_name: The platform the entity belongs to, for example `light` or `switch`.
        unique_id: The unique id of the entity.

    Returns:
        The `entity_id`, or `None` if no such entity can be found.

    """

    platform = next(
        (p for p in entity_platform.async_get_platforms(hass, DOMAIN) if p.domain == platform_name),
        None,
    )

    if platform is not None:
        return next(
            (
                entity.entity_id
                for entity in platform.entities.values()
                if entity.unique_id == unique_id
            ),
            None,
        )

    return None


def is_schedule_sync_enabled(hass: HomeAssistant) -> bool:
    """Return whether schedule synchronization is enabled.

    Whether schedule synchronization is enabled depends on the state of a `switch`
    entity having a `unique_id` of `const.SWITCH_SCHEDULE_SYNC`. This allows users to
    enable and disable schedule synchronization using for example a script or automation.
    """

    schedule_sync_switch = get_own_entity_by_unique_id(hass, SwitchPlatform, SWITCH_SCHEDULE_SYNC)
    if schedule_sync_switch is None:
        return False

    return hass.states.get(schedule_sync_switch) == STATE_ON
