"""Implementation of scenario 4 where an updated modbus schedule is synced with a scheduler.schedule, if linked."""

from datetime import time, timedelta
from enum import StrEnum
from typing import Final, override
from uuid import UUID, uuid4

from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.api import (
    ClimateZone,
    Timeslot,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.blend.scheduler.scenario import Scenario
from custom_components.remeha_modbus.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SCHEDULER_TAG_PREFIX,
    SWITCH_EXECUTE_SCHEDULING_ACTIONS,
    SchedulerAction,
    SchedulerCondition,
    SchedulerSchedule,
    SchedulerTimeslot,
    Weekday,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator


class ServiceOperation(StrEnum):
    """Enumerate the required service operation to store a schedule."""

    ADD = "add"
    """The schedule does not exist in the service, so it must be added."""
    EDIT = "edit"
    """The schedule already exists in the service, so it must be edited."""


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


def _get_durations(schedule: ZoneSchedule):
    time_slots = schedule.time_slots
    for idx, ts in enumerate(time_slots):
        if idx == len(time_slots) - 1:
            # Calculate the time delta until tomorrow.
            yield ts, timedelta(hours=24 - ts.switch_time.hour)
        else:
            next_ts: Timeslot = time_slots[idx + 1]
            yield ts, timedelta(hours=next_ts.switch_time.hour - ts.switch_time.hour)


def _to_preset_mode(setpoint_type: TimeslotSetpointType) -> str:
    if setpoint_type is TimeslotSetpointType.ECO:
        return PRESET_ECO
    if setpoint_type is TimeslotSetpointType.COMFORT:
        return PRESET_COMFORT

    return PRESET_NONE


def _to_schedule_name(schedule: ZoneSchedule) -> str:
    return f"zone_{schedule.zone_id}_{schedule.id.name.lower()}_{schedule.day.name.lower()}"


class ModbusScheduleUpdated(Scenario):
    """Handle an updated schedule from the modbus interface."""

    def __init__(
        self, hass: HomeAssistant, coordinator: RemehaUpdateCoordinator, schedule: ZoneSchedule
    ):
        """Create a new `ModbusScheduleUpdated`."""

        self._hass: HomeAssistant = hass
        self._coordinator: RemehaUpdateCoordinator = coordinator
        self._schedule: ZoneSchedule = schedule

    async def _to_scheduler_schedule(
        self,
        schedule: ZoneSchedule,
        operation: ServiceOperation,
        linked_scheduler_entity: str | None = None,
        linking_tag: UUID | None = None,
    ) -> SchedulerSchedule:
        durations: dict[Timeslot, timedelta] = dict(_get_durations(schedule=schedule))
        zone: ClimateZone = self._coordinator.get_climate(id=schedule.zone_id)
        climate_entity = next(
            iter(
                [
                    state
                    for state in self._hass.states.async_all(domain_filter="climate")
                    if state.attributes.get("zone_id") == zone.id
                ]
            )
        )

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
                            entity_id=f"switch.{SWITCH_EXECUTE_SCHEDULING_ACTIONS}",
                            value="on",
                            match_type="is",
                            attribute="state",
                        )
                    ],
                    condition_type="and",
                    actions=[
                        SchedulerAction(
                            entity_id=climate_entity.entity_id,
                            service="climate.set_preset_mode",
                            service_data={
                                "preset_mode": _to_preset_mode(setpoint_type=ts.setpoint_type)
                            },
                        )
                    ],
                )
                for ts in schedule.time_slots
            ],
        )

        if operation == ServiceOperation.EDIT:
            data["entity_id"] = linked_scheduler_entity
        elif operation == ServiceOperation.ADD:
            # Name must only be set when creating a new schedule.
            data["name"] = _to_schedule_name(schedule=schedule)

            # When creating a new schedule, a unique tag is added so it can be identified
            # when the new-schedule-event is received. It can then be linked to the correct modbus schedule.
            # This tag can be removed afterward.
            data["tags"] = [f"{SCHEDULER_TAG_PREFIX}{linking_tag}"]

        return data

    @override
    async def async_execute(self) -> None:
        """Update the linked `scheduler.schedule` if the updated `ZoneSchedule` is different from it.

        If a linked `scheduler.schedule` already exists, update it. Otherwise create a new linked one.
        """

        scheduler_entity: str | None = await self._coordinator.async_get_linked_scheduler_entity(
            zone_id=self._schedule.zone_id,
            schedule_id=self._schedule.id,
            weekday=self._schedule.day,
        )

        is_new_schedule: bool = scheduler_entity is None
        if is_new_schedule:
            operation: ServiceOperation = ServiceOperation.ADD
            uuid: UUID = uuid4()

            # Put a scheduler<->remeha_modbus schedule link on the waiting list.
            # That way, when the schedule is created and the corresponding
            # scenario (`schedule_created`) is executed, we can break the cycle
            # by just removing the link from the waiting list and storing it then
            # and not sending the update to modbus.
            self._coordinator.enqueue_for_linking(
                uuid=uuid,
                zone_id=self._schedule.zone_id,
                schedule_id=self._schedule.id,
                weekday=self._schedule.day,
            )

            await self._hass.services.async_call(
                domain="scheduler",
                service=str(operation),
                blocking=False,
                return_response=False,
                service_data=await self._to_scheduler_schedule(
                    schedule=self._schedule, operation=operation, linking_tag=uuid
                ),
            )
        else:
            operation: ServiceOperation = ServiceOperation.EDIT

            await self._hass.services.async_call(
                domain="scheduler",
                service=str(operation),
                blocking=False,
                return_response=False,
                service_data=await self._to_scheduler_schedule(
                    schedule=self._schedule,
                    operation=operation,
                    linked_scheduler_entity=scheduler_entity,
                ),
            )
