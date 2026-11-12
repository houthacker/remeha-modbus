"""Tests for NumberEntity instances in the Remeha Modbus integration."""

from unittest.mock import patch

import pytest
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number.const import ATTR_MAX, ATTR_MIN, ATTR_STEP
from homeassistant.components.number.const import DOMAIN as NumberDomain
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.remeha_modbus.const import DOMAIN

from .conftest import setup_platform


async def test_climates(hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit):
    """Test climates."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        # DhwHysteresisEntity + RemehaSummerWinterNumber + RemehaNeutralBandNumber
        # + RemehaBivalentTemperature + RemehaCompressorMinTemperature.
        assert len(hass.states.async_all(domain_filter="number")) == 5


async def test_dhw_hysteresis(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test a single DhwHysteresisEntity."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        hysteresis = hass.states.get("number.remeha_modbus_test_hub_dhw_hysteresis")
        assert hysteresis is not None
        assert hysteresis.state == "3.0"
        assert hysteresis.domain == "number"
        assert hysteresis.name == "Remeha Modbus test_hub dhw_hysteresis"

        # Update the state
        # Update some attributes
        await hass.services.async_call(
            domain=NumberDomain,
            service="set_value",
            service_data={
                "entity_id": hysteresis.entity_id,
                "value": 20.0,
            },
            blocking=True,
        )

        hysteresis = hass.states.get(hysteresis.entity_id)
        assert hysteresis is not None
        assert hysteresis.state == "20.0"


async def test_summer_winter(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test the appliance summer/winter threshold number entity (AP073)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        summer_winter = hass.states.get("number.remeha_modbus_test_hub_summer_winter_threshold")
        assert summer_winter is not None
        assert summer_winter.state == "22.0"
        assert summer_winter.domain == "number"

        await hass.services.async_call(
            domain=NumberDomain,
            service="set_value",
            service_data={
                "entity_id": summer_winter.entity_id,
                "value": 25.0,
            },
            blocking=True,
        )

        summer_winter = hass.states.get(summer_winter.entity_id)
        assert summer_winter is not None
        assert summer_winter.state == "25.0"


async def test_neutral_band(hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit):
    """Test the appliance neutral-band number entity (AP075)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        neutral_band = hass.states.get("number.remeha_modbus_test_hub_neutral_band_summer_winter")
        assert neutral_band is not None
        assert neutral_band.state == "4.0"

        await hass.services.async_call(
            domain=NumberDomain,
            service="set_value",
            service_data={"entity_id": neutral_band.entity_id, "value": 5.0},
            blocking=True,
        )

        neutral_band = hass.states.get(neutral_band.entity_id)
        assert neutral_band is not None
        assert neutral_band.state == "5.0"


@pytest.mark.parametrize(
    ("entity_id", "register", "initial", "min_value", "max_value", "new_value"),
    [
        pytest.param(
            "number.remeha_modbus_test_hub_bivalent_temperature",
            487,
            "5.0",
            -10.0,
            20.0,
            -7.0,
            id="bivalent_temperature_HP000",
        ),
        pytest.param(
            "number.remeha_modbus_test_hub_compressor_min_temperature",
            489,
            "-20.0",
            -20.0,
            5.0,
            3.0,
            id="compressor_min_temperature_HP051",
        ),
    ],
)
async def test_heat_pump_temperature_numbers(
    *,
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_id: str,
    register: int,
    initial: str,
    min_value: float,
    max_value: float,
    new_value: float,
):
    """Test the appliance-level heat pump temperature number entities (HP000, HP051)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == initial
        assert state.attributes[ATTR_MIN] == min_value
        assert state.attributes[ATTR_MAX] == max_value
        assert state.attributes[ATTR_STEP] == 1
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
        assert state.attributes[ATTR_DEVICE_CLASS] == NumberDeviceClass.TEMPERATURE

        await hass.services.async_call(
            domain=NumberDomain,
            service="set_value",
            service_data={"entity_id": entity_id, "value": new_value},
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == str(new_value)

        # The register holds an int16 with a scale of 0.01.
        (raw,) = await remeha_api.async_read_registers(register, struct_format=">h")
        assert raw == int(new_value * 100)


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        pytest.param("number.remeha_modbus_test_hub_bivalent_temperature", -11.0, id="HP000_low"),
        pytest.param("number.remeha_modbus_test_hub_bivalent_temperature", 21.0, id="HP000_high"),
        pytest.param(
            "number.remeha_modbus_test_hub_compressor_min_temperature", -21.0, id="HP051_low"
        ),
        pytest.param(
            "number.remeha_modbus_test_hub_compressor_min_temperature", 6.0, id="HP051_high"
        ),
    ],
)
async def test_heat_pump_temperature_numbers_out_of_range(
    *,
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_id: str,
    value: float,
):
    """Test that out-of-range values for HP000 and HP051 are rejected."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        initial = hass.states.get(entity_id)
        assert initial is not None

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                domain=NumberDomain,
                service="set_value",
                service_data={"entity_id": entity_id, "value": value},
                blocking=True,
            )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == initial.state


@pytest.mark.parametrize(
    ("entity_id", "register"),
    [
        pytest.param("number.remeha_modbus_test_hub_bivalent_temperature", 487, id="HP000"),
        pytest.param("number.remeha_modbus_test_hub_compressor_min_temperature", 489, id="HP051"),
    ],
)
async def test_heat_pump_temperature_numbers_not_an_int(
    *,
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    entity_id: str,
    register: int,
):
    """Test that fractional values for HP000 and HP051 are rejected, since only whole degrees are supported."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        initial = hass.states.get(entity_id)
        assert initial is not None
        (initial_raw,) = await remeha_api.async_read_registers(register, struct_format=">h")

        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                domain=NumberDomain,
                service="set_value",
                service_data={"entity_id": entity_id, "value": 3.5},
                blocking=True,
            )

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "value_not_an_int"
        assert exc_info.value.translation_placeholders == {"value": "3.5"}

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == initial.state

        (raw,) = await remeha_api.async_read_registers(register, struct_format=">h")
        assert raw == initial_raw


async def test_heat_pump_temperature_numbers_device(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the HP000 and HP051 entities are linked to the mainboard device."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        summer_winter = entity_registry.async_get(
            "number.remeha_modbus_test_hub_summer_winter_threshold"
        )
        assert summer_winter is not None
        assert summer_winter.device_id is not None

        for entity_id, unique_id in [
            ("number.remeha_modbus_test_hub_bivalent_temperature", "bivalent_temperature"),
            (
                "number.remeha_modbus_test_hub_compressor_min_temperature",
                "compressor_min_temperature",
            ),
        ]:
            entry = entity_registry.async_get(entity_id)
            assert entry is not None
            assert entry.unique_id == unique_id
            assert entry.device_id == summer_winter.device_id


@pytest.mark.parametrize("remeha_modbus_unit", ["modbus_store_no_dhw_climate.json"], indirect=True)
async def test_dhw_hysteresis_unavailable(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test a single DhwHysteresisEntity."""

    with patch(
        "custom_components.remeha_modbus.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        hysteresis = hass.states.get("number.remeha_modbus_test_hub_dhw_hysteresis")
        assert hysteresis is None
