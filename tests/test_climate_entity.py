"""Tests for the RemehaClimateEntity."""

import pytest
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.api import RemehaApi

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climates(hass: HomeAssistant, mock_modbus_client):
    """Test climates."""

    api: RemehaApi = get_api(mock_modbus_client=mock_modbus_client)

    await setup_platform(hass=hass, api=api)

    states = hass.states.async_all()
    assert len(states) == 2
