"""Tests for remeha_modbus integration services."""

from unittest.mock import patch

import pytest
from aio_remeha_modbus.api.climate_zone import (
    ClimateZone,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    Weekday,
    ZoneSchedule,
)
from homeassistant.core import HomeAssistant
from pymodbus import ModbusException

from custom_components.remeha_modbus.const import (
    DOMAIN,
    READ_REGISTERS_REGISTER_COUNT,
    READ_REGISTERS_START_REGISTER,
    READ_REGISTERS_STRUCT_FORMAT,
    SERVICE_AUTO_SCHEDULE,
    SERVICE_READ_REGISTERS,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import (
    RemehaServiceError,
)

from .conftest import setup_platform


@pytest.mark.parametrize("mock_config_entry", [{"auto_scheduling": True}], indirect=True)
async def test_scheduling_service(
    hass: HomeAssistant, remeha_api, remeha_modbus_unit, mock_config_entry
):
    """Test of the auto scheduling service."""

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]

        # Call the service
        await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_AUTO_SCHEDULE,
            blocking=True,
            return_response=False,
        )
        await hass.async_block_till_done()

        # Check that the schedule has been created but not activated.
        # For auto scheduling, we use SCHEDULE_1.
        # Using the test data, a schedule will be created for Weekday.FRIDAY.
        zone: ClimateZone | None = coordinator.get_climate(id=2)
        assert zone is not None
        assert zone.selected_schedule == ClimateZoneScheduleId.SCHEDULE_1
        assert zone.mode == ClimateZoneMode.SCHEDULING

        day: Weekday = Weekday.FRIDAY
        schedule: ZoneSchedule | None = (
            zone.current_schedule[day] if zone.current_schedule else None
        )
        assert schedule is not None


@pytest.mark.parametrize("mock_config_entry", [{"auto_scheduling": True}], indirect=True)
async def test_read_registers_service(hass: HomeAssistant, remeha_api, mock_config_entry):
    """Test of the auto scheduling service."""

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # Call the service
        assert await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_READ_REGISTERS,
            blocking=True,
            return_response=True,
            service_data={
                READ_REGISTERS_START_REGISTER: 1201,
                READ_REGISTERS_REGISTER_COUNT: 10,
                READ_REGISTERS_STRUCT_FORMAT: "=HHHHHHHHHH",
            },
        ) == {"value": (5, 0, 4096, 60, 19968, 4096, 108, 0, 126, 0)}


@pytest.mark.parametrize("mock_config_entry", [{"auto_scheduling": True}], indirect=True)
async def test_read_registers_service_exceptions(
    hass: HomeAssistant, remeha_api, mock_config_entry
):
    """Test modbus errors raised from the read_registers service."""
    with (
        patch(
            "custom_components.remeha_modbus.RemehaApi",
            new=lambda *args, **kwargs: remeha_api,
        ),
        patch(
            "custom_components.remeha_modbus.coordinator.RemehaUpdateCoordinator.async_read_registers"
        ) as mock,
    ):
        mock.side_effect = ModbusException("Oops!")
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # Call the service
        with pytest.raises(expected_exception=RemehaServiceError):
            await hass.services.async_call(
                domain=DOMAIN,
                service=SERVICE_READ_REGISTERS,
                blocking=True,
                return_response=True,
                service_data={
                    READ_REGISTERS_START_REGISTER: 128,
                    READ_REGISTERS_REGISTER_COUNT: 1,
                    READ_REGISTERS_STRUCT_FORMAT: "=H",
                },
            )
