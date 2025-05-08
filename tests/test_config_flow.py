"""Test the Remeha Modbus config flow."""

import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from dateutil import tz
from homeassistant import config_entries
from homeassistant.components.weather.const import DOMAIN as WeatherDomain
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.entity_component import EntityComponent

from custom_components.remeha_modbus.const import (
    CONFIG_AUTO_SCHEDULE,
    CONNECTION_RTU_OVER_TCP,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DHW_BOILER_CONFIG_SECTION,
    DHW_BOILER_ENERGY_LABEL,
    DHW_BOILER_HEAT_LOSS_RATE,
    DHW_BOILER_VOLUME,
    DOMAIN,
    HA_CONFIG_MINOR_VERSION,
    HA_CONFIG_VERSION,
    MODBUS_DEVICE_ADDRESS,
    MODBUS_SERIAL_BAUDRATE,
    MODBUS_SERIAL_BYTESIZE,
    MODBUS_SERIAL_METHOD,
    MODBUS_SERIAL_METHOD_RTU,
    MODBUS_SERIAL_PARITY,
    MODBUS_SERIAL_PARITY_NONE,
    MODBUS_SERIAL_STOPBITS,
    PV_ANNUAL_EFFICIENCY_DECREASE,
    PV_CONFIG_SECTION,
    PV_INSTALLATION_DATE,
    PV_NOMINAL_POWER_WP,
    PV_ORIENTATION,
    PV_TILT,
    WEATHER_ENTITY_ID,
    PVSystemOrientation,
)
from tests.conftest import MockWeatherEntity, get_api, setup_platform


async def test_generic_config_invalid_data(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that invalid configuration data raises an exception."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with pytest.raises(InvalidData):
        # Fill in the form correctly
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test_serial_modbus_hub",
                CONF_TYPE: CONNECTION_SERIAL,
                MODBUS_DEVICE_ADDRESS: "not-a-number",
            },
        )

    await hass.async_block_till_done()


async def test_config_modbus_serial(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test for modbus serial configuration setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Fill in the form correctly
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "test_serial_modbus_hub", CONF_TYPE: CONNECTION_SERIAL},
    )
    await hass.async_block_till_done()

    # We should have been presented with the 2nd form, to fill in the
    # serial connection details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            MODBUS_SERIAL_BAUDRATE: 9600,
            MODBUS_SERIAL_BYTESIZE: 8,
            MODBUS_SERIAL_METHOD: MODBUS_SERIAL_METHOD_RTU,
            MODBUS_SERIAL_PARITY: MODBUS_SERIAL_PARITY_NONE,
            CONF_PORT: "/dev/ttyUSB0",
            MODBUS_SERIAL_STOPBITS: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Remeha Modbus"
    assert result["data"] == {
        CONF_NAME: "test_serial_modbus_hub",
        CONF_TYPE: CONNECTION_SERIAL,
        MODBUS_DEVICE_ADDRESS: 100,
        MODBUS_SERIAL_BAUDRATE: 9600,
        MODBUS_SERIAL_BYTESIZE: 8,
        MODBUS_SERIAL_METHOD: MODBUS_SERIAL_METHOD_RTU,
        MODBUS_SERIAL_PARITY: MODBUS_SERIAL_PARITY_NONE,
        CONF_PORT: "/dev/ttyUSB0",
        MODBUS_SERIAL_STOPBITS: 2,
        CONFIG_AUTO_SCHEDULE: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_modbus_socket(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test for modbus socket configuration setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Fill in the form with a socket modbus connection type.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "test_socket_modbus_hub", CONF_TYPE: CONNECTION_RTU_OVER_TCP},
    )
    await hass.async_block_till_done()

    # We should have been presented with the 2nd form, to fill in the
    # socket connection details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_PORT: 502}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Remeha Modbus"
    assert result["data"] == {
        CONF_NAME: "test_socket_modbus_hub",
        CONF_TYPE: CONNECTION_RTU_OVER_TCP,
        MODBUS_DEVICE_ADDRESS: 100,
        CONF_HOST: "192.168.1.1",
        CONF_PORT: 502,
        CONFIG_AUTO_SCHEDULE: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_auto_scheduling(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test for modbus socket configuration setup with auto scheduling."""

    # Prepare hass by adding a weather entity.
    component = EntityComponent(
        logger=logging.getLogger("weather"),
        domain=WeatherDomain,
        hass=hass,
        scan_interval=timedelta(seconds=-1),
    )

    # Stop timers when HA stops.
    component.register_shutdown()

    # Add fake weather entity.
    entity = MockWeatherEntity(entity_id="weather.fake_weather")
    await component.async_add_entities([entity])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Fill in the form with a socket modbus connection type.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test_socket_modbus_hub",
            CONF_TYPE: CONNECTION_RTU_OVER_TCP,
            CONFIG_AUTO_SCHEDULE: True,
        },
    )
    await hass.async_block_till_done()

    # We should have been presented with the 2nd form, to fill in the
    # auto schedule details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            WEATHER_ENTITY_ID: "weather.fake_weather",
            PV_CONFIG_SECTION: {
                PV_NOMINAL_POWER_WP: 1375,
                PV_ORIENTATION: PVSystemOrientation.SOUTH,
                PV_TILT: 30,
                PV_ANNUAL_EFFICIENCY_DECREASE: 0.54,
                PV_INSTALLATION_DATE: datetime(
                    year=2025,
                    month=3,
                    day=14,
                    hour=15,
                    minute=6,
                    second=26,
                    tzinfo=tz.gettz(hass.config.time_zone),
                ),
            },
            DHW_BOILER_CONFIG_SECTION: {
                DHW_BOILER_VOLUME: 300,
                DHW_BOILER_HEAT_LOSS_RATE: 2.19,
            },
        },
    )

    # We should have been presented with the 3rd form, to fill in the
    # socket connection details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_PORT: 502}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Remeha Modbus"
    assert result["data"] == {
        CONF_NAME: "test_socket_modbus_hub",
        CONF_TYPE: CONNECTION_RTU_OVER_TCP,
        MODBUS_DEVICE_ADDRESS: 100,
        CONF_HOST: "192.168.1.1",
        CONF_PORT: 502,
        CONFIG_AUTO_SCHEDULE: True,
        WEATHER_ENTITY_ID: "weather.fake_weather",
        PV_CONFIG_SECTION: {
            PV_NOMINAL_POWER_WP: 1375,
            PV_ORIENTATION: PVSystemOrientation.SOUTH,
            PV_TILT: 30,
            PV_ANNUAL_EFFICIENCY_DECREASE: 0.54,
            PV_INSTALLATION_DATE: datetime(
                year=2025,
                month=3,
                day=14,
                hour=15,
                minute=6,
                second=26,
                tzinfo=tz.gettz(hass.config.time_zone),
            ),
        },
        DHW_BOILER_CONFIG_SECTION: {
            DHW_BOILER_VOLUME: 300,
            DHW_BOILER_HEAT_LOSS_RATE: 2.19,
            DHW_BOILER_ENERGY_LABEL: None,
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_auto_scheduling_no_installation_date(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test for modbus socket configuration setup with auto scheduling without a pv installation date."""

    # Prepare hass by adding a weather entity.
    component = EntityComponent(
        logger=logging.getLogger("weather"),
        domain=WeatherDomain,
        hass=hass,
        scan_interval=timedelta(seconds=-1),
    )

    # Stop timers when HA stops.
    component.register_shutdown()

    # Add fake weather entity.
    entity = MockWeatherEntity(entity_id="weather.fake_weather")
    await component.async_add_entities([entity])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Fill in the form with a socket modbus connection type.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test_socket_modbus_hub",
            CONF_TYPE: CONNECTION_RTU_OVER_TCP,
            CONFIG_AUTO_SCHEDULE: True,
        },
    )
    await hass.async_block_till_done()

    # We should have been presented with the 2nd form, to fill in the
    # auto schedule details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            WEATHER_ENTITY_ID: "weather.fake_weather",
            PV_CONFIG_SECTION: {
                PV_NOMINAL_POWER_WP: 1375,
                PV_ORIENTATION: PVSystemOrientation.SOUTH,
                PV_TILT: 30,
                PV_ANNUAL_EFFICIENCY_DECREASE: 0.54,
            },
            DHW_BOILER_CONFIG_SECTION: {
                DHW_BOILER_VOLUME: 300,
                DHW_BOILER_HEAT_LOSS_RATE: 2.19,
            },
        },
    )

    # We should have been presented with the 3rd form, to fill in the
    # socket connection details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_PORT: 502}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Remeha Modbus"
    assert result["data"] == {
        CONF_NAME: "test_socket_modbus_hub",
        CONF_TYPE: CONNECTION_RTU_OVER_TCP,
        MODBUS_DEVICE_ADDRESS: 100,
        CONF_HOST: "192.168.1.1",
        CONF_PORT: 502,
        CONFIG_AUTO_SCHEDULE: True,
        WEATHER_ENTITY_ID: "weather.fake_weather",
        PV_CONFIG_SECTION: {
            PV_NOMINAL_POWER_WP: 1375,
            PV_ORIENTATION: "S",
            PV_TILT: 30,
            PV_ANNUAL_EFFICIENCY_DECREASE: 0.54,
            PV_INSTALLATION_DATE: None,
        },
        DHW_BOILER_CONFIG_SECTION: {
            DHW_BOILER_VOLUME: 300,
            DHW_BOILER_HEAT_LOSS_RATE: 2.19,
            DHW_BOILER_ENERGY_LABEL: None,
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_reconfigure_non_unique_id(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
) -> None:
    """Test that reconfiguring the modbus connection fails if the hub name is changed as well."""
    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # First setup the platform with the mocked ConfigEntry
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(domain=DOMAIN)
        assert len(entries) == 1

        config_entry: ConfigEntry = entries[0]

        # Then update the connection to another connection type.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: CONNECTION_TCP}
        )
        await hass.async_block_till_done()

        # We should have been presented with the 2nd form, to fill in the
        # socket connection details.
        assert result["type"] is FlowResultType.FORM

        # Fill in the details, check the result.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "also.does.not.matter", CONF_PORT: 502}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT

        entries = hass.config_entries.async_entries(domain=DOMAIN)

        # No extra entries must be added
        assert len(entries) == 1

        # But the fields must be updated.
        config_entry = entries[0]
        assert config_entry.data == {
            CONF_NAME: "test_hub",
            CONF_TYPE: CONNECTION_TCP,
            MODBUS_DEVICE_ADDRESS: 100,
            CONF_HOST: "also.does.not.matter",
            CONF_PORT: 502,
            CONFIG_AUTO_SCHEDULE: False,
        }


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
@pytest.mark.parametrize("mock_config_entry", [{"version": 1, "minor_version": 0}], indirect=True)
async def test_migrate_from_config_v1_0(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
) -> None:
    """Test the migration of config v1.0 to whatever the current version is."""

    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 0

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # First setup the platform with the mocked ConfigEntry
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(domain=DOMAIN)
        assert len(entries) == 1

        # Must have been updated.
        config_entry: ConfigEntry = entries[0]
        assert config_entry.version == HA_CONFIG_VERSION
        assert config_entry.minor_version == HA_CONFIG_MINOR_VERSION
