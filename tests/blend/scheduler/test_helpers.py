"""Test scheduler helpers."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.blend.scheduler import helpers
from custom_components.remeha_modbus.blend.scheduler.const import (
    SchedulerSchedule,
    ServiceOperation,
)
from custom_components.remeha_modbus.const import ClimateZoneScheduleId, Weekday
from tests.conftest import get_api, replace_tag_template, setup_platform


def test_compose_scheduler_tag():
    """Test compose_scheduler_tag."""

    uuid = uuid4()

    tag = helpers.compose_scheduler_tag(uuid)
    assert tag is not None
    assert str(uuid) in tag


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize("json_fixture", ["scheduler_schedule.json"], indirect=True)
async def test_to_scheduler_schedule(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, json_fixture: SchedulerSchedule
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
