"""Test the sensor component."""

from unittest.mock import patch

import pytest
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


async def test_water_pressure_sensor_resolves_its_value(
    hass: HomeAssistant, remeha_api, mock_config_entry
):
    """The water pressure sensor must resolve a value.

    Sensor values are looked up by entity name, but `aio-remeha-modbus` holds the water
    pressure in `actual_water_pressure` (register 409). Without mapping that name, the
    lookup misses and the sensor stays without a value.
    """

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        pressure = hass.states.get("sensor.remeha_modbus_test_hub_water_pressure")
        assert pressure is not None
        assert float(pressure.state) == pytest.approx(1.2)
        assert pressure.attributes["unit_of_measurement"] == "bar"
