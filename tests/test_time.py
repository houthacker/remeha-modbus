"""Test the time component."""

from unittest.mock import patch

import pytest
from homeassistant.components.time.const import DOMAIN as TimeDomain
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import (
    TIME_SILENT_MODE_END_TIME,
    TIME_SILENT_MODE_START_TIME,
)

from .conftest import remeha_api, setup_platform


@pytest.mark.parametrize("remeha_modbus_unit", ["modbus_store.json"], indirect=True)
async def test_time_entities(hass: HomeAssistant, remeha_modbus_unit, mock_config_entry):
    """Test available time entities."""

    api = remeha_api(remeha_modbus_unit=remeha_modbus_unit)
    with patch(
        "aio_remeha_modbus.api.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=TimeDomain)) == 2

        for unique_id in [TIME_SILENT_MODE_START_TIME, TIME_SILENT_MODE_END_TIME]:
            entity_id = f"{TimeDomain}.remeha_modbus_test_hub_{unique_id}"
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.entity_id == entity_id
