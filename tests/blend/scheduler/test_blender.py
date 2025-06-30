"""Tests for the scheduler blender."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.blend.scheduler import Blender, BlenderState
from tests.conftest import get_api, setup_platform
from tests.util import set_storage_stub_return_value


async def test_create_blender(hass: HomeAssistant, mock_config_entry, mock_modbus_client):
    """Test the creation of a new Blender."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data["coordinator"]
        event_dispatcher = mock_config_entry.runtime_data["event_dispatcher"]
        blender: Blender = Blender(hass=hass, coordinator=coordinator, dispatcher=event_dispatcher)

        assert blender.state == BlenderState.INITIAL


async def test_start_stop_blender(hass: HomeAssistant, mock_config_entry, mock_modbus_client):
    """Test the Blender states after starting and stopping it."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data["coordinator"]
        event_dispatcher = mock_config_entry.runtime_data["event_dispatcher"]
        blender: Blender = Blender(hass=hass, coordinator=coordinator, dispatcher=event_dispatcher)

        # Start, stop the Blender and assert its state.
        blender.start()
        assert blender.state == BlenderState.STARTED

        blender.stop()
        assert blender.state == BlenderState.STOPPED


async def test_create_scheduler_schedule(
    hass: HomeAssistant, mock_config_entry, mock_modbus_client
):
    """Test that the `ScheduleCreated` scenario is executed when a `scheduler.schedule` is created from the scheduler UI."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
        patch("custom_components.scheduler.store.ScheduleStorage") as scheduler_storage,
        patch(
            "custom_components.remeha_modbus.blend.scheduler.scenarios.ScheduleCreated.async_execute"
        ) as execute_scenario,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # hass is set up, patch the async_get_registry-mock
        set_storage_stub_return_value(hass=hass, scheduler_storage=scheduler_storage)

        coordinator = mock_config_entry.runtime_data["coordinator"]
        event_dispatcher = mock_config_entry.runtime_data["event_dispatcher"]
        blender: Blender = Blender(hass=hass, coordinator=coordinator, dispatcher=event_dispatcher)

        blender.start()

        # Create a scheduler.schedule
        await hass.services.async_call(
            blocking=True,
            domain="scheduler",
            service="add",
            service_data={
                "weekdays": ["mon"],
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
                "repeat_type": "repeat",
            },
        )

        await hass.async_block_till_done()

        # Now, the execute_scenario method must have been called.
        execute_scenario.assert_called_once()
