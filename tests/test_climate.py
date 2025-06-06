"""Tests for the RemehaClimateEntity."""

from datetime import datetime
from unittest.mock import patch

import pytest
from dateutil import tz
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

from custom_components.remeha_modbus.climate import ClimateZone, InvalidClimateContext
from custom_components.remeha_modbus.const import (
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
    ClimateZoneMode,
)

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climates(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test climates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter="climate")) == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test DHW climate entity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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
async def test_ch_climate(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test CH climate entity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1 is not None

        assert circa1.state == "heat_cool"
        assert circa1.attributes["hvac_action"] == HVACAction.COOLING
        assert circa1.attributes["hvac_modes"] == [
            HVACMode.OFF,
            HVACMode.HEAT_COOL,
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

        # Turn it off.
        await hass.services.async_call(
            domain=ClimateDomain,
            service="turn_off",
            service_data={"entity_id": circa1.entity_id},
            blocking=True,
        )

        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.state == STATE_OFF

        # Setting HVAC mode influences preset mode
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_hvac_mode",
            service_data={
                "entity_id": circa1.entity_id,
                "hvac_mode": HVACMode.AUTO,
            },
            blocking=True,
        )

        # Preset mode must have changed to previously selected schedule.
        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.state == "auto"
        assert circa1.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_1

        # Setting HVAC mode influences preset mode
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_hvac_mode",
            service_data={
                "entity_id": circa1.entity_id,
                "hvac_mode": HVACMode.HEAT_COOL,
            },
            blocking=True,
        )

        # Preset mode must have changed to manual
        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.attributes["preset_mode"] == ClimateZoneMode.MANUAL.name.lower()

        # Change preset to schedule
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


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_ch_temporary_setpoint_override(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test overriding setpoint of CH climate.

    Reading the current setpoint for CH in scheduling mode is not yet supported.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1 is not None

        # Change preset to schedule
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_preset_mode",
            service_data={
                "entity_id": circa1.entity_id,
                "preset_mode": REMEHA_PRESET_SCHEDULE_1,
            },
            blocking=True,
        )

        # When in scheduling mode, reading the current setpoint is not yet supported.
        circa1 = hass.states.get(entity_id="climate.remeha_modbus_test_hub_circa1")
        assert circa1.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_1
        assert circa1.attributes["temperature"] == -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_temporary_setpoint_override(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test temporary setpoint override of a DHW climate entity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None
        assert dhw.attributes["preset_mode"] == PRESET_COMFORT
        assert dhw.attributes["temperature"] == 55.0

        # Change preset to schedule
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
        assert dhw.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_1

        # Current setpoint must be resolved when in scheduling mode.
        current_setpoint = dhw.attributes["temperature"]
        assert current_setpoint != -1

        # Overwrite the current setpoint
        new_setpoint = current_setpoint + 1
        await hass.services.async_call(
            domain=ClimateDomain,
            service="set_temperature",
            service_data={
                "entity_id": dhw.entity_id,
                "temperature": new_setpoint,
            },
            blocking=True,
        )

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw.attributes["preset_mode"] == REMEHA_PRESET_SCHEDULE_1

        # Current setpoint must have been updated
        assert dhw.attributes["temperature"] == new_setpoint

        # And temporary override end time must be set.
        zone: ClimateZone = await api.async_read_zone(id=2)
        assert zone.is_domestic_hot_water()
        assert zone.temporary_setpoint_end_time > datetime.now(
            tz=tz.gettz(name=hass.config.time_zone)
        )


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_hvac_mode_off(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting HVACMode.OFF.

    This must put it in preset 'ECO' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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
async def test_dhw_climate_hvac_mode_heat(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting HVACMode.HEAT.

    This must put it in preset 'ECO' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with (
        patch(
            "custom_components.remeha_modbus.api.RemehaApi.create",
            new=lambda *args, **kwargs: api,
        ),
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup the platform and start testing.
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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
async def test_dhw_climate_hvac_mode_auto(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting HVACMode.AUTO.

    This must put it in preset 'SCHEDULE_x' and return the correct temperature setpoint,
    parsed from the selected schedule..
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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

        # Current setpoint changes over time due to schedule, so it must not be 'unset'
        assert dhw.attributes["temperature"] != -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_preset_mode_schedule(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting preset_mode to SCHEDULE_x (1-3).

    This must put it in hvac_mode 'AUTO' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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

        # Current setpoint changes over time due to schedule, so it must not be 'unset'
        assert dhw.attributes["temperature"] != -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_climate_preset_mode_eco(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting preset_mode to ECO.

    This must put it in hvac_mode 'OFF' and return the correct (lowered) temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # Then setup platform.
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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
async def test_dhw_climate_preset_mode_comfort(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting preset_mode to COMFORT.

    This must put it in hvac_mode 'HEAT' and return the correct temperature setpoint.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

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
async def test_dhw_climate_preset_mode_none(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test setting preset_mode to NONE.

    This must raise an exception since the NONE preset can only be set implicitly.
    Preset NONE is set when api.ClimateZone.mode has an unsupported value.
    """

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        # In the modbus_store.json file, the zone pump is not running. So update that before we actually start.
        await mock_modbus_client.set_zone_pump_state(zone_id=2, state=True)

        # Then setup platform.
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        dhw = hass.states.get(entity_id="climate.remeha_modbus_test_hub_dhw")
        assert dhw is not None

        # Setting preset to NONE raises an exception.
        with pytest.raises(InvalidClimateContext):
            await hass.services.async_call(
                domain=ClimateDomain,
                service="set_preset_mode",
                service_data={
                    "entity_id": dhw.entity_id,
                    "preset_mode": PRESET_NONE,
                },
                blocking=True,
            )
