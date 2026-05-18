"""Test the scenario where an updated schedule is received through modbus."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from pydantic import TypeAdapter, ValidationError

from custom_components.remeha_modbus.api.climate_zone import ClimateZone
from custom_components.remeha_modbus.api.schedule import ZoneSchedule
from custom_components.remeha_modbus.api.store import RemehaModbusStore
from custom_components.remeha_modbus.blend.scheduler.const import SchedulerDomain, SchedulerSchedule
from custom_components.remeha_modbus.blend.scheduler.scenarios.modbus_schedule_updated import (
    ModbusScheduleUpdated,
)
from custom_components.remeha_modbus.const import Weekday
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.helpers.entities import integration_entities
from tests.conftest import get_api, setup_platform
from tests.util.util import set_storage_stub_return_value


async def test_schedule_updated(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, modbus_test_store: RemehaModbusStore
):
    """Test schedule updates through modbus."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
        patch("custom_components.scheduler.store.ScheduleStorage") as scheduler_storage,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # HA is set up, patch the async_get_registry mock
        set_storage_stub_return_value(
            mock_config_entry=mock_config_entry, scheduler_storage=scheduler_storage
        )

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        climate: ClimateZone | None = coordinator.get_climate(id=2)
        assert climate is not None

        schedule: ZoneSchedule | None = climate.current_schedule[Weekday.MONDAY]
        assert schedule is not None

        scenario = ModbusScheduleUpdated(hass=hass, coordinator=coordinator, schedule=schedule)

        # Expect no existing links and no scheduler entities.
        assert len(await coordinator.async_get_scheduler_links()) == 0
        assert len(list(integration_entities(hass=hass, entry_name=SchedulerDomain))) == 0

        # Execute the scenario
        await scenario.async_execute()
        await hass.async_block_till_done()

        # Retrieve the list of service calls to `scheduler.add`
        service_call_list: list[ServiceCall] = hass.data[SchedulerDomain]["get_call_logs"]("add")
        assert len(service_call_list) == 1
        call: ServiceCall = service_call_list[0]

        # We expect a SchedulerSchedule-like object
        validator = TypeAdapter(SchedulerSchedule)

        try:
            validator.validate_python(call.data)
        except ValidationError as e:
            pytest.fail(
                f"Importing a schedule caused a service call, but the service data is invalid: {e}"
            )

        assert len(list(integration_entities(hass=hass, entry_name=SchedulerDomain))) == 1
