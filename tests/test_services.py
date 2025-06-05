"""Tests for remeha_modbus integration services."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.api import ClimateZone, Weekday, ZoneSchedule
from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_DEFAULT_ID,
    AUTO_SCHEDULE_SERVICE_NAME,
    DOMAIN,
    ClimateZoneMode,
    ClimateZoneScheduleId,
)

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize("mock_config_entry", [{"auto_scheduling": True}], indirect=True)
async def test_scheduling_service(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test of the auto scheduling service."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # Call the service
        await hass.services.async_call(
            domain=DOMAIN,
            service=AUTO_SCHEDULE_SERVICE_NAME,
            blocking=True,
            return_response=False,
        )
        await hass.async_block_till_done()

        # Check that the schedule has been created but not activated.
        # For auto scheduling, we use SCHEDULE_1.
        # Using the test data, a schedule will be created for Weekday.FRIDAY.
        zone: ClimateZone = await api.async_read_zone(id=2)
        assert zone.selected_schedule == ClimateZoneScheduleId.SCHEDULE_1
        assert zone.mode == ClimateZoneMode.MANUAL

        day: Weekday = Weekday.FRIDAY
        schedule: ZoneSchedule = await api.async_read_zone_schedule(
            zone=zone, schedule_id=AUTO_SCHEDULE_DEFAULT_ID, day=day
        )
        assert schedule is not None
