"""Test the binary_sensor component."""

from unittest.mock import patch

from aio_remeha_modbus.api.main_control_monitoring import ApplianceDemandStatus, MonitoringStatus
from homeassistant.components.binary_sensor import DOMAIN as BinarySensorDomain
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import setup_platform


async def test_sensors(hass: HomeAssistant, remeha_api, mock_config_entry):
    """Test available sensors."""

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=BinarySensorDomain)) == 22

        statuses = [*list(ApplianceDemandStatus), *list(MonitoringStatus)]

        for status in statuses:
            assert isinstance(status.name, str)
            state = hass.states.get(f"binary_sensor.remeha_modbus_test_hub_{status.name.lower()}")
            assert state is not None
            assert state.entity_id == f"binary_sensor.remeha_modbus_test_hub_{status.name.lower()}"

            # Sensor state must not be empty. See issue #107
            assert state.state in [STATE_ON, STATE_OFF]
