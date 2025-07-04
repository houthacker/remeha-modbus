"""Implementation of scenario 4 where an updated modbus schedule is synced with a scheduler.schedule, if linked."""

from typing import override

from custom_components.remeha_modbus.blend.scheduler.scenario import Scenario


class ModbusScheduleUpdated(Scenario):
    """Handle an updated schedule from the modbus interface."""

    @override
    async def async_execute(self) -> None:
        """Execute the scenario."""
