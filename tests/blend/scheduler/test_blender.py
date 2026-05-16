"""Tests for the SchedulerBlender."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pymodbus.client import ModbusBaseClient
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remeha_modbus.blend.blender import BlenderState
from custom_components.remeha_modbus.blend.scheduler.blender import SchedulerBlender
from custom_components.remeha_modbus.blend.scheduler.event_dispatcher import EventDispatcher
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from tests.conftest import get_api, setup_platform


async def test_blender_creation(
    hass: HomeAssistant, mock_modbus_client: ModbusBaseClient, mock_config_entry: MockConfigEntry
):
    """Test that creating a new SchedulerBlender puts it in the expected state."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        dispatcher = EventDispatcher(hass)

        blender = SchedulerBlender(hass, coordinator, dispatcher)
        assert blender.state == BlenderState.INITIAL


async def test_blender_async_blend(
    hass: HomeAssistant,
    mock_modbus_client: ModbusBaseClient,
    mock_config_entry: MockConfigEntry,
    finalizer: list,
):
    """Test that blending a SchedulerBlender transitions it to the STARTED state."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        dispatcher = EventDispatcher(hass)
        finalizer.append(dispatcher.untrack_all)

        blender = SchedulerBlender(hass, coordinator, dispatcher)
        await blender.async_blend()

        assert blender.state == BlenderState.STARTED
