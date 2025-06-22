"""Tests for synchronization between scheduler.schedule entities and the Remeha modbus interface."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from pydantic import TypeAdapter, ValidationError

from custom_components.remeha_modbus import RemehaUpdateCoordinator
from custom_components.remeha_modbus.api import ZoneSchedule
from custom_components.remeha_modbus.const import (
    DOMAIN,
    IMPORT_SCHEDULE_CLIMATE_ENTITY,
    IMPORT_SCHEDULE_SERVICE_NAME,
    IMPORT_SCHEDULE_WEEKDAY,
    SchedulerSchedule,
    Weekday,
)
from custom_components.remeha_modbus.schedule_sync.synchronizer import (
    to_scheduler_state,
)
from custom_components.scheduler.const import DOMAIN as SchedulerDomain
from custom_components.scheduler.switch import ScheduleEntry
from tests.conftest import get_api, setup_platform
from tests.util import set_storage_stub_return_value


async def test_to_scheduler_state(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test available sensors."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        climate_state = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")

        # A climate is not a scheduler.schedule
        with pytest.raises(expected_exception=ValidationError):
            to_scheduler_state(state=climate_state)


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_import_schedule(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, expected_lingering_timers
):
    """Test that a schedule can be added by the synchronizer."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
        patch("custom_components.scheduler.store.ScheduleStorage") as scheduler_storage,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # hass is set up, patch the async_get_registry-mock
        set_storage_stub_return_value(hass=hass, scheduler_storage=scheduler_storage)

        # Retrieve the list of service calls to `scheduler.add`
        service_call_list = hass.data[SchedulerDomain]["get_call_logs"]("add")
        assert service_call_list == []

        # Call the import service.
        await hass.services.async_call(
            domain=DOMAIN,
            service=IMPORT_SCHEDULE_SERVICE_NAME,
            service_data={
                IMPORT_SCHEDULE_CLIMATE_ENTITY: "climate.remeha_modbus_test_hub_dhw",
                IMPORT_SCHEDULE_WEEKDAY: "monday",
            },
        )

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


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_export_schedule(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, expected_lingering_timers
):
    """Test that a schedule can be edited by the synchronizer."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
        patch("custom_components.scheduler.store.ScheduleStorage") as scheduler_storage,
    ):
        created_schedules: list[ScheduleEntry] = []
        edited_schedules: list[ScheduleEntry] = []

        await setup_platform(
            hass=hass,
            config_entry=mock_config_entry,
            add_schedule_callback=created_schedules.append,
            edit_schedule_callback=edited_schedules.append,
        )
        await hass.async_block_till_done()

        # hass is set up, patch the async_get_registry-mock
        set_storage_stub_return_value(hass=hass, scheduler_storage=scheduler_storage)

        # Retrieve the list of service calls
        add_call_log = hass.data[SchedulerDomain]["get_call_logs"]("add")
        edit_call_log = hass.data[SchedulerDomain]["get_call_logs"]("edit")
        assert edit_call_log == []

        # Create a remeha modbus schedule.
        await hass.services.async_call(
            domain=DOMAIN,
            service=IMPORT_SCHEDULE_SERVICE_NAME,
            service_data={
                IMPORT_SCHEDULE_CLIMATE_ENTITY: "climate.remeha_modbus_test_hub_dhw",
                IMPORT_SCHEDULE_WEEKDAY: "monday",
            },
        )
        assert len(add_call_log) == 1
        assert len(created_schedules) == 1
        await hass.async_block_till_done()

        # Update the scheduler.schedule.
        schedule_entry: ScheduleEntry = next(iter(created_schedules))
        schedule_entity_id: str = hass.data[SchedulerDomain]["schedules"][
            schedule_entry.schedule_id
        ]
        await hass.services.async_call(
            domain=SchedulerDomain,
            service="edit",
            service_data={
                "entity_id": schedule_entity_id,
                "timeslots": [
                    {
                        "start": "10:00:00",
                        "stop": "18:00:00",
                        "conditions": [
                            {
                                "attribute": "state",
                                "entity_id": "switch.execute_scheduling_actions",
                                "match_type": "is",
                                "value": "on",
                            }
                        ],
                        "condition_type": "and",
                        "track_conditions": False,
                        "actions": [
                            {
                                "entity_id": "climate.remeha_modbus_test_hub_dhw",
                                "service": "climate.set_preset_mode",
                                "service_data": {
                                    "preset_mode": "comfort",
                                },
                            }
                        ],
                    }
                ],
            },
        )

        assert len(edit_call_log) == 1
        assert len(edited_schedules) == 1

        # Wait for HA to finish exporting the schedule to the modbus interface
        await hass.async_block_till_done(wait_background_tasks=True)
        all_but_me = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        await asyncio.wait(all_but_me)

        # And check if it did change.
        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]

        # Force a re-read from the modbus interface, since refreshes are disabled while testing.
        await coordinator.async_refresh()

        current_schedule = coordinator.get_climate(id=2).current_schedule
        assert current_schedule is not None

        zone_schedule: ZoneSchedule = current_schedule[Weekday.MONDAY]
        assert len(zone_schedule.time_slots) == 1
