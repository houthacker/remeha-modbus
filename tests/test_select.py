"""Tests for select entities."""

from unittest.mock import patch

import pytest
from homeassistant.components.select.const import DOMAIN as SelectDomain
from homeassistant.core import HomeAssistant

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_quiet_mode_select(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test the heat pump quiet mode select entity (HP058)."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # register 490 is 2 in the fixture -> level_2
        quiet_mode = hass.states.get("select.remeha_modbus_test_hub_quiet_mode")
        assert quiet_mode is not None
        assert quiet_mode.state == "level_2"

        await hass.services.async_call(
            domain=SelectDomain,
            service="select_option",
            service_data={"entity_id": quiet_mode.entity_id, "option": "off"},
            blocking=True,
        )

        quiet_mode = hass.states.get(quiet_mode.entity_id)
        assert quiet_mode is not None
        assert quiet_mode.state == "off"
