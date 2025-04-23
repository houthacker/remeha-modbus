"""Tests for the RemehaClimateEntity."""

from unittest.mock import patch

import pytest
from homeassistant.components.climate import (
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import DOMAIN as ClimateDomain
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported, ServiceValidationError

from custom_components.remeha_modbus.api import ClimateZoneMode
from custom_components.remeha_modbus.climate import InvalidOperationContextError
from custom_components.remeha_modbus.const import (
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
)

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climates(hass: HomeAssistant, mock_modbus_client):
    """Test climates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        states = hass.states.async_all()
        assert len(states) == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate(hass: HomeAssistant, mock_modbus_client):
    """Test DHW climate entity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        assert dhw.state == "heat"
        assert dhw.attributes["hvac_action"] == HVACAction.IDLE
        assert dhw.attributes["hvac_modes"] == [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.AUTO,
        ]
        assert dhw.attributes["max_temp"] == 65
        assert dhw.attributes["min_temp"] == 10
        assert dhw.attributes["preset_mode"] == PRESET_COMFORT
        assert dhw.attributes["preset_modes"] == [
            REMEHA_PRESET_SCHEDULE_1,
            REMEHA_PRESET_SCHEDULE_2,
            REMEHA_PRESET_SCHEDULE_3,
            PRESET_COMFORT,
            PRESET_ECO,
            PRESET_NONE,
        ]
        assert dhw.attributes["temperature"] == 55
        assert dhw.attributes["current_temperature"] == 53.2
        assert dhw.attributes["target_temp_step"] == 0.5

        # Update some attributes
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_temperature",
            service_data={
                "entity_id": dhw.entity_id,
                "temperature": 60.0,
            },
            blocking=True,
        )

        dhw = hass.states.get(entity_id=dhw.entity_id)
        assert dhw.attributes["temperature"] == 60.0

        # Cannot turn a DHW climate on or off
        with pytest.raises(ServiceNotSupported):
            await hass.services.async_call(
                domain=ClimateDomain,
                service="turn_on",
                service_data={"entity_id": dhw.entity_id},
                blocking=True,
            )

        with pytest.raises(ServiceNotSupported):
            await hass.services.async_call(
                domain=ClimateDomain,
                service="turn_off",
                service_data={"entity_id": dhw.entity_id},
                blocking=True,
            )

        # Set presets
        for preset in [
            PRESET_COMFORT,
            PRESET_ECO,
            REMEHA_PRESET_SCHEDULE_1,
            REMEHA_PRESET_SCHEDULE_2,
            REMEHA_PRESET_SCHEDULE_3,
        ]:
            await hass.services.async_call(
                domain=ClimateDomain,
                service="set_preset_mode",
                service_data={"entity_id": dhw.entity_id, "preset_mode": preset},
                blocking=True,
            )
            dhw = hass.states.get(entity_id=dhw.entity_id)
            assert dhw.attributes["preset_mode"] == preset

        # Unsupported preset
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                domain=ClimateDomain,
                service="set_preset_mode",
                service_data={
                    "entity_id": dhw.entity_id,
                    "preset_mode": "i_dont_exist",
                },
                blocking=True,
            )


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_ch_climate(hass: HomeAssistant, mock_modbus_client):
    """Test CH climate entity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1 is not None

        assert circa1.state == "cool"
        assert circa1.attributes["hvac_action"] == HVACAction.COOLING
        assert circa1.attributes["hvac_modes"] == [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
        ]
        assert circa1.attributes["max_temp"] == 30
        assert circa1.attributes["min_temp"] == 6
        assert circa1.attributes["preset_mode"] == ClimateZoneMode.MANUAL.name.lower()
        assert circa1.attributes["preset_modes"] == [
            REMEHA_PRESET_SCHEDULE_1,
            REMEHA_PRESET_SCHEDULE_2,
            REMEHA_PRESET_SCHEDULE_3,
            ClimateZoneMode.MANUAL.name.lower(),
            ClimateZoneMode.ANTI_FROST.name.lower(),
        ]
        assert circa1.attributes["temperature"] == 20.0
        assert circa1.attributes["current_temperature"] == 23.2
        assert circa1.attributes["target_temp_step"] == 0.5

        # Change setpoint
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_temperature",
            service_data={
                "entity_id": circa1.entity_id,
                "temperature": circa1.attributes["max_temp"],
            },
            blocking=True,
        )

        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.attributes["temperature"] == circa1.attributes["max_temp"]

        # Set preset mode to something other than MANUAL, so the climate can't be turned off.
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": circa1.entity_id,
                "preset_mode": REMEHA_PRESET_SCHEDULE_1,
            },
            blocking=True,
        )
        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_1

        # Try turning it off
        with pytest.raises(InvalidOperationContextError):
            await hass.services.async_call(
                domain=ClimateDomain,
                service="turn_off",
                service_data={"entity_id": circa1.entity_id},
                blocking=True,
            )

        # Back to manual mode
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": circa1.entity_id,
                "preset_mode": ClimateZoneMode.MANUAL.name.lower(),
            },
            blocking=True,
        )

        # Turn off must now succeed.
        await hass.services.async_call(
            domain=ClimateDomain,
            service="turn_off",
            service_data={"entity_id": circa1.entity_id},
            blocking=True,
        )

        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.state == STATE_OFF

        # Setting mode to the same value raises no exception
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": circa1.entity_id,
                "preset_mode": ClimateZoneMode.MANUAL.name.lower(),
            },
            blocking=True,
        )
        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.attributes["preset_mode"] == ClimateZoneMode.MANUAL.name.lower()


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_hvac_mode_off(hass: HomeAssistant, mock_modbus_client):
    """Test setting HVACMode.OFF.

    This must put it in preset 'ECO' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting HVAC mode to OFF activates Preset.ECO
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_hvac_mode",
            service_data={"entity_id": dhw.entity_id, "hvac_mode": HVACMode.OFF},
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.state == STATE_OFF
        assert dhw.attributes["preset_mode"] == PRESET_ECO
        assert dhw.attributes["temperature"] == 25
        assert dhw.attributes["hvac_action"] == HVACAction.IDLE


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_hvac_mode_heat(hass: HomeAssistant, mock_modbus_client):
    """Test setting HVACMode.HEAT.

    This must put it in preset 'ECO' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda name, config: api,
        ),
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup the platform and start testing.
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting HVAC mode to HEAT activates Preset.COMFORT
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_hvac_mode",
            service_data={"entity_id": dhw.entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.state == "heat"
        assert dhw.attributes["preset_mode"] == PRESET_COMFORT
        assert dhw.attributes["temperature"] == 55
        assert dhw.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_hvac_mode_auto(hass: HomeAssistant, mock_modbus_client):
    """Test setting HVACMode.AUTO.

    This must put it in preset 'SCHEDULE_x' and return the correct temperature setpoint,
    parsed from the selected schedule..
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Select a schedule which will be shown as a preset after HVACMode is set to AUTO.
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": dhw.entity_id,
                "preset_mode": REMEHA_PRESET_SCHEDULE_2,
            },
            blocking=True,
        )

        # Setting HVAC mode to AUTO activates the (previously) selected schedule.
        # This will return the preset SCHEDULE_x
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_hvac_mode",
            service_data={"entity_id": dhw.entity_id, "hvac_mode": HVACMode.AUTO},
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.state == "auto"
        assert dhw.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_2
        assert dhw.attributes["hvac_action"] == HVACAction.HEATING

        # TODO handle reading schedules
        assert dhw.attributes["temperature"] == -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_preset_mode_schedule(
    hass: HomeAssistant, mock_modbus_client
):
    """Test setting preset_mode to SCHEDULE_x (1-3).

    This must put it in hvac_mode 'AUTO' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting preset to SCHEDULE_x sets hvac_mode to HVACMode.AUTO
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": dhw.entity_id,
                "preset_mode": REMEHA_PRESET_SCHEDULE_1,
            },
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.state == "auto"
        assert dhw.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_1
        assert dhw.attributes["hvac_action"] == HVACAction.HEATING

        # TODO handle reading schedudes 1-3
        assert dhw.attributes["temperature"] == -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_preset_mode_eco(hass: HomeAssistant, mock_modbus_client):
    """Test setting preset_mode to ECO.

    This must put it in hvac_mode 'OFF' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # Then setup platform.
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting preset to ECO sets hvac_mode to HVACMode.OFF
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": dhw.entity_id,
                "preset_mode": PRESET_ECO,
            },
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.state == "off"
        assert dhw.attributes["preset_mode"] == PRESET_ECO
        assert dhw.attributes["hvac_action"] == HVACAction.IDLE
        assert dhw.attributes["temperature"] == 25


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_preset_mode_comfort(hass: HomeAssistant, mock_modbus_client):
    """Test setting preset_mode to COMFORT.

    This must put it in hvac_mode 'HEAT' and return the correct temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting preset to SCHEDULE_x sets hvac_mode to HVACMode.AUTO
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": dhw.entity_id,
                "preset_mode": PRESET_COMFORT,
            },
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.state == "heat"
        assert dhw.attributes["preset_mode"] == PRESET_COMFORT
        assert dhw.attributes["hvac_action"] == HVACAction.HEATING
        assert dhw.attributes["temperature"] == 55


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_preset_mode_none(hass: HomeAssistant, mock_modbus_client):
    """Test setting preset_mode to NONE.

    This must raise an exception since the NONE preset can only be set implicitly.
    Preset NONE is set when api.ClimateZone.mode has an unsupported value.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting preset to NONE raises an exception.
        with pytest.raises(InvalidOperationContextError):
            await hass.services.async_call(
                domain=ClimateDomain,
                service="set_preset_mode",
                service_data={
                    "entity_id": dhw.entity_id,
                    "preset_mode": PRESET_NONE,
                },
                blocking=True,
            )
