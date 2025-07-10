"""Test blend.scheduler helper methods."""

from typing import cast
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonValueType

from custom_components.remeha_modbus.blend.scheduler.helpers import (
    links_exclusively_to_remeha_climate,
)
from custom_components.remeha_modbus.const import SchedulerState
from tests.conftest import get_api, setup_platform


@pytest.mark.parametrize(
    ("json_fixture", "expected_result"),
    [("scheduler_schedule_no_remeha_reference.json", False), ("new_scheduler_schedule.json", True)],
    indirect=["json_fixture"],
)
async def test_links_exclusively_to_remeha_climate(
    hass: HomeAssistant,
    mock_modbus_client,
    mock_config_entry,
    json_fixture: JsonValueType,
    modbus_test_store,
    expected_result: bool,
):
    """Test that a ScheduleState which does (not) point to a remeha_modbus schedule is recognized as such."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
        patch(
            "custom_components.remeha_modbus.api.RemehaModbusStore.create",
            new=lambda *args, **kwargs: modbus_test_store,
        ),
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert (
            links_exclusively_to_remeha_climate(
                hass=hass, scheduler_state=cast(SchedulerState, json_fixture)
            )
            is expected_result
        )
