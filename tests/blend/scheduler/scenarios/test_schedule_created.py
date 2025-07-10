"""Tests for the `schedule_created` scenario."""

from datetime import time
from typing import cast
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonValueType

from custom_components.remeha_modbus.api import (
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.blend.scheduler.scenarios import ScheduleCreated
from custom_components.remeha_modbus.blend.scheduler.scenarios.schedule_created import (
    SHORT_DESC_TO_WEEKDAY,
)
from custom_components.remeha_modbus.const import SchedulerLinkView, SchedulerState
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from tests.conftest import get_api, setup_platform


@pytest.mark.parametrize("json_fixture", ["new_scheduler_schedule.json"], indirect=True)
async def test_schedule_created(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    json_fixture: JsonValueType,
    modbus_test_store,
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
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        state: SchedulerState = cast(SchedulerState, json_fixture)
        scenario: ScheduleCreated = ScheduleCreated(
            hass=hass, schedule=state, coordinator=coordinator
        )

        # Expect no existing link yet.
        assert len(await coordinator.async_get_scheduler_links()) == 0

        # Execute the scenario
        await scenario.async_execute()
        await hass.async_block_till_done()

        # After executing the scenario, a link must exist.
        link: SchedulerLinkView = next(iter(await coordinator.async_get_scheduler_links()))

        # Retrieve the climate schedule from the modbus interface. This must now 'equal' the scheduler state.
        zone_schedule: ZoneSchedule = await api.async_read_zone_schedule(
            zone=link.zone_id,
            schedule_id=link.schedule_id,
            day=SHORT_DESC_TO_WEEKDAY[state["attributes"]["weekdays"][0]],
        )

        assert zone_schedule.id == link.schedule_id
        assert zone_schedule.zone_id == link.zone_id
        assert zone_schedule.day == SHORT_DESC_TO_WEEKDAY[state["attributes"]["weekdays"][0]]
        assert zone_schedule.time_slots == [
            Timeslot(
                setpoint_type=TimeslotSetpointType.ECO,
                activity=TimeslotActivity.DHW,
                switch_time=time(hour=0, second=0),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.COMFORT,
                activity=TimeslotActivity.DHW,
                switch_time=time(hour=12, second=0),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.ECO,
                activity=TimeslotActivity.DHW,
                switch_time=time(hour=20, second=0),
            ),
        ]


@pytest.mark.parametrize(
    "json_fixture", ["scheduler_schedule_invalid_time_slots.json"], indirect=True
)
async def test_schedule_created_invalid_time_slots(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    json_fixture: JsonValueType,
    modbus_test_store,
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
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        state: SchedulerState = cast(SchedulerState, json_fixture)
        scenario: ScheduleCreated = ScheduleCreated(
            hass=hass, schedule=state, coordinator=coordinator
        )

        # Expect no existing link yet.
        assert len(await coordinator.async_get_scheduler_links()) == 0

        # Execute the scenario
        with pytest.raises(
            expected_exception=ValueError,
            match="Cannot parse timeslot string",
        ):
            await scenario.async_execute()

        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "json_fixture", ["scheduler_schedule_invalid_service_action.json"], indirect=True
)
async def test_schedule_created_invalid_service_action(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    json_fixture: JsonValueType,
    modbus_test_store,
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
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        state: SchedulerState = cast(SchedulerState, json_fixture)
        scenario: ScheduleCreated = ScheduleCreated(
            hass=hass, schedule=state, coordinator=coordinator
        )

        # Expect no existing link yet.
        assert len(await coordinator.async_get_scheduler_links()) == 0

        # Execute the scenario
        with pytest.raises(
            expected_exception=ValueError,
            match="Invalid SchedulerStateAction",
        ):
            await scenario.async_execute()

        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "json_fixture", ["scheduler_schedule_multiple_weekdays.json"], indirect=True
)
async def test_schedule_created_multiple_weekdays(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    json_fixture: JsonValueType,
    modbus_test_store,
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
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        state: SchedulerState = cast(SchedulerState, json_fixture)
        scenario: ScheduleCreated = ScheduleCreated(
            hass=hass, schedule=state, coordinator=coordinator
        )

        # Expect no existing link yet.
        assert len(await coordinator.async_get_scheduler_links()) == 0

        # Execute the scenario
        with pytest.raises(
            expected_exception=ValueError,
            match="Cannot parse ZoneSchedule from SchedulerState: require exactly 1 weekdays, got",
        ):
            await scenario.async_execute()

        await hass.async_block_till_done()
