"""Tests for repair flows."""

from unittest.mock import patch

import pytest
from homeassistant.components.climate.const import ATTR_PRESET_MODE, PRESET_ECO
from homeassistant.components.repairs.issue_handler import async_process_repairs_platforms
from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from remeha_modbus.helpers.entities import get_climate_entity_id

from custom_components.remeha_modbus.const import (
    DOMAIN,
    HEATPUMP_MANAGED_SCHEDULES,
    ISSUE_DISCOVERY_TABLE_CORRUPTED,
    ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF,
    ISSUE_INVALID_ZONE_SCHEDULE,
    REMEHA_ZONE_RESERVED_REGISTERS,
    MetaRegisters,
    ZoneRegisters,
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


@pytest.mark.parametrize(
    "mock_modbus_client", ["modbus_store_invalid_timeslot.json"], indirect=True
)
async def test_invalid_zone_schedule_repair(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, hass_client, hass_ws_client
):
    """Test repairing an invalid zone schedule."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # Start remeha_modbus
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # And modbus register 1201 must contain 0x05a0
        (timeslot_activity_register,) = await api.async_read_registers(
            ZoneRegisters.TIME_PROGRAM_MONDAY.start_address + REMEHA_ZONE_RESERVED_REGISTERS, 1
        )
        assert timeslot_activity_register == 0xA005

        # Start repair fix flow
        issue_registry = ir.async_get(hass)
        issues = await get_repairs(hass, hass_ws_client)
        assert issues
        assert issue_registry.async_get_issue(DOMAIN, ISSUE_INVALID_ZONE_SCHEDULE) is not None

        await async_process_repairs_platforms(hass)
        client = await hass_client()
        data = await start_repair_fix_flow(client, DOMAIN, ISSUE_INVALID_ZONE_SCHEDULE)

        flow_id = data["flow_id"]
        assert data["type"] == FlowResultType.FORM
        assert data["step_id"] == "confirm_overwrite"

        # Issue must have been removed
        data = await process_repair_fix_flow(client, flow_id, json={})
        assert data["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert issue_registry.async_get_issue(DOMAIN, ISSUE_INVALID_ZONE_SCHEDULE) is None

        # And modbus register 1201 must contain 0x0100 (was 0x05a0)
        (timeslot_activity_register,) = await api.async_read_registers(
            ZoneRegisters.TIME_PROGRAM_MONDAY.start_address + REMEHA_ZONE_RESERVED_REGISTERS, 1
        )
        assert timeslot_activity_register == 0x0001


async def test_undo_manual_schedule_execution_repair(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry, hass_client, hass_ws_client
):
    """Test repairing/resetting `switch.heatpump_managed_schedules`."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # Start remeha_modbus
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        entity_id = f"{SwitchDomain}.{HEATPUMP_MANAGED_SCHEDULES}"

        # Switch must be on by default
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

        # Retrieve the current DHW climate preset.
        climate_entity_id = get_climate_entity_id(hass, 2)
        state = hass.states.get(climate_entity_id)
        assert state is not None
        original_preset = state.attributes[ATTR_PRESET_MODE]

        # Turn the switch off
        await hass.services.async_call(
            domain=SwitchDomain, service=SERVICE_TURN_OFF, target={ATTR_ENTITY_ID: entity_id}
        )

        # Switch must be off now
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

        # DHW climate must be set to preset=ECO as a result.
        state = hass.states.get(climate_entity_id)
        assert state is not None
        assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO

        # Start repair fix flow
        issue_registry = ir.async_get(hass)
        issues = await get_repairs(hass, hass_ws_client)
        assert issues
        assert (
            issue_registry.async_get_issue(DOMAIN, ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF) is not None
        )

        await async_process_repairs_platforms(hass)
        client = await hass_client()
        data = await start_repair_fix_flow(client, DOMAIN, ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF)

        flow_id = data["flow_id"]
        assert data["type"] == FlowResultType.FORM
        assert data["step_id"] == "confirm_undo"

        # Issue must have been removed
        data = await process_repair_fix_flow(client, flow_id, json={})
        assert data["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert issue_registry.async_get_issue(DOMAIN, ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF) is None

        # Switch is back on
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

        # And climate is back to previous state
        state = hass.states.get(climate_entity_id)
        assert state is not None
        assert state.attributes[ATTR_PRESET_MODE] == original_preset
