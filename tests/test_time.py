"""Test the time component."""

from unittest.mock import patch

import pytest
from homeassistant.components.time.const import DOMAIN as TimeDomain
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import (
    TIME_SILENT_MODE_END_TIME,
    TIME_SILENT_MODE_START_TIME,
)

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_time_entities(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test available time entities."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
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
