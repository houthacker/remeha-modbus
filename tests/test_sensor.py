"""Test the sensor component."""

from unittest.mock import patch

from homeassistant.components.sensor.const import DOMAIN as SensorDomain
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import REMEHA_SENSORS

from .conftest import setup_platform


async def test_sensors(hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit):
    """Test available sensors."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SensorDomain)) == 35

        for sd in REMEHA_SENSORS:
            assert isinstance(sd.name, str)
            state = hass.states.get(f"sensor.remeha_modbus_test_hub_{sd.name}")
            assert state is not None
            assert state.entity_id == f"sensor.remeha_modbus_test_hub_{sd.name}"

            # Sensor state must not be empty. See issue #107
            assert len(state.state) > 0


async def test_buffer_tank_sensors(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the buffer tank temperatures are exposed as sensors."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        bottom = hass.states.get("sensor.remeha_modbus_test_hub_buffer_temperature_bottom")
        assert bottom is not None
        assert float(bottom.state) == 24.5

        # The fixture holds 0xFFFF for the top sensor, which is how a missing sensor is reported.
        top = hass.states.get("sensor.remeha_modbus_test_hub_buffer_temperature_top")
        assert top is not None
        assert top.state == STATE_UNKNOWN
