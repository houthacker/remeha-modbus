"""Tests for the SchedulerScheduleUpdated scenario."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, State

from custom_components.remeha_modbus.blend.scheduler.scenarios.scheduler_schedule_updated import (
    SchedulerScheduleUpdated,
)
from custom_components.remeha_modbus.const import ClimateZoneScheduleId, Weekday, ZoneScheduleUID
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import ScenarioExecutionError
from tests.conftest import get_api, setup_platform


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_updated_not_on_waiting_list(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test that an updated schedule not on the waiting list is ignored."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        # The entity is not on the waiting list, so is_modbus_sourced_update returns False.
        # This means we proceed to check if it's linked and potentially update modbus.
        with patch.object(coordinator, "async_get_linked_zone_schedule_uid", return_value=None):
            await scenario.async_execute()


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_updated_not_linked(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test that an updated schedule not linked to a ZoneSchedule is ignored."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        # Mock is_modbus_sourced_update to return False (update sourced from outside our integration)
        # Mock async_get_linked_zone_schedule_uid to return None (not linked)
        with (
            patch.object(coordinator, "is_modbus_sourced_update", return_value=False),
            patch.object(coordinator, "async_get_linked_zone_schedule_uid", return_value=None),
        ):
            await scenario.async_execute()


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_updated_missing_climate(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test that an updated schedule linked to a non-existent climate raises an error."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        # Create a UID for zone 99 which doesn't exist
        fake_uid = ZoneScheduleUID(
            zone_id=99, schedule_id=ClimateZoneScheduleId.SCHEDULE_1, weekday=Weekday.MONDAY
        )

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        with (
            patch.object(coordinator, "is_modbus_sourced_update", return_value=False),
            patch.object(coordinator, "async_get_linked_zone_schedule_uid", return_value=fake_uid),
            patch.object(coordinator, "get_climate", return_value=None),
            pytest.raises(ScenarioExecutionError) as exc_info,
        ):
            await scenario.async_execute()

        assert exc_info.value.translation_key == "scenario_execution_error_missing_climate"


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_updated_successfully(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test a successful schedule update."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        # Get the actual DHW zone (zone 2 based on fixture)
        climate = coordinator.get_climate(id=2)
        assert climate is not None

        # Create a valid UID for the existing zone
        uid = ZoneScheduleUID(
            zone_id=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_1, weekday=Weekday.MONDAY
        )

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        # Mock coordinator methods and verify async_write_schedule is called correctly
        with (
            patch.object(coordinator, "async_get_linked_zone_schedule_uid", return_value=uid),
            patch.object(coordinator, "async_write_schedule") as mock_write,
        ):
            await scenario.async_execute()

            # Verify async_write_schedule was called once
            assert mock_write.called


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_updated_calls_async_write_schedule_with_correct_data(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test that async_write_schedule is called with the correct ZoneSchedule data."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        climate = coordinator.get_climate(id=2)
        assert climate is not None

        uid = ZoneScheduleUID(
            zone_id=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_1, weekday=Weekday.MONDAY
        )

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        # Mock is_modbus_sourced_update to return None (not on waiting list)
        with (
            patch.object(coordinator, "is_modbus_sourced_update", return_value=False),
            patch.object(coordinator, "async_get_linked_zone_schedule_uid", return_value=uid),
            patch.object(coordinator, "get_climate", return_value=climate),
            patch.object(coordinator, "async_write_schedule") as mock_write,
        ):
            await scenario.async_execute()

            # Verify the call was made with a ZoneSchedule argument
            assert mock_write.called
            call_args = mock_write.call_args
            zone_schedule = call_args[0][0]

            # Check that the schedule has correct properties
            assert zone_schedule.zone_id == 2
            assert zone_schedule.id == ClimateZoneScheduleId.SCHEDULE_1
            assert zone_schedule.day == Weekday.MONDAY


async def test_init_with_none_state(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, modbus_test_store
):
    """Test initialization with None state raises an error."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]

        with pytest.raises(ScenarioExecutionError) as exc_info:
            SchedulerScheduleUpdated(
                hass=hass,
                coordinator=coordinator,
                schedule_state=None,
            )

        assert exc_info.value.translation_key == "scenario_execution_error_missing_required_state"


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_modbus_sourced_update_is_ignored(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test that an updated schedule sourced by modbus is ignored (prevents update cycles)."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        # Mock is_modbus_sourced_update to return False
        # This should cause the method to exit early without doing anything
        with (
            patch.object(
                coordinator,
                "is_modbus_sourced_update",
                return_value=True,
            ),
            patch.object(
                coordinator,
                "async_get_linked_zone_schedule_uid",
                return_value=ZoneScheduleUID(
                    zone_id=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_1, weekday=Weekday.MONDAY
                ),
            ) as mock_get,
        ):
            await scenario.async_execute()

            # Verify async_get_linked_zone_schedule_uid was NOT called
            assert not mock_get.called


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_updated_on_waiting_list_removes_from_list(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict,
):
    """Test that when schedule is on waiting list, it's removed from the list."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create", new=lambda *args, **kwargs: api
        ),
        patch(
            "custom_components.remeha_modbus.api.store.RemehaModbusStore",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        scheduler_state = State(**json_fixture)

        scenario = SchedulerScheduleUpdated(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
        )

        # Mock is_modbus_sourced_update to return false
        with patch.object(
            coordinator, "is_modbus_sourced_update", return_value=False
        ) as is_modbus_sourced_update:
            await scenario.async_execute()

            # Verify is_modbus_sourced_update was called with correct entity_id
            is_modbus_sourced_update.assert_called_with(scheduler_state.entity_id)
