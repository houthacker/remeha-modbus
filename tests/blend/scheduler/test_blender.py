"""Tests for the SchedulerBlender."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remeha_modbus.blend.blender import BlenderState
from custom_components.remeha_modbus.blend.scheduler.blender import SchedulerBlender
from custom_components.remeha_modbus.blend.scheduler.event_dispatcher import EventDispatcher
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from tests.conftest import setup_platform


async def test_blender_creation(
    hass: HomeAssistant, remeha_api, mock_config_entry: MockConfigEntry, remeha_modbus_unit
):
    """Test that creating a new SchedulerBlender puts it in the expected state."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        dispatcher = EventDispatcher(hass)

        blender = SchedulerBlender(hass, coordinator, dispatcher)
        assert blender.state == BlenderState.INITIAL


async def test_blender_async_blend(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry: MockConfigEntry,
    finalizer: list,
    remeha_modbus_unit,
):
    """Test that blending a SchedulerBlender transitions it to the STARTED state."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        dispatcher = EventDispatcher(hass)
        finalizer.append(dispatcher.untrack_all)

        blender = SchedulerBlender(hass, coordinator, dispatcher)
        await blender.async_blend()

        assert blender.state == BlenderState.STARTED
