"""Tests for remeha_modbus integration services."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import AUTO_SCHEDULE_SERVICE_NAME, DOMAIN

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize("mock_config_entry", [{"auto_scheduling": True}], indirect=True)
async def test_climates(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test climates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # Call our service, must not fail.
        await hass.services.async_call(
            domain=DOMAIN,
            service=AUTO_SCHEDULE_SERVICE_NAME,
            blocking=True,
            return_response=False,
        )
