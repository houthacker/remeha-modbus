"""Test the sensor component."""

from unittest.mock import patch

import pytest
from homeassistant.components.sensor.const import DOMAIN as SensorDomain
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import REMEHA_SENSORS

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_sensors(hass: HomeAssistant, mock_modbus_client):
    """Test available sensors."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SensorDomain)) == 7

        for sd in REMEHA_SENSORS.values():
            state = hass.states.get(f"sensor.remeha_modbus_test_hub_{sd.name}")
            assert state.name == f"Remeha Modbus test_hub {sd.name}"
