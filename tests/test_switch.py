"""Tests for switch entities."""

from unittest.mock import patch

from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import HEATPUMP_MANAGED_SCHEDULES, SWITCH_SCHEDULE_SYNC

from .conftest import get_api, setup_platform


async def test_switch(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test a single DhwHysteresisEntity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        for unique_id in [SWITCH_SCHEDULE_SYNC, HEATPUMP_MANAGED_SCHEDULES]:
            state = hass.states.get(f"{SwitchDomain}.{unique_id}")
            assert state is not None
            assert state.name == unique_id
