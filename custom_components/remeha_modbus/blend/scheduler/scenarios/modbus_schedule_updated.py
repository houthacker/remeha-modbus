"""Implementation of scenario 1 where an updated modbus schedule is received through modbus."""

from typing import TYPE_CHECKING, Any, cast, override
from uuid import UUID, uuid4

from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.blend import Scenario
from custom_components.remeha_modbus.blend.scheduler.const import (
    SchedulerDomain,
    ScheduleUpdate,
    ServiceOperation,
)
from custom_components.remeha_modbus.blend.scheduler.helpers import to_scheduler_schedule
from custom_components.remeha_modbus.const import (
    ZoneScheduleUID,
)

if TYPE_CHECKING:
    from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator


class ModbusScheduleUpdated(Scenario):
    """Handle an updated schedule from the modbus interface."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: RemehaUpdateCoordinator,
        update: ScheduleUpdate,
    ):
        """Create a new `ModbusScheduleUpdated`."""

        self._hass: HomeAssistant = hass
        self._coordinator: RemehaUpdateCoordinator = coordinator
        self._update: ScheduleUpdate = update

    @override
    async def async_execute(self) -> None:
        """Update the linked `scheduler.schedule` if the updated `ZoneSchedule` is different from it.

        If a linked `scheduler.schedule` already exists, update it. Otherwise create a new linked one.
        """

        scheduler_entity: str | None = await self._coordinator.async_get_linked_scheduler_entity(
            uid=ZoneScheduleUID(
                zone_id=self._update.zone_id,
                schedule_id=self._update.schedule_id,
                weekday=self._update.day,
            ),
        )

        operation: ServiceOperation
        is_new_schedule: bool = scheduler_entity is None
        if is_new_schedule:
            operation = ServiceOperation.ADD
            uuid: UUID = uuid4()

            # Put a scheduler<->remeha_modbus schedule link on the waiting list.
            # That way, when the schedule is created and the corresponding
            # scenario (schedule_created) is executed, we can break the cycle
            # by just removing the link from the waiting list and storing it then
            # and not sending the update to modbus.
            self._coordinator.enqueue_for_linking(
                uuid=uuid,
                zone_schedule_uid=ZoneScheduleUID(
                    zone_id=self._update.zone_id,
                    schedule_id=self._update.schedule_id,
                    weekday=self._update.day,
                ),
            )

            await self._hass.services.async_call(
                domain=SchedulerDomain,
                service=str(operation),
                blocking=False,
                return_response=False,
                service_data=cast(
                    dict[str, Any],
                    await to_scheduler_schedule(
                        hass=self._hass,
                        day=self._update.day,
                        schedule_id=self._update.schedule_id,
                        time_slots=self._update.time_slots,
                        operation=operation,
                        linking_tag=uuid,
                    ),
                ),
            )
        else:
            operation = ServiceOperation.EDIT

            # Put a scheduler<->remeha_modbus schedule link on the waiting list for updates.
            # That way, when the schedule is updated and the corresponding
            # scenario (scenario_updated) is executed, it breaks the update cycle by just
            # removing the link from the waiting list. If it's not on the waiting list, the
            # update originated from the scheduler component itself and the update is pushed
            # to modbus.
            self._coordinator.notify_of_modbus_sourced_update(entity_id=scheduler_entity)

            await self._hass.services.async_call(
                domain=SchedulerDomain,
                service=str(operation),
                blocking=False,
                return_response=False,
                service_data=cast(
                    dict[str, Any],
                    await to_scheduler_schedule(
                        hass=self._hass,
                        day=self._update.day,
                        schedule_id=self._update.schedule_id,
                        time_slots=self._update.time_slots,
                        operation=operation,
                        linked_scheduler_entity=scheduler_entity,
                    ),
                ),
            )
