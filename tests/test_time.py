"""Tests for time entities."""

from unittest.mock import patch

import pytest
from homeassistant.components.time.const import DOMAIN as TimeDomain
from homeassistant.core import HomeAssistant

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_quiet_mode_times(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test the heat pump quiet mode start/end time entities (HP094/HP095)."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # register 491 = 132 (132 * 10 min = 22:00), register 492 = 42 (07:00)
        start = hass.states.get("time.remeha_modbus_test_hub_quiet_mode_start")
        assert start is not None
        assert start.state == "22:00:00"

        end = hass.states.get("time.remeha_modbus_test_hub_quiet_mode_end")
        assert end is not None
        assert end.state == "07:00:00"

        await hass.services.async_call(
            domain=TimeDomain,
            service="set_value",
            service_data={"entity_id": start.entity_id, "time": "23:30:00"},
            blocking=True,
        )

        start = hass.states.get(start.entity_id)
        assert start is not None
        assert start.state == "23:30:00"
