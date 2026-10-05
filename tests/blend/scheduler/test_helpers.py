"""Test scheduler helpers."""

from datetime import time
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from aio_remeha_modbus.gtw08.const import Weekday
from aio_remeha_modbus.gtw08.time_program import (
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
)
from homeassistant.core import HomeAssistant, State
from pydantic import ValidationError

from custom_components.remeha_modbus import RemehaUpdateCoordinator
from custom_components.remeha_modbus.blend.scheduler import helpers
from custom_components.remeha_modbus.blend.scheduler.const import (
    SCHEDULER_TAG_PREFIX,
    SchedulerState,
    ServiceOperation,
)
from custom_components.remeha_modbus.errors import ParseError, RemehaModbusError
from tests.conftest import setup_platform
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


@pytest.mark.parametrize("json_file", ["scheduler.state.json"], indirect=True)
def test_to_scheduler_state(json_file: dict[str, Any]):
    """Test conversion of a State to a SchedulerState."""

    state = State(**json_file)
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


@pytest.mark.parametrize("json_file", ["scheduler.invalid_scheduler.state.json"], indirect=True)
def test_to_scheduler_state_invalid(json_file: dict[str, Any]):
    """Test conversion of a State object that is not a SchedulerState."""

    state = State(**json_file)

    with pytest.raises(ValidationError):
        helpers.to_scheduler_state(state)


@pytest.mark.parametrize("json_file", ["remeha.schedulerstate.json"], indirect=True)
def test_to_zone_schedule(json_file: dict[str, Any]):
    """Test conversion of a SchedulerState to a ZoneSchedule."""

    scheduler_state = SchedulerState(**json_file)

    weekday, time_slots = helpers.to_zone_schedule(scheduler_state)
    assert weekday == Weekday.MONDAY
    assert time_slots == [
        Timeslot(
            setpoint_type=TimeslotSetpointType.COMFORT,
            activity=TimeslotActivity.DHW,
            switch_time=time(hour=8),
        )
    ]


@pytest.mark.parametrize("json_file", ["remeha.invalid-schedulerstate.json"], indirect=True)
def test_to_zone_schedule_invalid(json_file: dict[str, Any]):
    """Test conversion of a SchedulerState not calling climate.set_preset."""

    scheduler_state = SchedulerState(**json_file)

    with pytest.raises(ParseError):
        helpers.to_zone_schedule(scheduler_state)


@pytest.mark.parametrize("json_file", ["scheduler_schedule.json"], indirect=True)
async def test_to_scheduler_schedule(
    hass: HomeAssistant, remeha_api, mock_config_entry, json_file, remeha_modbus_unit
):
    """Test that to_scheduler_schedule converts a ZoneSchedule correctly."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        climate = coordinator.get_climate(id=2)
        assert climate is not None
        assert climate.selected_schedule is not None
        zone_schedule = (
            climate.current_schedule[Weekday.MONDAY]
            if climate.current_schedule is not None
            else None
        )
        assert zone_schedule is not None

        uuid = uuid4()

        # Replace placeholder in fixture with real value
        json_file = replace_tag_template(json_file, uuid)
        scheduler_schedule = await helpers.to_scheduler_schedule(
            hass,
            zone_id=climate.id,
            schedule_id=climate.selected_schedule,
            day=Weekday.MONDAY,
            time_slots=zone_schedule,
            operation=ServiceOperation.ADD,
            linking_tag=uuid,
        )
        assert scheduler_schedule == json_file


@pytest.mark.parametrize("json_file", ["remeha.schedulerstate.json"], indirect=True)
async def test_links_exclusively_to_remeha_climate(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    json_file: SchedulerState,
    remeha_modbus_unit,
):
    """Test whether a given scheduler.State links exclusively to a remeha climate entity."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert helpers.links_exclusively_to_remeha_climate(hass, json_file)


@pytest.mark.parametrize(
    "json_file", ["remeha.schedulerstate.multiple-climates.json"], indirect=True
)
async def test_links_exclusively_to_remeha_climate_invalid(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    json_file: SchedulerState,
    remeha_modbus_unit,
):
    """Test that the helper returns False when a SchedulerState links to at least two entities."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert not helpers.links_exclusively_to_remeha_climate(hass, json_file)


async def test_get_updated_dhw_schedules(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test calculating updated DHW schedules between two schedule sets."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        climates = coordinator.get_climates(lambda zone: zone.is_domestic_hot_water())

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
