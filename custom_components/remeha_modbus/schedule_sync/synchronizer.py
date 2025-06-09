"""Implementation of schedule synchronization."""

import logging
from datetime import time, timedelta
from enum import StrEnum
from typing import Final

from homeassistant.components.climate.const import PRESET_COMFORT, PRESET_ECO, PRESET_NONE
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.api import (
    ClimateZone,
    Timeslot,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.const import (
    DOMAIN,
    PUSH_SCHEDULE_REQUIRED_DOMAIN_NAME,
    PUSH_SCHEDULE_REQUIRED_SERVICES,
    SWITCH_EXECUTE_SCHEDULING_ACTIONS,
    Weekday,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import RequiredServiceMissing

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


class ServiceOperation(StrEnum):
    """Enumerate the required service operation to store a schedule."""

    ADD = "add"
    """The schedule does not exist in the service, so it must be added."""
    EDIT = "edit"
    """The schedule already exists in the service, so it must be edited."""


class ScheduleSynchronizer:
    """Synchronization of schedules between this integration and other HA scheduling services."""

    def __init__(self, hass: HomeAssistant, coordinator: RemehaUpdateCoordinator):
        """Create a new synchronizer instance."""

        self._hass: HomeAssistant = hass
        self._coordinator: RemehaUpdateCoordinator = coordinator

    def _to_schedule_name(self, schedule: ZoneSchedule) -> str:
        return f"zone_{schedule.zone_id}_{schedule.id.name.lower()}_{schedule.day.name.lower()}"

    def _to_entity_id(self, schedule: ZoneSchedule) -> str:
        return f"switch.schedule_{self._to_schedule_name(schedule=schedule)}"

    async def _get_service_operation(self, schedule: ZoneSchedule) -> ServiceOperation:
        return (
            ServiceOperation.ADD
            if self._hass.states.get(entity_id=self._to_entity_id(schedule=schedule)) is None
            else ServiceOperation.EDIT
        )

    def _get_durations(self, schedule: ZoneSchedule):
        time_slots = schedule.time_slots
        for idx, ts in enumerate(time_slots):
            if idx == len(time_slots) - 1:
                # Calculate the time delta until tomorrow.
                yield ts, timedelta(hours=24 - ts.switch_time.hour)
            else:
                next_ts: Timeslot = time_slots[idx + 1]
                yield ts, timedelta(hours=next_ts.switch_time.hour - ts.switch_time.hour)

    def _to_preset_mode(self, type: TimeslotSetpointType) -> str:
        if type is TimeslotSetpointType.ECO:
            return PRESET_ECO
        if type is TimeslotSetpointType.COMFORT:
            return PRESET_COMFORT

        return PRESET_NONE

    def _to_service_data(self, schedule: ZoneSchedule, operation: ServiceOperation) -> dict:
        durations: dict[Timeslot, timedelta] = dict(self._get_durations(schedule=schedule))
        zone: ClimateZone = self._coordinator.get_climate(id=schedule.zone_id)

        data = {
            "name": self._to_schedule_name(schedule=schedule),
            "weekdays": [WEEKDAY_TO_SHORT_DESC[schedule.day]],
            "repeat_type": "repeat",
            "timeslots": [
                {
                    "start": ts.switch_time.strftime("%H:%M:%S"),
                    "stop": time(
                        hour=int((ts.switch_time.hour + (durations[ts].seconds / 3600)) % 24)
                    ).strftime("%H:%M:%S"),
                    "conditions": [
                        {
                            "entity_id": f"switch.{SWITCH_EXECUTE_SCHEDULING_ACTIONS}",
                            "value": "on",
                            "match_type": "is",
                        }
                    ],
                    "actions": [
                        {
                            "entity_id": f"climate.{DOMAIN}_{zone.short_name}",
                            "service": "climate.set_preset_mode",
                            "service_data": {
                                "preset_mode": self._to_preset_mode(type=ts.setpoint_type)
                            },
                        }
                    ],
                }
                for ts in schedule.time_slots
            ],
        }

        if operation == ServiceOperation.EDIT:
            data |= {"entity_id": self._to_entity_id(schedule=schedule)}

        return data

    async def async_push_schedule(self, schedule: ZoneSchedule) -> str:
        """Push the given schedule to the scheduler service.

        If the schedule already exists, it is updated. Otherwise, it is created.

        Args:
          schedule (ZoneSchedule): The schedule to push.

        Returns:
          str: The entity id of the created (or updated) schedule.

        """

        services: dict | None = self._hass.services.async_services_for_domain(
            PUSH_SCHEDULE_REQUIRED_DOMAIN_NAME
        )

        if not services or not services.keys() & PUSH_SCHEDULE_REQUIRED_SERVICES:
            raise RequiredServiceMissing(
                translation_domain=DOMAIN, translation_key="push_schedule_missing_services"
            )

        operation: ServiceOperation = await self._get_service_operation(schedule=schedule)

        data = self._to_service_data(schedule=schedule, operation=operation)

        await self._hass.services.async_call(
            domain=PUSH_SCHEDULE_REQUIRED_DOMAIN_NAME,
            service=str(operation),
            blocking=False,
            return_response=False,
            service_data=data,
        )
