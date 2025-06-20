"""Tests for synchronization between scheduler.schedule entities and the Remeha modbus interface."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from pydantic import TypeAdapter, ValidationError

from custom_components.remeha_modbus.const import (
    DOMAIN,
    IMPORT_SCHEDULE_CLIMATE_ENTITY,
    IMPORT_SCHEDULE_SERVICE_NAME,
    IMPORT_SCHEDULE_WEEKDAY,
    SchedulerSchedule,
)
from custom_components.remeha_modbus.schedule_sync.synchronizer import to_scheduler_state
from tests.conftest import TESTING_ATTR_ADD_SCHEDULING_CALLS, get_api, setup_platform


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


async def test_import_schedule(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test that a schedule can be added by the scheduler."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # Retrieve the list of service calls to `scheduler.add`
        service_call_list = hass.data[DOMAIN][TESTING_ATTR_ADD_SCHEDULING_CALLS]
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
