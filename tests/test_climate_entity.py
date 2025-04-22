"""Tests for the RemehaClimateEntity."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climates(hass: HomeAssistant, mock_modbus_client):
    """Test climates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        states = hass.states.async_all()
        assert len(states) == 2
