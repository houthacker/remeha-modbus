"""Implementation of scenario 4 where a linked `scheduler.schedule` is updated."""

import logging
from typing import override

from homeassistant.core import HomeAssistant, State

from custom_components.remeha_modbus.blend.blender import Scenario
from custom_components.remeha_modbus.blend.scheduler.helpers import (
    to_scheduler_state,
    to_zone_schedule,
)
from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import ScenarioExecutionError

_LOGGER = logging.getLogger(__name__)


class SchedulerScheduleUpdated(Scenario):
    """Handle an updated schedule in the scheduler integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: RemehaUpdateCoordinator,
        schedule_state: State | None,
    ):
        """Create a new SchedulerScheduleUpdated scenario."""
        if schedule_state is None:
            raise ScenarioExecutionError(
                translation_domain=DOMAIN,
                translation_key="scenario_execution_error_missing_required_state",
                translation_placeholders={
                    "scenario": "scheduler_schedule_updated",
                    "component": "scheduler",
                },
            )
        self._hass = hass
        self._coordinator = coordinator
        self._schedule_state = schedule_state

    @override
    async def async_execute(self) -> None:
        """Push an updated `scheduler.schedule` to modbus.

        If the schedule was updated due to a previously updated modbus schedule,
        this update is effectively ignored to prevent a never ending update cycle.

        If the schedule update didn't originate from modbus, the update is pushed
        there.
        """

        if (
            self._coordinator.remove_from_update_waiting_list(self._schedule_state.entity_id)
            is None
        ):
            # The updated schedule must be linked to a ZoneSchedule.
            uid = await self._coordinator.async_get_linked_zone_schedule_uid(
                self._schedule_state.entity_id
            )

            if uid is None:
                _LOGGER.debug(
                    "Ignoring update of scheduler.schedule %s since it's not linked to one of our ZoneSchedules.",
                    self._schedule_state.entity_id,
                )
                return

            # Retrieve the climate
            zone = self._coordinator.get_climate(uid.zone_id)

            # Climate must exist
            if zone is None:
                raise ScenarioExecutionError(
                    translation_domain=DOMAIN,
                    translation_key="scenario_execution_error_missing_climate",
                    translation_placeholders={
                        "scenario": "scheduler_schedule_updated",
                        "scheduler_entity": self._schedule_state.entity_id,
                    },
                )

            # CH zones schedule editing is not supported yet, so our zone here must be a DHW zone.
            # For these zones, only schedule_1 is available through the Remeha Home app is seems.
            zone_schedule = to_zone_schedule(to_scheduler_state(self._schedule_state), uid)

            # Push the ZoneSchedule to the modbus interface.
            await self._coordinator.async_write_schedule(zone_schedule)
