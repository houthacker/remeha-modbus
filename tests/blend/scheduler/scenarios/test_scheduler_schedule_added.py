"""Tests for the SchedulerScheduleAdded scenario."""

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import MockEntity

from custom_components.remeha_modbus.blend.scheduler.scenarios.scheduler_schedule_added import (
    SchedulerScheduleAdded,
)
from custom_components.remeha_modbus.const import ClimateZoneScheduleId, Weekday, ZoneScheduleUID
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from tests.conftest import get_api, setup_platform
from tests.util.util import replace_tag_template


@pytest.mark.parametrize("json_fixture", ["scheduler.state_no_tags.json"], indirect=True)
async def test_schedule_added_no_tags(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict[str, Any],
):
    """Test an added scheduler.schedule having no tags."""

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
        schedule_state_tracked = [False]

        def _track_schedule_state():
            schedule_state_tracked[0] = True

        scenario = SchedulerScheduleAdded(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
            track_schedule_state=_track_schedule_state,
        )

        await scenario.async_execute()
        assert not schedule_state_tracked[0]


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_added_not_on_waiting_list(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict[str, Any],
):
    """Test an added scheduler.schedule having no tags."""

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
        schedule_state_tracked = [False]

        def _track_schedule_state():
            schedule_state_tracked[0] = True

        scenario = SchedulerScheduleAdded(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
            track_schedule_state=_track_schedule_state,
        )

        await scenario.async_execute()
        assert not schedule_state_tracked[0]


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
async def test_schedule_added(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    modbus_test_store,
    json_fixture: dict[str, Any],
):
    """Test an added scheduler.schedule having no tags."""

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
        uuid = uuid4()
        scheduler_state = State(**replace_tag_template(json_fixture, uuid))
        await setup_platform(
            hass=hass,
            config_entry=mock_config_entry,
            scheduler_entities=[MockEntity(entity_id=scheduler_state.entity_id)],
        )
        await hass.async_block_till_done()

        # HA is set up, patch the async_get_registry mock

        zone_uid = ZoneScheduleUID(2, ClimateZoneScheduleId.SCHEDULE_1, Weekday.MONDAY)
        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]

        # Prepare waiting list.
        coordinator.enqueue_for_linking(uuid, zone_uid)

        schedule_state_tracked = [False]

        def _track_schedule_state():
            schedule_state_tracked[0] = True

        scenario = SchedulerScheduleAdded(
            hass=hass,
            coordinator=coordinator,
            schedule_state=scheduler_state,
            track_schedule_state=_track_schedule_state,
        )

        await scenario.async_execute()

        assert schedule_state_tracked[0]
        assert coordinator.async_get_linked_scheduler_entity(zone_uid) is not None
