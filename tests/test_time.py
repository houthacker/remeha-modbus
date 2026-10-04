"""Test the time component."""

from unittest.mock import patch

from homeassistant.components.time.const import DOMAIN as TimeDomain
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import (
    TIME_SILENT_MODE_END_TIME,
    TIME_SILENT_MODE_START_TIME,
)

from .conftest import setup_platform


async def test_time_entities(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test available time entities."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=TimeDomain)) == 2

        for unique_id in [TIME_SILENT_MODE_START_TIME, TIME_SILENT_MODE_END_TIME]:
            entity_id = f"{TimeDomain}.remeha_modbus_test_hub_{unique_id}"
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.entity_id == entity_id
