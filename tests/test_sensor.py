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


async def test_status_sensor_reads_appliance_status(
    hass: HomeAssistant, remeha_api, mock_config_entry
):
    """The `status` sensor must read varApStatus, not the main control monitoring status.

    `Appliance` and `MainControlMonitoring` both expose a `status` field, but they read
    different registers (411 resp. 279). Sensor values are collected from both components
    into one mapping, so the appliance has to win that name collision.

    The fixture holds 411 = 8 (controlled shutdown) and 279 = 160, which is not an
    appliance status at all: if the monitoring value wins, the sensor has no value.
    """

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        status = hass.states.get("sensor.remeha_modbus_test_hub_status")
        assert status is not None
        assert status.state == "controlled_shutdown"
