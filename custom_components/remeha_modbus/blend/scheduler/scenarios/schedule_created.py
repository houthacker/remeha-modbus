"""Implementation of schenario 1 where a new `scheduler.schedule` is created."""

import logging
from datetime import datetime
from typing import Final, override
from uuid import UUID

from homeassistant.core import HomeAssistant, State

from custom_components.remeha_modbus.api import (
    ClimateZone,
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.api.store import WaitingListEntry
from custom_components.remeha_modbus.blend.scheduler.scenario import Scenario
from custom_components.remeha_modbus.const import (
    ATTR_ZONE_ID,
    SCHEDULER_TAG_PREFIX,
    ClimateZoneScheduleId,
    SchedulerState,
    SchedulerStateAction,
    Weekday,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.helpers.validation import require_not_none

_LOGGER = logging.getLogger(__name__)

WEEKDAY_TO_SHORT_DESC: Final[dict[Weekday, str]] = {
    Weekday.MONDAY: "mon",
    Weekday.TUESDAY: "tue",
    Weekday.WEDNESDAY: "wed",
    Weekday.THURSDAY: "thu",
    Weekday.FRIDAY: "fri",
    Weekday.SATURDAY: "sat",
    Weekday.SUNDAY: "sun",
}

SHORT_DESC_TO_WEEKDAY: Final[dict[str, Weekday]] = {
    WEEKDAY_TO_SHORT_DESC[day]: day for day in Weekday
}


def _get_tag_uuid(schedule: SchedulerState) -> UUID | None:
    """Return the uuid in the schedule tag, or `None` if no such tag exists."""

    stripped_tag: str | None = next(
        iter(
            [
                tag.removeprefix(SCHEDULER_TAG_PREFIX)
                for tag in schedule["attributes"].get("tags", [])
                if tag.startswith(SCHEDULER_TAG_PREFIX)
            ]
        ),
        None,
    )

    return UUID(stripped_tag) if stripped_tag is not None else None


def _to_zone_schedule(
    state: SchedulerState, zone_id: int, schedule_id: ClimateZoneScheduleId
) -> ZoneSchedule:
    """Create a `ZoneSchedule` based on the given entity state.

    The given state must have a domain of `switch` and adhere to the state format
    of a `scheduler.schedule` instance.

    Args:
        state (SchedulerState): The scheduler state.
        zone_id (int): The id of the linked `ClimateZone`.
        schedule_id (ClimateZoneScheduleId): The id of the schedule in the `ClimateZone`.

    Returns:
        ZoneSchedule: The zone schedule.

    Raises:
        ValueError: if the state cannot be parsed to a ZoneSchedule.

    """

    def _to_time_slot(idx: int, time_slot: str) -> Timeslot:
        parts = [s.strip() for s in time_slot.split("-")]
        if len(parts) != 2:
            raise ValueError("Cannot parse timeslot string [%s] in exactly two parts.", time_slot)

        related_action: SchedulerStateAction = state["attributes"]["actions"][idx]
        if (
            related_action["service"] == "climate.set_preset_mode"
            and "preset_mode" in related_action["data"]
        ):
            return Timeslot(
                setpoint_type=TimeslotSetpointType[related_action["data"]["preset_mode"].upper()],
                activity=TimeslotActivity.DHW,
                switch_time=datetime.strptime(parts[0], "%H:%M:%S").time(),
            )

        raise ValueError("Invalid SchedulerStateAction")

    if len(state["attributes"]["weekdays"]) == 1:
        weekday: Weekday = SHORT_DESC_TO_WEEKDAY[state["attributes"]["weekdays"][0]]
        time_slots: list[Timeslot] = [
            _to_time_slot(idx=idx, time_slot=time_slot)
            for (idx, time_slot) in enumerate(state["attributes"]["timeslots"])
        ]

        return ZoneSchedule(id=schedule_id, zone_id=zone_id, day=weekday, time_slots=time_slots)

    raise ValueError(
        "Cannot parse ZoneSchedule from SchedulerState: require exactly 1 weekdays, got %d",
        len(state["attributes"]["weekdays"]),
    )


class ScheduleCreated(Scenario):
    """Handle a newly created `scheduler.schedule`.

    When a new schedule is created in the `scheduler` integration, and it is exclusively linked
    to a `remeha_modbus` climate, it is converted to its modbus counterpart, `ZoneSchedule`.

    The link between these schedules is then stored in a JSON file named to the value of `const.STORAGE_FILE_KEY`,
    so this information will survive HA reboots etc. This allows updating the schedule in either direction if the
    other end was updated or removed.

    """

    def __init__(
        self, hass: HomeAssistant, schedule: SchedulerState, coordinator: RemehaUpdateCoordinator
    ):
        """Create a new scenario instance for the given event.

        Args:
            hass (HomeAssistant): The current Home Assistant instance.
            schedule (SchedulerState): The new schedule state.
            coordinator (RemehaUpdateCoordinator): The coordinator responsible for storing schedule links.

        """

        self._hass: HomeAssistant = hass
        self._schedule: SchedulerState = schedule
        self._coordinator: RemehaUpdateCoordinator = coordinator

    @override
    async def async_execute(self) -> None:
        """Push the schedule to the modbus interface.

        If the schedule was created manually using the scheduler frontend, it is linked
        and written to the modbus interface. The link is created between the `scheduler.schedule`
        and the currently selected schedule in the related `ClimateZone`. If no schedule is selected,
        the first schedule is used.

        Otherwise, the schedule was created due to a new schedule being retrieved from the
        modbus interface. The only task left is then to link both schedules.

        *Note*: This scenario assumes that the provided `SchedulerState` is valid for use in this method.
        This is ensured by the `Blender` that executes this scenario.

        Raises:
            ValueError: if the schedule is created due to a newly retrieved schedule from the modbus interface,
                    and no linking information is present on the waiting list.
            ValueError: if the related `ClimateZone` does not exist.
            ValueError: if any `SchedulerState` attribute value cannot be parsed into its `ZoneSchedule` counterpart.

        """

        uuid: UUID | None = _get_tag_uuid(self._schedule)

        if uuid is not None:
            # If the schedule is tagged, an entry must exist on the waiting list.
            entry: WaitingListEntry = require_not_none(
                self._coordinator.pop_from_linking_waiting_list(uuid=uuid),
                "Newly created scheduler.schedule %s contains a tag, but no link with a ZoneSchedule can be created.",
                self._schedule["entity_id"],
            )

            # Store the link between the schedules.
            await self._coordinator.async_link_scheduler_entity(
                zone_id=entry.zone_id,
                schedule_id=entry.schedule_id,
                weekday=entry.weekday,
                entity_id=self._schedule["entity_id"],
            )
        else:
            # If the schedule is not tagged (i.e. created manually in the scheduler UI), create a link based on the
            # currently selected climate schedule.
            climate_state: State = self._hass.states.get(
                entity_id=self._schedule["attributes"]["entities"][0]
            )
            zone_id: int = int(climate_state.attributes[ATTR_ZONE_ID])
            zone: ClimateZone = require_not_none(
                self._coordinator.get_climate(id=zone_id),
                "scheduler.schedule is related to ClimateZone(id=%d), but no such zone exists.",
                zone_id,
            )
            schedule_id: ClimateZoneScheduleId = zone.selected_schedule
            if schedule_id is None:
                _LOGGER.debug(
                    "ClimateZone(id=%d) has no selected schedule; linking to SCHEDULE_1.",
                    zone_id,
                )
                schedule_id = ClimateZoneScheduleId.SCHEDULE_1

            zone_schedule: ZoneSchedule = _to_zone_schedule(
                state=self._schedule, zone_id=zone_id, schedule_id=schedule_id
            )

            # Push the ZoneSchedule to the modbus interface.
            # TODO If writing fails, reschedule it right after the next successful coordinator update.
            await self._coordinator.async_write_schedule(schedule=zone_schedule)
            await self._coordinator.async_link_scheduler_entity(
                zone_id=zone_id,
                schedule_id=schedule_id,
                entity_id=self._schedule["entity_id"],
                weekday=SHORT_DESC_TO_WEEKDAY[self._schedule["attributes"]["weekdays"][0]],
            )
