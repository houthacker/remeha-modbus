"""Fixtures for testing."""

import uuid
from collections.abc import Generator
from datetime import tzinfo
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.components.weather import WeatherEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt
from homeassistant.util.json import JsonObjectType
from pymodbus.client import ModbusBaseClient
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockEntity,
    load_json_object_fixture,
)

from custom_components.remeha_modbus.api import ConnectionType, RemehaApi
from custom_components.remeha_modbus.const import (
    CONFIG_AUTO_SCHEDULE,
    CONNECTION_RTU_OVER_TCP,
    DHW_BOILER_CONFIG_SECTION,
    DHW_BOILER_ENERGY_LABEL,
    DHW_BOILER_HEAT_LOSS_RATE,
    DHW_BOILER_VOLUME,
    DOMAIN,
    HA_CONFIG_MINOR_VERSION,
    HA_CONFIG_VERSION,
    MODBUS_DEVICE_ADDRESS,
    PV_ANNUAL_EFFICIENCY_DECREASE,
    PV_CONFIG_SECTION,
    PV_INSTALLATION_DATE,
    PV_NOMINAL_POWER_WP,
    PV_ORIENTATION,
    PV_TILT,
    REMEHA_ZONE_RESERVED_REGISTERS,
    WEATHER_ENTITY_ID,
    BoilerEnergyLabel,
    ZoneRegisters,
)


class MockWeatherEntity(MockEntity, WeatherEntity):
    """Mock weather entity."""

    def __init__(self, **values):
        """Create a new MockWeatherEntity."""
        super().__init__(**values)


def get_api(
    mock_modbus_client: ModbusBaseClient,
    name: str = "test_api",
    device_address: int = 100,
) -> RemehaApi:
    """Create a new RemehaApi instance with a mocked modbus client."""

    # mock_modbus_client MUST be a mock, otherwise a real connection might be made and mess up the appliance.
    if not isinstance(mock_modbus_client, Mock):
        pytest.fail(
            f"Trying to create RemehaApi with non-mocked modbus client type {type(mock_modbus_client).__qualname__}."
        )

    return RemehaApi(
        name=name,
        connection_type=ConnectionType.RTU_OVER_TCP,
        client=mock_modbus_client,
        device_address=device_address,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.remeha_modbus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_modbus_client(request) -> Generator[AsyncMock]:
    """Create a mocked pymodbus client.

    The registers for the modbus client are retrieved from the `request` and will be
    looked up using `load_json_object_fixture`. See `fixtures/modbus_store.json` as an example.
    """

    with (
        patch("pymodbus.client.AsyncModbusTcpClient", autospec=True) as mock,
        patch(
            "pymodbus.pdu.register_message.ReadHoldingRegistersResponse", autospec=True
        ) as read_pdu,
        patch(
            "pymodbus.pdu.register_message.WriteMultipleRegistersRequest", autospec=True
        ) as write_pdu,
    ):
        store: JsonObjectType = load_json_object_fixture(request.param)

        def get_registers(address: int, count: int) -> list[int]:
            return [
                int(store["server"]["registers"][str(r)], 16)
                for r in range(address, address + count)
            ]

        async def get_from_store(address: int, count: int, **kwargs):
            read_pdu.side_effect = AsyncMock()
            read_pdu.isError = Mock(return_value=False)
            read_pdu.registers = get_registers(address, count)
            read_pdu.dev_id = 100

            return read_pdu

        def close():
            return Mock()

        async def write_to_store(address: int, values: list[int], **kwargs):
            for idx, r in enumerate(values):
                store["server"]["registers"][str(address + idx)] = int(r).to_bytes(2).hex()

            write_pdu.side_effect = AsyncMock()
            write_pdu.isError = Mock(return_value=False)
            write_pdu.dev_id = 100

            return write_pdu

        async def set_pump_state(zone_id: int, state: bool = False):
            return await write_to_store(
                address=ZoneRegisters.PUMP_RUNNING.start_address
                + (REMEHA_ZONE_RESERVED_REGISTERS * (zone_id - 1)),
                values=[int(state)],
            )

        mock.connected = MagicMock(return_value=True)
        mock.read_holding_registers.side_effect = get_from_store
        mock.write_registers = write_to_store
        mock.set_zone_pump_state = set_pump_state
        mock.close = close

        yield mock


@pytest.fixture
def mock_config_entry(request) -> Generator[MockConfigEntry]:
    """Create a mocked config entry.

    If `version` and `version_minor` are provided, arguments introduced after this version are ignored.

    `request.param` is an optional dict with the following keys:
    * `version` (int): The config entry major version, defaults to current major version.
    * `version_minor` (int): The config entry minor version, defaults to current minor version.
    * `hub_name` (str): The modbus hub name, defaults to `test_hub`.
    * `device_address` (int): The modbus device address, defaults to `100`.
    * `auto_scheduling` (bool): Whether to enable auto scheduling, defaults to `False`. Since config v1.1
    * `time_zone` (tzinfo): The time zone. Defaults to `None`. Since config v1.1
    * `dhw_boiler_volume` (float): The DHW boiler volume in L. Defaults to 300. Since config v1.1
    * `dhw_boiler_heat_loss_rate (float): The DHW boiler heat loss rate in Watts. Defaults to 2.19. Since config v1.1
    * `dhw_energy_label (BoilerEnergyLabel | None): The DHW boiler energy label. Defaults to `None`. Since config v1.1
    """

    if not hasattr(request, "param"):
        yield _create_config_entry()
    else:
        args: dict[str, Any] = request.param
        yield _create_config_entry(
            version=(
                args.get("version", HA_CONFIG_VERSION),
                args.get("minor_version", HA_CONFIG_MINOR_VERSION),
            ),
            hub_name=args.get("hub_name", "test_hub"),
            device_address=args.get("device_address", 100),
            auto_scheduling=args.get("auto_scheduling", False),
            time_zone=args.get("time_zone"),
            dhw_boiler_volume=args.get("dhw_boiler_volume", 300),
            dhw_boiler_heat_loss_rate=args.get("dhw_boiler_heat_loss_rate", 2.19),
            dhw_energy_label=args.get("dhw_energy_label"),
        )


async def setup_platform(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Set up the platform."""

    config_entry.add_to_hass(hass=hass)

    # We don't want lingering timers after the tests are done, so disable the updates of the update coordinator.
    with patch(
        "custom_components.remeha_modbus.coordinator.RemehaUpdateCoordinator.update_interval",
        0,
    ):
        await hass.config_entries.async_setup(entry_id=config_entry.entry_id)
        await hass.async_block_till_done()


def _create_config_entry(
    version: tuple[int, int] = (HA_CONFIG_VERSION, HA_CONFIG_MINOR_VERSION),
    hub_name: str = "test_hub",
    device_address: int = 100,
    auto_scheduling: bool = False,
    time_zone: tzinfo | None = None,
    dhw_boiler_volume: float = 300,
    dhw_boiler_heat_loss_rate: float = 2.19,
    dhw_energy_label: BoilerEnergyLabel | None = None,
) -> MockConfigEntry:
    """Mock a config entry for Remeha Modbus integration."""

    # v1.0
    entry_data = {
        CONF_NAME: hub_name,
        CONF_TYPE: CONNECTION_RTU_OVER_TCP,
        MODBUS_DEVICE_ADDRESS: device_address,
        CONF_HOST: "does.not.matter",
        CONF_PORT: 8899,
    }

    # v1.1
    if version[1] == 1:
        entry_data |= {CONFIG_AUTO_SCHEDULE: auto_scheduling}

        if auto_scheduling is True:
            entry_data |= {
                WEATHER_ENTITY_ID: "fake_weather",
                PV_CONFIG_SECTION: {
                    PV_NOMINAL_POWER_WP: 5720,
                    PV_ORIENTATION: "S",
                    PV_TILT: 30.0,
                    PV_ANNUAL_EFFICIENCY_DECREASE: 0.42,
                    PV_INSTALLATION_DATE: dt.now(time_zone=time_zone),
                },
                DHW_BOILER_CONFIG_SECTION: {
                    DHW_BOILER_VOLUME: dhw_boiler_volume,
                    DHW_BOILER_HEAT_LOSS_RATE: dhw_boiler_heat_loss_rate,
                },
            }

            if dhw_energy_label is not None:
                entry_data[DHW_BOILER_CONFIG_SECTION] |= {DHW_BOILER_ENERGY_LABEL: dhw_energy_label}

    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Remeha Modbus {hub_name}",
        unique_id=str(uuid.uuid4()),
        data=entry_data,
        version=version[0],
        minor_version=version[1],
    )
