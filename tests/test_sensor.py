"""Test the sensor component."""

from unittest.mock import patch

from homeassistant.components.sensor.const import DOMAIN as SensorDomain
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import REMEHA_SENSORS

from .conftest import setup_platform


async def test_sensors(hass: HomeAssistant, remeha_api, mock_config_entry):
    """Test available sensors."""

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SensorDomain)) == 33

        for sd in REMEHA_SENSORS:
            assert isinstance(sd.name, str)
            state = hass.states.get(f"sensor.remeha_modbus_test_hub_{sd.name}")
            assert state is not None
            assert state.entity_id == f"sensor.remeha_modbus_test_hub_{sd.name}"

            # Sensor state must not be empty. See issue #107
            assert len(state.state) > 0
