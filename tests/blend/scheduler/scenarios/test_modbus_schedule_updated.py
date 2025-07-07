"""Tests for the `modbus_schedule_updated` scenario."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.template import integration_entities
from pydantic import TypeAdapter, ValidationError

from custom_components.remeha_modbus.api import ZoneSchedule
from custom_components.remeha_modbus.blend.scheduler.scenarios.modbus_schedule_updated import (
    ModbusScheduleUpdated,
)
from custom_components.remeha_modbus.const import SchedulerSchedule, Weekday
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.scheduler.const import DOMAIN as SchedulerDomain
from tests.conftest import get_api, setup_platform
from tests.util import set_storage_stub_return_value


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_schedule_created(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    expected_lingering_timers,
):
    """Test that a newly created `scheduler.schedule` is pushed correctly to the modbus interface."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
        patch(
            "custom_components.remeha_modbus.api.RemehaModbusStore.create",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
        patch("custom_components.scheduler.store.ScheduleStorage") as scheduler_storage,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # hass is set up, patch the async_get_registry-mock
        set_storage_stub_return_value(hass=hass, scheduler_storage=scheduler_storage)

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        schedule: ZoneSchedule = coordinator.get_climate(id=2).current_schedule[Weekday.MONDAY]
        scenario: ModbusScheduleUpdated = ModbusScheduleUpdated(
            hass=hass, coordinator=coordinator, schedule=schedule
        )

        # Expect no existing links and scheduler.schedule entities.
        assert len(await coordinator.async_get_scheduler_links()) == 0
        assert len(integration_entities(hass=hass, entry_name="scheduler")) == 0

        # Execute the scenario
        await scenario.async_execute()
        await hass.async_block_till_done()

        # Retrieve the list of service calls to `scheduler.add`
        service_call_list = hass.data[SchedulerDomain]["get_call_logs"]("add")
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

        assert len(integration_entities(hass=hass, entry_name="scheduler")) == 1
