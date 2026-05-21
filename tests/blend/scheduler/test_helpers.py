"""Test scheduler helpers."""

from copy import deepcopy
from dataclasses import replace
from datetime import time
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from homeassistant.core import HomeAssistant, State
from pydantic import ValidationError

from custom_components.remeha_modbus.api.schedule import (
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
)
from custom_components.remeha_modbus.blend.scheduler import helpers
from custom_components.remeha_modbus.blend.scheduler.const import (
    SCHEDULER_TAG_PREFIX,
    SchedulerState,
    ServiceOperation,
)
from custom_components.remeha_modbus.const import ClimateZoneScheduleId, Weekday, ZoneScheduleUID
from custom_components.remeha_modbus.errors import ParseError, RemehaModbusError
from tests.conftest import get_api, setup_platform
from tests.util.util import replace_tag_template


def test_compose_scheduler_tag():
    """Test compose_scheduler_tag."""

    uuid = uuid4()

    tag = helpers.compose_scheduler_tag(uuid)
    assert tag is not None
    assert str(uuid) in tag


def test_decompose_scheduler_tag():
    """Test decomposing a scheduler tag to a UUID."""

    # Valid scheduler tag
    expected_uuid = uuid4()
    tag = helpers.compose_scheduler_tag(expected_uuid)
    assert helpers.decompose_scheduler_tag(tag) == expected_uuid

    # Incorrect tag prefix
    tag = f"INVALID_PREFIX_{expected_uuid!s}"
    with pytest.raises(expected_exception=ValueError, match="Invalid scheduler tag."):
        helpers.decompose_scheduler_tag(tag)

    # tag does not contain a UUID
    tag = f"{SCHEDULER_TAG_PREFIX}abc"
    with pytest.raises(expected_exception=ValueError, match="badly formed hexadecimal UUID string"):
        helpers.decompose_scheduler_tag(tag)


@pytest.mark.parametrize("json_fixture", ["scheduler.state.json"], indirect=True)
def test_to_scheduler_state(json_fixture: dict[str, Any]):
    """Test conversion of a State to a SchedulerState."""

    state = State(**json_fixture)
    converted: SchedulerState = helpers.to_scheduler_state(state)

    assert converted["entity_id"] == state.entity_id
    assert converted["state"] == state.state
    assert converted["attributes"] == {
        "weekdays": ["mon"],
        "timeslots": ["08:00:00 - 16:00:00"],
        "entities": ["climate.remeha_modbus_dhw"],
        "actions": [{"service": "climate.set_preset_mode", "data": {"preset_mode": "comfort"}}],
        "tags": ["test_remeha", "remeha_modbus___UUID__"],
    }


@pytest.mark.parametrize("json_fixture", ["scheduler.invalid_scheduler.state.json"], indirect=True)
def test_to_scheduler_state_invalid(json_fixture: dict[str, Any]):
    """Test conversion of a State object that is not a SchedulerState."""

    state = State(**json_fixture)

    with pytest.raises(ValidationError):
        helpers.to_scheduler_state(state)


@pytest.mark.parametrize("json_fixture", ["remeha.schedulerstate.json"], indirect=True)
def test_to_zone_schedule(json_fixture: dict[str, Any]):
    """Test conversion of a SchedulerState to a ZoneSchedule."""

    scheduler_state = SchedulerState(**json_fixture)
    uid = ZoneScheduleUID(
        zone_id=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_1, weekday=Weekday.MONDAY
    )
    zone_schedule = helpers.to_zone_schedule(scheduler_state, uid)
    assert zone_schedule.id == uid.schedule_id
    assert zone_schedule.zone_id == uid.zone_id
    assert zone_schedule.day == uid.weekday
    assert zone_schedule.time_slots == [
        Timeslot(
            setpoint_type=TimeslotSetpointType.COMFORT,
            activity=TimeslotActivity.DHW,
            switch_time=time(hour=8),
        )
    ]


@pytest.mark.parametrize("json_fixture", ["remeha.invalid-schedulerstate.json"], indirect=True)
def test_to_zone_schedule_invalid(json_fixture: dict[str, Any]):
    """Test conversion of a SchedulerState not calling climate.set_preset."""

    scheduler_state = SchedulerState(**json_fixture)
    uid = ZoneScheduleUID(
        zone_id=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_1, weekday=Weekday.MONDAY
    )

    with pytest.raises(ParseError):
        helpers.to_zone_schedule(scheduler_state, uid)


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize("json_fixture", ["scheduler_schedule.json"], indirect=True)
async def test_to_scheduler_schedule(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, json_fixture: dict[str, Any]
):
    """Test that to_scheduler_schedule converts a ZoneSchedule correctly."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        zone_schedule = await api.async_read_zone_schedule(
            2, ClimateZoneScheduleId.SCHEDULE_1, Weekday.MONDAY
        )
        assert zone_schedule is not None

        uuid = uuid4()

        # Replace placeholder in fixture with real value
        json_fixture = replace_tag_template(json_fixture, uuid)
        scheduler_schedule = await helpers.to_scheduler_schedule(
            hass=hass, schedule=zone_schedule, operation=ServiceOperation.ADD, linking_tag=uuid
        )
        assert scheduler_schedule == json_fixture


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize("json_fixture", ["remeha.schedulerstate.json"], indirect=True)
async def test_links_exclusively_to_remeha_climate(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, json_fixture: SchedulerState
):
    """Test whether a given scheduler.State links exclusively to a remeha climate entity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert helpers.links_exclusively_to_remeha_climate(hass, json_fixture)


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize(
    "json_fixture", ["remeha.schedulerstate.multiple-climates.json"], indirect=True
)
async def test_links_exclusively_to_remeha_climate_invalid(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, json_fixture: SchedulerState
):
    """Test that the helper returns False when a SchedulerState links to at least two entities."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert not helpers.links_exclusively_to_remeha_climate(hass, json_fixture)


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_get_updated_dhw_schedules(mock_modbus_client):
    """Test calculating updated DHW schedules between two schedule sets."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    climates = [
        climate for climate in await api.async_read_zones() if climate.is_domestic_hot_water()
    ]

    # Same climates have no updates
    assert (
        helpers.get_updated_dhw_schedules(
            {zone.id: zone for zone in climates}, {zone.id: zone for zone in climates}
        )
        == []
    )

    # climate sets with different keys raise an error
    with pytest.raises(RemehaModbusError):
        helpers.get_updated_dhw_schedules({zone.id: zone for zone in climates}, {})

    # climates with different schedules return the mutual difference.
    new_climates = deepcopy(climates)
    dhw = new_climates[0]
    zone_schedule = dhw.current_schedule[Weekday.MONDAY]

    # Update the setpoint_type
    assert zone_schedule is not None
    ts = zone_schedule.time_slots[0]
    zone_schedule.time_slots[0] = replace(
        ts,
        setpoint_type=(
            TimeslotSetpointType.ECO
            if ts.setpoint_type == TimeslotSetpointType.COMFORT
            else TimeslotSetpointType.COMFORT
        ),
    )

    # These must now differ.
    assert zone_schedule != climates[0].current_schedule[Weekday.MONDAY]

    updates = helpers.get_updated_dhw_schedules(
        {zone.id: zone for zone in climates}, {zone.id: zone for zone in new_climates}
    )
    assert len(updates) == 1
    assert updates[0] == zone_schedule
