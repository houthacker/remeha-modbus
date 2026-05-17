"""Utilities for handling the various scheduler blending scenarios."""

from datetime import datetime, time, timedelta
from typing import cast
from uuid import UUID

from homeassistant.components.climate.const import DOMAIN as ClimateDomain
from homeassistant.components.climate.const import PRESET_COMFORT, PRESET_ECO, PRESET_NONE
from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant, State
from pydantic import TypeAdapter

from custom_components.remeha_modbus.api.climate_zone import ClimateZone
from custom_components.remeha_modbus.api.schedule import (
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.blend.scheduler.const import (
    SCHEDULER_TAG_PREFIX,
    SHORT_DESC_TO_WEEKDAY,
    WEEKDAY_TO_SHORT_DESC,
    SchedulerAction,
    SchedulerCondition,
    SchedulerDomain,
    SchedulerSchedule,
    SchedulerState,
    SchedulerStateAction,
    SchedulerTimeslot,
    ServiceOperation,
)
from custom_components.remeha_modbus.const import (
    ATTR_SCHEDULER_NAME,
    ATTR_SCHEDULER_TAGS,
    DOMAIN,
    HEATPUMP_MANAGED_SCHEDULES,
    Weekday,
    ZoneScheduleUID,
)
from custom_components.remeha_modbus.errors import (
    ParseError,
    RemehaModbusError,
)
from custom_components.remeha_modbus.helpers.entities import (
    generate_unique_id,
    get_own_entity_by_unique_id,
    integration_entities,
)


def _set_key_diff[T](left: set[T], right: set[T]) -> set[T]:
    """Return the two-way difference between `left` and `right`."""
    return set((left - right) ^ (right - left))


def compose_scheduler_tag(uuid: UUID) -> str:
    """Compose a schedule tag.

    This tag is used to be able to find a reference to a `scheduler.schedule`
    before an `entity_id` has been assigned to it.

    Args:
        uuid (UUID): The uuid which ensures the tag is unique.

    Returns:
        The composed scheduler tag.

    """

    return f"{SCHEDULER_TAG_PREFIX}{uuid}"


def scheduler_tag_to_uuid(scheduler_tag: str) -> UUID | None:
    """Transform a scheduler tag into a `UUID`.

    Args:
        scheduler_tag (str): The scheduler tag to transform

    Returns:
        The scheduler tag transformed to a v4 `UUID`, or `None` if the scheduler
        tag is not prefxed with `SCHEDULER_TAG_PREFIX`.

    Raises:
        `ValueError` if the `UUID` string is invalid.

    """

    if scheduler_tag.startswith(SCHEDULER_TAG_PREFIX):
        return UUID(hex=scheduler_tag.replace(SCHEDULER_TAG_PREFIX, ""), version=4)

    return None


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


def to_zone_schedule(state: SchedulerState, uid: ZoneScheduleUID) -> ZoneSchedule:
    """Convert the given state to a `ZoneSchedule` instance.

    Args:
        state (SchedulerState): The scheduler state.
        uid (ZoneScheduleUID): The unique identification of the zone schedule.

    Returns:
        ZoneSchedule: The zone schedule

    Raises:
        ParseError: if `state` cannot be converted into a ZoneSchedule.

    """

    def _to_time_slot(idx: int, time_slot: str) -> Timeslot:
        parts = [s.strip() for s in time_slot.split("-")]
        if len(parts) != 2:
            raise ParseError(
                translation_domain=DOMAIN,
                translation_key="parse_error_time_slot",
                translation_placeholders={
                    "schedule_entity_id": state["entity_id"],
                    "time_slot": time_slot,
                    "part_count": str(len(parts)),
                },
            )

        scheduler_action: SchedulerStateAction = state["attributes"]["actions"][idx]
        if (
            scheduler_action["service"] == "climate.set_preset_mode"
            and "preset_mode" in scheduler_action["data"]
        ):
            return Timeslot(
                setpoint_type=TimeslotSetpointType[scheduler_action["data"]["preset_mode"].upper()],
                activity=TimeslotActivity.DHW,
                switch_time=datetime.strptime(parts[0], "%H:%M:%S").time(),
            )

        raise ParseError(
            translation_domain=DOMAIN,
            translation_key="parse_error_scheduler_state_action",
            translation_placeholders={"schedule_entity_id": state["entity_id"]},
        )

    if len(state["attributes"]["weekdays"]) == 1:
        weekday: Weekday = SHORT_DESC_TO_WEEKDAY[state["attributes"]["weekdays"][0]]
        time_slots: list[Timeslot] = [
            _to_time_slot(idx=idx, time_slot=time_slot)
            for (idx, time_slot) in enumerate(state["attributes"]["timeslots"])
        ]

        return ZoneSchedule(
            id=uid.schedule_id, zone_id=uid.zone_id, day=weekday, time_slots=time_slots
        )

    raise ParseError(
        translation_domain=DOMAIN,
        translation_key="parse_error_multiple_weekdays",
        translation_placeholders={"schedule_entity_id": state["entity_id"]},
    )


def _to_schedule_name(schedule: ZoneSchedule) -> str:
    return f"zone_{schedule.zone_id}_{schedule.id.name.lower()}_{schedule.day.name.lower()}"


def _get_durations(schedule: ZoneSchedule):
    time_slots = schedule.time_slots
    for idx, ts in enumerate(time_slots):
        if idx == len(time_slots) - 1:
            # Calculate the time delta until tomorrow.
            yield ts, timedelta(hours=24 - ts.switch_time.hour)
        else:
            next_ts: Timeslot = time_slots[idx + 1]
            yield ts, timedelta(hours=next_ts.switch_time.hour - ts.switch_time.hour)


def _to_dhw_preset_mode(setpoint_type: TimeslotSetpointType) -> str:
    if setpoint_type is TimeslotSetpointType.ECO:
        return PRESET_ECO
    if setpoint_type is TimeslotSetpointType.COMFORT:
        return PRESET_COMFORT

    return PRESET_NONE


def _to_new_scheduler_schedule(
    schedule: ZoneSchedule, linking_tag: UUID, data: SchedulerSchedule
) -> SchedulerSchedule:
    data[ATTR_SCHEDULER_NAME] = _to_schedule_name(schedule=schedule)

    # When creating a new schedule, a unique tag is added so it can be identified
    # when the new-schedule-event is received. It can then be linked to the correct modbus schedule.
    # This tag can be removed afterward.
    data[ATTR_SCHEDULER_TAGS] = [compose_scheduler_tag(linking_tag), DOMAIN]

    return data


def _to_edited_scheduler_schedule(
    linked_scheduler_entity: str, data: SchedulerSchedule
) -> SchedulerSchedule:
    data["entity_id"] = linked_scheduler_entity

    return data


async def to_scheduler_schedule(
    hass: HomeAssistant,
    schedule: ZoneSchedule,
    operation: ServiceOperation,
    linked_scheduler_entity: str | None = None,
    linking_tag: UUID | None = None,
) -> SchedulerSchedule:
    """Convert the given `ZoneSchedule` to a `scheduler.schedule`.

    The returned dict is usable in the `scheduler.add` service call.

    Args:
        hass (HomeAssistant): The HA instance.
        schedule (ZoneSchedule): The schedule to convert.
        operation (ServiceOperation): The type of service to call on the scheduler component.
        linked_scheduler_entity (str | None): The linked scheduler entity. Only required if `operation` is `EDIT`.
        linking_tag (UUID | None): The tag to use to link the `scheduler.schedule` to our `climate` entity. Only required if `operation` is `ADD`.

    Raises:
        `ParseError` if parsing `schedule` to a `SchedulerSchedule` fails.

    Returns:
        The converted `SchedulerSchedule`.

    """

    durations: dict[Timeslot, timedelta] = dict(_get_durations(schedule=schedule))
    climate_entity_id = get_own_entity_by_unique_id(
        hass, ClimateDomain, generate_unique_id(schedule)
    )
    if climate_entity_id is None:
        raise ParseError(translation_domain=DOMAIN, translation_key="parse_error_entity_not_found")

    data = SchedulerSchedule(
        weekdays=[WEEKDAY_TO_SHORT_DESC[schedule.day]],
        repeat_type="repeat",
        timeslots=[
            SchedulerTimeslot(
                start=ts.switch_time.strftime("%H:%M:%S"),
                stop=time(
                    hour=int((ts.switch_time.hour + (durations[ts].seconds / 3600)) % 24)
                ).strftime("%H:%M:%S"),
                conditions=[
                    SchedulerCondition(
                        entity_id=f"{SwitchDomain}.{HEATPUMP_MANAGED_SCHEDULES}",
                        value=STATE_OFF,
                        match_type="is",
                        attribute="state",
                    )
                ],
                condition_type="and",
                actions=[
                    SchedulerAction(
                        entity_id=climate_entity_id,
                        service=f"{ClimateDomain}.set_preset_mode",
                        service_data={
                            "preset_mode": _to_dhw_preset_mode(setpoint_type=ts.setpoint_type)
                        },
                    )
                ],
            )
            for ts in schedule.time_slots
        ],
    )

    match operation:
        case ServiceOperation.EDIT:
            return _to_edited_scheduler_schedule(
                linked_scheduler_entity=cast(str, linked_scheduler_entity), data=data
            )
        case ServiceOperation.ADD:
            return _to_new_scheduler_schedule(
                schedule=schedule, linking_tag=cast(UUID, linking_tag), data=data
            )


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


def scheduler_is_installed(hass: HomeAssistant) -> bool:
    """Return whether the `scheduler` integration has been installed.

    Args:
        hass (HomeAssistant): The current Home Assistant instance.

    """

    return SchedulerDomain in hass.config.components


def get_updated_dhw_schedules(
    old: dict[int, ClimateZone], new: dict[int, ClimateZone]
) -> list[ZoneSchedule]:
    """Return all updated `ZoneSchedule`s of the DHW zones.

    Both `old` and `new` are allowed to contain `ClimateZone`s that are not DHW,
    but those zones will not be considered here.

    Args:
        old: The old climate zones indexed by their id.
        new: The possibly updated climate zones indexed by their id.

    Returns:
        A list containing all new and updated `ZoneSchedule` instances, or an
        empty list if either `old` or `new` is `None`.

    Raises:
        RemehaModbusError if `old` and `new` don't have the exact same keys.

    """

    if old is None or new is None:
        return []

    # Keys from old and new must be the same. This would otherwise indicate
    # the a zone has been added at the Remeha appliance.
    # Handling that scenario is not yet supported.  A workaround is to restart
    # HA after a climate zone has been added.
    key_diff = _set_key_diff(set(old.keys()), set(new.keys()))
    if len(key_diff) > 0:
        raise RemehaModbusError(
            translation_domain=DOMAIN,
            translation_key="schedule_update_non_equal_climates",
        )

    updated_new_schedules: list[ZoneSchedule] = []
    for key, old_zone in old.items():
        new_zone: ClimateZone = new[key]

        # We only support DHW zone schedule synchronization at this time.
        if new_zone.is_domestic_hot_water():
            # Either both zones have a selected schedule,
            if old_zone.selected_schedule is not None and new_zone.selected_schedule is not None:
                updated_new_schedules += [
                    schedule
                    for key, schedule in new_zone.current_schedule.items()
                    if old_zone.current_schedule[key] != schedule and schedule is not None
                ]
            # or, the old zone didn't have a schedule yet and a new one was created.
            elif new_zone.selected_schedule is not None:
                updated_new_schedules += [
                    schedule
                    for schedule in new_zone.current_schedule.values()
                    if schedule is not None
                ]

    return updated_new_schedules
