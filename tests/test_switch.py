"""Tests for switch entities."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoard
from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.remeha_modbus.const import HEATPUMP_MANAGED_SCHEDULES, SWITCH_SCHEDULE_SYNC

from .conftest import setup_platform

MAINBOARD_SWITCHES = [
    "switch.remeha_modbus_test_hub_ch_enabled",
    "switch.remeha_modbus_test_hub_cooling_enabled",
    "switch.remeha_modbus_test_hub_force_summer",
]


def _assert_switches(hass: HomeAssistant, expect_mainboard_switches: bool):
    """Assert which switches have been added."""

    entity_registry = er.async_get(hass)

    for unique_id in [SWITCH_SCHEDULE_SYNC, HEATPUMP_MANAGED_SCHEDULES]:
        assert hass.states.get(f"{SwitchDomain}.{unique_id}") is not None

    for entity_id in MAINBOARD_SWITCHES:
        if expect_mainboard_switches:
            assert hass.states.get(entity_id) is not None
            assert entity_registry.async_get(entity_id) is not None
        else:
            assert hass.states.get(entity_id) is None
            assert entity_registry.async_get(entity_id) is None


async def test_switch(hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit):
    """Test a single DhwHysteresisEntity."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        for unique_id in [SWITCH_SCHEDULE_SYNC, HEATPUMP_MANAGED_SCHEDULES]:
            state = hass.states.get(f"{SwitchDomain}.{unique_id}")
            assert state is not None
            assert state.name == unique_id


async def test_appliance_switches(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test the appliance-level modbus switches (AP016 / AP028)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        # Both are enabled in the modbus_store fixture (registers 500 and 502 are 1).
        ch_enabled = hass.states.get("switch.remeha_modbus_test_hub_ch_enabled")
        assert ch_enabled is not None
        assert ch_enabled.state == "on"

        cooling_enabled = hass.states.get("switch.remeha_modbus_test_hub_cooling_enabled")
        assert cooling_enabled is not None
        assert cooling_enabled.state == "on"

        # Turning the switch off is reflected immediately.
        await hass.services.async_call(
            domain=SwitchDomain,
            service="turn_off",
            service_data={"entity_id": ch_enabled.entity_id},
            blocking=True,
        )

        ch_enabled = hass.states.get(ch_enabled.entity_id)
        assert ch_enabled is not None
        assert ch_enabled.state == "off"


async def test_force_summer_switch(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test the appliance force-summer switch (AP074)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        # register 389 is 0 in the fixture -> off
        force_summer = hass.states.get("switch.remeha_modbus_test_hub_force_summer")
        assert force_summer is not None
        assert force_summer.state == "off"

        await hass.services.async_call(
            domain=SwitchDomain,
            service="turn_on",
            service_data={"entity_id": force_summer.entity_id},
            blocking=True,
        )

        force_summer = hass.states.get(force_summer.entity_id)
        assert force_summer is not None
        assert force_summer.state == "on"


async def test_mainboard_switches_added(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that mainboard-dependent switches are added when the mainboard supports them."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SwitchDomain)) == 5
        _assert_switches(hass, expect_mainboard_switches=True)


@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_mainboard_switches_not_added_on_heat_pump_boiler(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    caplog: pytest.LogCaptureFixture,
):
    """Test that CH, cooling and force-summer switches are not added on a CU_HW mainboard."""

    caplog.set_level(logging.DEBUG, logger="custom_components.remeha_modbus.switch")

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SwitchDomain)) == 2
        _assert_switches(hass, expect_mainboard_switches=False)
        assert "mainboard does not support them" in caplog.text


@pytest.mark.parametrize(
    "mainboards",
    [
        pytest.param([], id="no_mainboard"),
        pytest.param([MagicMock(spec=DeviceBoard, board_category=None)], id="no_category"),
    ],
)
async def test_mainboard_switches_not_added_without_mainboard_category(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    mainboards: list[DeviceBoard],
):
    """Test that mainboard-dependent switches are not added if the mainboard type is unknown."""

    with (
        patch(
            "aio_remeha_modbus.gtw08.GTW08",
            new=lambda *args, **kwargs: remeha_api,
        ),
        patch(
            "custom_components.remeha_modbus.coordinator.RemehaUpdateCoordinator.get_devices",
            return_value=mainboards,
        ),
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SwitchDomain)) == 2
        _assert_switches(hass, expect_mainboard_switches=False)
