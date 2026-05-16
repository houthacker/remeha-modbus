"""Helper methods for entity-related functionality."""

from homeassistant.components.climate.const import DOMAIN as ClimatePlatform
from homeassistant.components.switch.const import DOMAIN as SwitchPlatform
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.template import integration_entities

from custom_components.remeha_modbus.api.climate_zone import ClimateZone, ZoneSchedule
from custom_components.remeha_modbus.blend.scheduler.const import SchedulerDomain
from custom_components.remeha_modbus.const import DOMAIN, SWITCH_SCHEDULE_SYNC
from custom_components.remeha_modbus.errors import EntityNotFoundError


def generate_unique_id(source: ClimateZone | ZoneSchedule | int) -> str:
    """Generate the `unique_id` if the related climate entity.

    Args:
        source (ClimateZone | ZoneSchedule | int): The source to base the unique id on.

    Returns: the unique_id of the related climate entity.

    Raises:
        `TypeError` if source is of an invalid type.

    """

    zone_id: int
    if isinstance(source, int):
        zone_id = source
    elif isinstance(source, ClimateZone):
        zone_id = source.id
    elif isinstance(source, ZoneSchedule):
        zone_id = source.zone_id
    else:
        raise TypeError("source")

    return f"zone_{zone_id}"


def is_scheduler_switch(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether the given entity id is of a `switch` in the `scheduler` component."""

    state = hass.states.get(entity_id)
    if state is None:
        return False

    if state.domain != SwitchPlatform:
        return False

    return entity_id in integration_entities(hass, SchedulerDomain)


def get_own_entity_by_unique_id(
    hass: HomeAssistant, platform_name: str, unique_id: str
) -> str | None:
    """Return a `remeha_modbus` entity_id by its `unique_id`.

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


def get_climate_entity_id(hass: HomeAssistant, zone: ClimateZone) -> str:
    """Get the `entity_id` of the given climate zone.

    Args:
        hass (HomeAssistant): The HA instance.
        zone (ClimateZone): The zone to retrieve the entity id of.

    Returns:
        The `entity_id`.

    Raises:
        `EntityNotFoundError` if the entity_id cannot be retrieved.

    """

    unique_id = generate_unique_id(zone.id)
    entity_id = get_own_entity_by_unique_id(hass, ClimatePlatform, unique_id)
    if entity_id is not None:
        return entity_id

    raise EntityNotFoundError(
        translation_domain=DOMAIN,
        translation_key="entity_not_found",
        translation_placeholders={"platform": ClimatePlatform, "unqiue_id": unique_id},
    )


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
