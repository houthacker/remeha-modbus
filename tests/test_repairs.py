"""Tests for repair flows."""

from unittest.mock import patch

import pytest
from homeassistant.components.repairs.issue_handler import async_process_repairs_platforms
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from custom_components.remeha_modbus.const import (
    DOMAIN,
    ISSUE_DISCOVERY_TABLE_CORRUPTED,
    MetaRegisters,
)
from tests.conftest import get_api, setup_platform
from tests.util.repairs import get_repairs, process_repair_fix_flow, start_repair_fix_flow


@pytest.mark.parametrize(
    "mock_modbus_client", ["modbus_store_corrupted_discovery_table.json"], indirect=True
)
async def test_discovery_table_corrupted_repair(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, hass_client, hass_ws_client
):
    """Test repairing a corrupted modbus discovery table."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # Modbus recovery register must be zero
        (discovery_register,) = await api.async_read_registers(
            MetaRegisters.RESET_DISCOVERY_TABLE.start_address, 1
        )
        assert discovery_register == 0x0000

        # Start remeha_modbus
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # Start repair fix flow
        issue_registry = ir.async_get(hass)
        issues = await get_repairs(hass, hass_ws_client)
        assert issues
        assert issue_registry.async_get_issue(DOMAIN, ISSUE_DISCOVERY_TABLE_CORRUPTED) is not None

        await async_process_repairs_platforms(hass)
        client = await hass_client()
        data = await start_repair_fix_flow(client, DOMAIN, ISSUE_DISCOVERY_TABLE_CORRUPTED)

        flow_id = data["flow_id"]
        assert data["type"] == FlowResultType.FORM
        assert data["step_id"] == "confirm_force_rediscovery"

        # Issue must have been removed
        data = await process_repair_fix_flow(client, flow_id, json={})
        assert data["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert issue_registry.async_get_issue(DOMAIN, ISSUE_DISCOVERY_TABLE_CORRUPTED) is None

        # And modbus register 200 must contain 0x5a
        (discovery_register,) = await api.async_read_registers(
            MetaRegisters.RESET_DISCOVERY_TABLE.start_address, 1
        )
        assert discovery_register == 0x5A00
