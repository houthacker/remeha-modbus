"""Test the sensor component."""

from unittest.mock import MagicMock, patch

import pytest
from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoard, DeviceBoardType
from homeassistant.components.sensor.const import DOMAIN as SensorDomain
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.remeha_modbus.const import DOMAIN, REMEHA_SENSORS
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

from .conftest import setup_platform

TANK_TEMPERATURE_TOP = "sensor.remeha_modbus_test_hub_dhw_tank_temperature_top"
TANK_TEMPERATURE_BOTTOM = "sensor.remeha_modbus_test_hub_dhw_tank_temperature_bottom"


async def test_sensors(hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit):
    """Test available sensors."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SensorDomain)) == 35

        for sd in REMEHA_SENSORS:
            assert isinstance(sd.name, str)
            state = hass.states.get(f"sensor.remeha_modbus_test_hub_{sd.name}")
            assert state is not None
            assert state.entity_id == f"sensor.remeha_modbus_test_hub_{sd.name}"

            # Sensor state must not be empty. See issue #107
            assert len(state.state) > 0


async def test_tank_temperature_sensors_not_added(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the tank temperature sensors are not added if the mainboard is not CU_HW."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        mainboards = coordinator.get_devices(lambda board: board.is_mainboard())
        assert mainboards[0].board_category is not None
        assert mainboards[0].board_category.type is not DeviceBoardType.CU_HW

        assert hass.states.get(TANK_TEMPERATURE_TOP) is None
        assert hass.states.get(TANK_TEMPERATURE_BOTTOM) is None


@pytest.mark.parametrize(
    "mainboards",
    [
        pytest.param([], id="no_mainboard"),
        pytest.param([MagicMock(spec=DeviceBoard, board_category=None)], id="no_category"),
    ],
)
@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_tank_temperature_sensors_not_added_without_mainboard_category(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    mainboards: list[DeviceBoard],
):
    """Test that the tank temperature sensors are not added if the mainboard type is unknown."""

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

        assert len(hass.states.async_all(domain_filter=SensorDomain)) == len(REMEHA_SENSORS)
        assert hass.states.get(TANK_TEMPERATURE_TOP) is None
        assert hass.states.get(TANK_TEMPERATURE_BOTTOM) is None


@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_tank_temperature_sensors(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test the tank temperature sensors of a heat pump boiler (CU_HW mainboard)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        mainboard = coordinator.get_devices(lambda board: board.is_mainboard())[0]
        assert mainboard.board_category is not None
        assert mainboard.board_category.type is DeviceBoardType.CU_HW

        assert len(hass.states.async_all(domain_filter=SensorDomain)) == len(REMEHA_SENSORS) + 2

        # Top: register 1120 (0x14dc), bottom: the DHW zone current temperature, register 1119 (0x14c8).
        for entity_id, expected in [(TANK_TEMPERATURE_TOP, 53.4), (TANK_TEMPERATURE_BOTTOM, 53.2)]:
            state = hass.states.get(entity_id)
            assert state is not None
            assert float(state.state) == expected
            assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
            assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
            assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT

        # The bottom temperature is the current temperature of the DHW climate.
        dhw = hass.states.get("climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None
        assert dhw.attributes["current_temperature"] == 53.2

        # Both sensors are attached to the mainboard device.
        device = dr.async_get(hass).async_get_device_by_identifier(
            identifier=(DOMAIN, str(mainboard.article_number)),
            config_entry_id=mock_config_entry.entry_id,
        )
        assert device is not None

        entity_registry = er.async_get(hass)
        for entity_id in [TANK_TEMPERATURE_TOP, TANK_TEMPERATURE_BOTTOM]:
            entry = entity_registry.async_get(entity_id)
            assert entry is not None
            assert entry.device_id == device.id


@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_tank_temperature_sensors_update(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the tank temperature sensors follow the appliance registers."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]

        # Top: 54.0 °C, bottom: 48.5 °C
        remeha_modbus_unit.load_raw({"holding": {1120: 0x1518, 1119: 0x12F2}})
        await coordinator.async_refresh()

        # Only climate zone registers changed in this test. Since the zones are updated in place,
        # the coordinator data compares equal and listeners are not notified automatically.
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        top = hass.states.get(TANK_TEMPERATURE_TOP)
        assert top is not None
        assert float(top.state) == 54.0

        bottom = hass.states.get(TANK_TEMPERATURE_BOTTOM)
        assert bottom is not None
        assert float(bottom.state) == 48.5


async def test_buffer_tank_sensors(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the buffer tank temperatures are exposed as sensors."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        bottom = hass.states.get("sensor.remeha_modbus_test_hub_buffer_temperature_bottom")
        assert bottom is not None
        assert float(bottom.state) == 24.5

        # The fixture holds 0xFFFF for the top sensor, which is how a missing sensor is reported.
        top = hass.states.get("sensor.remeha_modbus_test_hub_buffer_temperature_top")
        assert top is not None
        assert top.state == STATE_UNKNOWN
