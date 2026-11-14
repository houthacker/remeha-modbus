"""Tests for the RemehaWaterHeaterEntity."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from aio_remeha_modbus.gtw08.climate_zone import (
    ClimateZone,
    ClimateZoneFunction,
    ClimateZoneRunningMode,
)
from aio_remeha_modbus.gtw08.system_discovery_table import (
    DeviceBoard,
    DeviceBoardCategory,
    DeviceBoardType,
)
from homeassistant.components.water_heater.const import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_GAS,
    STATE_HEAT_PUMP,
    WaterHeaterCapabilityAttribute,
)
from homeassistant.components.water_heater.const import (
    DOMAIN as WaterHeaterDomain,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.const import (
    REMEHA_PRESET_SCHEDULE_1,
    WATER_HEATER_STATE_OIL,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import MainboardNotFound
from custom_components.remeha_modbus.water_heater import (
    RemehaElectricWaterHeaterEntity,
    RemehaGasWaterHeaterEntity,
    RemehaHeatPumpBoilerEntity,
    RemehaOilWaterHeaterEntity,
    RemehaWaterHeaterEntity,
)

from .conftest import setup_platform

ENTITY_ID = "water_heater.remeha_modbus_test_hub_dhw"

# Each fixture yields a different main board type and thus a different water heater type,
# which is mainly distinguished by its `_attr_operation_list`.
WATER_HEATER_TYPES = pytest.mark.parametrize(
    ("remeha_modbus_unit", "entity_type", "manual_operation"),
    [
        ("modbus_store_gas.json", RemehaGasWaterHeaterEntity, STATE_GAS),
        ("modbus_store_oil.json", RemehaOilWaterHeaterEntity, WATER_HEATER_STATE_OIL),
        ("modbus_store.json", RemehaElectricWaterHeaterEntity, STATE_HEAT_PUMP),
        ("azorra_ace_store.json", RemehaHeatPumpBoilerEntity, STATE_HEAT_PUMP),
    ],
    indirect=["remeha_modbus_unit"],
)


async def _setup(hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit):
    with patch("aio_remeha_modbus.gtw08.GTW08", new=lambda *args, **kwargs: remeha_api):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

    coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
    return coordinator


def _dhw_zone(coordinator: RemehaUpdateCoordinator) -> ClimateZone:
    return coordinator.get_climates(lambda zone: zone.is_domestic_hot_water())[0]


async def _call(hass: HomeAssistant, service: str, **data) -> None:
    await hass.services.async_call(
        domain=WaterHeaterDomain,
        service=service,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )


@WATER_HEATER_TYPES
async def test_water_heater_type(
    hass: HomeAssistant,
    *,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_type: type[RemehaWaterHeaterEntity],
    manual_operation: str,
):
    """Test that the main board type determines the water heater type and its attributes."""

    coordinator = await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)

    entity = RemehaWaterHeaterEntity.create_instance(
        remeha_api, coordinator, _dhw_zone(coordinator).id
    )
    assert type(entity) is entity_type
    assert entity.device_info is not None
    assert entity.calorifier_hysteresis is not None
    assert entity.tank_temperature_top is not None

    assert len(hass.states.async_all(domain_filter=WaterHeaterDomain)) == 1
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == REMEHA_PRESET_SCHEDULE_1
    operation_list = state.attributes[WaterHeaterCapabilityAttribute.OPERATION_LIST]
    assert operation_list == entity.operation_list
    assert operation_list[0] == manual_operation
    assert state.attributes["min_temp"] == 10.0
    assert state.attributes["max_temp"] == 65.0
    assert state.attributes["current_temperature"] == 53.4
    assert state.attributes[ATTR_TEMPERATURE] == 25.0
    assert state.attributes[ATTR_AWAY_MODE] == STATE_OFF


@WATER_HEATER_TYPES
async def test_water_heater_set_operation_mode(
    hass: HomeAssistant,
    *,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_type: type[RemehaWaterHeaterEntity],
    manual_operation: str,
):
    """Test that every operation in the operation list can be selected and is reported back."""

    coordinator = await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)
    entity = RemehaWaterHeaterEntity.create_instance(
        remeha_api, coordinator, _dhw_zone(coordinator).id
    )
    assert type(entity) is entity_type
    assert entity.operation_list

    # Reverse, so the initially active schedule_1 is not the first mode to be set.
    for operation_mode in reversed(entity.operation_list):
        await _call(hass, SERVICE_SET_OPERATION_MODE, **{ATTR_OPERATION_MODE: operation_mode})

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == operation_mode


@WATER_HEATER_TYPES
async def test_water_heater_set_temperature(
    hass: HomeAssistant,
    *,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_type: type[RemehaWaterHeaterEntity],
    manual_operation: str,
):
    """Test setting the temperature in manual operation."""

    await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)

    # DHW setpoints cannot be overridden while scheduling, so switch to manual operation first.
    await _call(hass, SERVICE_SET_OPERATION_MODE, **{ATTR_OPERATION_MODE: manual_operation})
    await _call(hass, SERVICE_SET_TEMPERATURE, **{ATTR_TEMPERATURE: 60.0})

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == manual_operation
    assert state.attributes[ATTR_TEMPERATURE] == 60.0


@WATER_HEATER_TYPES
async def test_water_heater_set_temperature_with_operation_mode(
    hass: HomeAssistant,
    *,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_type: type[RemehaWaterHeaterEntity],
    manual_operation: str,
):
    """Test that the setpoint applies to the current operation before switching to the new one."""

    await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)

    # Setpoints are ignored while scheduling, but the operation mode is still switched.
    await _call(
        hass,
        SERVICE_SET_TEMPERATURE,
        **{ATTR_TEMPERATURE: 60.0, ATTR_OPERATION_MODE: manual_operation},
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == manual_operation
    assert state.attributes[ATTR_TEMPERATURE] != 60.0

    # In manual operation, the setpoint is stored as the manual setpoint before switching to eco.
    await _call(
        hass,
        SERVICE_SET_TEMPERATURE,
        **{ATTR_TEMPERATURE: 60.0, ATTR_OPERATION_MODE: STATE_ECO},
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ECO

    await _call(hass, SERVICE_SET_OPERATION_MODE, **{ATTR_OPERATION_MODE: manual_operation})
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 60.0


async def test_water_heater_away_mode(
    hass: HomeAssistant, *, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test turning away mode on and off."""

    coordinator = await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)
    zone = _dhw_zone(coordinator)

    with (
        patch.object(ClimateZone, "async_enable_holiday_mode") as enable_holiday_mode,
        patch.object(
            ClimateZone,
            "running_mode",
            new_callable=PropertyMock,
            return_value=ClimateZoneRunningMode.HOLIDAY,
        ),
    ):
        await _call(hass, SERVICE_SET_AWAY_MODE, **{ATTR_AWAY_MODE: True})

        enable_holiday_mode.assert_awaited_once()
        assert enable_holiday_mode.await_args is not None
        start, end = enable_holiday_mode.await_args.args
        assert start < end

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.attributes[ATTR_AWAY_MODE] == STATE_ON

    with patch.object(ClimateZone, "async_disable_holiday_mode") as disable_holiday_mode:
        await _call(hass, SERVICE_SET_AWAY_MODE, **{ATTR_AWAY_MODE: False})

        disable_holiday_mode.assert_awaited_once()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.attributes[ATTR_AWAY_MODE] == STATE_OFF

    assert zone.running_mode is not ClimateZoneRunningMode.HOLIDAY


async def test_water_heater_unavailable_when_zone_disabled(
    hass: HomeAssistant, *, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the water heater is unavailable if its zone function is disabled."""

    coordinator = await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)

    with patch.object(
        ClimateZone,
        "function",
        new_callable=PropertyMock,
        return_value=ClimateZoneFunction.DISABLED,
    ):
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def test_create_instance_errors(
    hass: HomeAssistant, *, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that create_instance refuses to create an entity in unsupported situations."""

    coordinator = await _setup(hass, remeha_api, mock_config_entry, remeha_modbus_unit)
    dhw_zone_id = _dhw_zone(coordinator).id
    ch_zone_id = coordinator.get_climates(lambda zone: zone.is_central_heating())[0].id

    with (
        patch.object(coordinator, "get_devices", return_value=[]),
        pytest.raises(MainboardNotFound, match="No mainboard found"),
    ):
        RemehaWaterHeaterEntity.create_instance(remeha_api, coordinator, dhw_zone_id)

    with (
        patch.object(
            coordinator,
            "get_devices",
            return_value=[MagicMock(spec=DeviceBoard, board_category=None)],
        ),
        pytest.raises(ValueError, match="does not designate a category"),
    ):
        RemehaWaterHeaterEntity.create_instance(remeha_api, coordinator, dhw_zone_id)

    with (
        patch.object(
            coordinator,
            "get_devices",
            return_value=[
                MagicMock(
                    spec=DeviceBoard,
                    board_category=DeviceBoardCategory(type=DeviceBoardType.MK, generation=1),
                )
            ],
        ),
        pytest.raises(ValueError, match="Unsupported device board type MK"),
    ):
        RemehaWaterHeaterEntity.create_instance(remeha_api, coordinator, dhw_zone_id)

    with (
        patch.object(coordinator, "get_climate", return_value=None),
        pytest.raises(ValueError, match="No existing ClimateZone"),
    ):
        RemehaWaterHeaterEntity.create_instance(remeha_api, coordinator, dhw_zone_id)

    with pytest.raises(ValueError, match="Unsupported zone type"):
        RemehaWaterHeaterEntity.create_instance(remeha_api, coordinator, ch_zone_id)
