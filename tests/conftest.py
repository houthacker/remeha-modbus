"""Fixtures for testing."""

import logging
import uuid
from collections.abc import Callable, Generator, Iterable
from datetime import timedelta, tzinfo
from typing import Any, Final, cast
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import voluptuous as vol
from aio_remeha_modbus.api.api import RemehaApi
from aio_remeha_modbus.api.const import BoilerEnergyLabel
from dateutil import tz
from homeassistant.components.modbus.const import RTUOVERTCP
from homeassistant.components.weather import (
    SERVICE_GET_FORECASTS,
    Forecast,
    WeatherEntity,
    async_get_forecasts_service,
)
from homeassistant.components.weather.const import DOMAIN as WeatherDomain
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import dt
from homeassistant.util.json import JsonValueType
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockEntity,
    load_json_value_fixture,
)

from custom_components.remeha_modbus.api.store import RemehaModbusStore
from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SELECTED_SCHEDULE,
    CONFIG_AUTO_SCHEDULE,
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
    REMEHA_PRESET_SCHEDULE_1,
    WEATHER_ENTITY_ID,
)
from custom_components.remeha_modbus.services import register_services
from custom_components.scheduler.store import ScheduleEntry
from tests.util import SchedulerPlatformStub

TESTING_TIME_ZONE: Final[str] = "Europe/Amsterdam"


class MockWeatherEntity(MockEntity, WeatherEntity):
    """Mock weather entity."""

    def __init__(self, **values):
        """Create a new MockWeatherEntity."""
        super().__init__(**values)

    @property
    def supported_features(self) -> int | None:
        """Return the features of this entity."""
        return WeatherEntityFeature.FORECAST_HOURLY

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""

        # TODO Update timestamps to now() + relative hours.
        return cast(list[Forecast], load_json_value_fixture("weather_forecast.json"))


@pytest_asyncio.fixture
async def remeha_api(
    request,
    remeha_modbus_unit,
) -> RemehaApi:
    """Create a new RemehaApi instance with a mocked modbus client."""

    # mock_modbus_client MUST be a mock, otherwise a real connection might be made and mess up the appliance.
    if not isinstance(remeha_modbus_unit, MockModbusUnit):
        pytest.fail(
            f"Cannot create RemehaApi with non-mocked modbus unit type {type(remeha_modbus_unit).__qualname__}."
        )

    require_update = (
        request.param.get("require_update", True) if hasattr(request, "param") else True
    )
    name = request.param.get("name", "test_api") if hasattr(request, "param") else "test_api"
    time_zone: tzinfo | None = (
        tz.gettz(request.param.get("time_zone", TESTING_TIME_ZONE))
        if hasattr(request, "param")
        else tz.gettz(TESTING_TIME_ZONE)
    )

    api = RemehaApi(
        name=name,
        unit=remeha_modbus_unit,
        time_zone=time_zone,
    )
    if require_update:
        await api.async_update()

    return api


@pytest.fixture
def remeha_modbus_unit(request, mock_modbus_unit: MockModbusUnit, json_fixture) -> MockModbusUnit:
    """Return a mocked modbus unit with registers loaded from the requested json file."""

    store: dict[str, str] = json_fixture["server"]["registers"]
    mock_modbus_unit.load_raw(
        {"holding": {int(key): int(value, 16) for key, value in store.items()}}
    )

    return mock_modbus_unit


@pytest.fixture
def finalizer():
    """Return a list of callables that are executed after the test method finishes."""
    callables = []
    yield callables

    for fn in callables:
        fn()


@pytest.fixture
def json_fixture(request) -> JsonValueType:
    """Read a fixture and return it as a `JsonValueType`."""
    filename = request.param if hasattr(request, "param") else "modbus_store.json"
    return load_json_value_fixture(filename=filename)


@pytest.fixture
def json_file(request) -> JsonValueType:
    """Load an additional json file."""

    filename = request.param if hasattr(request, "param") else "no-file-specified"
    return load_json_value_fixture(filename=filename)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def entity_registry(hass: HomeAssistant) -> er.EntityRegistry:
    """Return the entity registry for the current hass instance."""
    return er.async_get(hass)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.remeha_modbus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


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


@pytest.fixture
def modbus_test_store(request, hass) -> RemehaModbusStore:
    """Create a testing store.

    To configure the store with defaults, pass no parameters.
    Otherwise, arguments may be passed in a dict of str:
    ```
    {
        version: int,
        minor_version: int,
        key: str
    }
    ```
    """

    args: dict[str, Any] = request.param if hasattr(request, "param") else {}
    return RemehaModbusStore(
        hass=hass,
        version=args.get("version", 1),
        minor_version=args.get("minor_version", 0),
        key=args.get("key", "remeha-modbus-test-store"),
    )


async def setup_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    add_schedule_callback: Callable[[ScheduleEntry], None] | None = None,
    edit_schedule_callback: Callable[[ScheduleEntry], None] | None = None,
    scheduler_entities: Iterable[MockEntity] = [],
):
    """Set up the platform based on the given `config_entry`, using a `RemehaUpdateCoordinator` that does not update.

    Additionally, the following entities and services are configured:
     * A `weather.fake_weather` entity;
     * A mocked `weather.get_forecasts` entity service;
     * A mocked `scheduler.add` service;
     * A mocked `scheduler.edit` service;
     * `hass.data['remeha_modbus']['add_scheduler_calls']` contains a list of service calls to the `scheduler.add` service.
     * `hass.data['remeha_modbus']['edit_schedule_calls']` contains a list of service calls to the `scheduler.edit` service.

    If the scheduler services require a side effect, provide the respective callback.

    Args:
        hass (HomeAssistant): Home Assistant instance.
        config_entry (MockConfigEntry): The config entry to use for setting up the platform.
        add_schedule_callback (Callable[[ScheduleEntry], None] | None): A callback function for the `scheduler.add` service.
        edit_schedule_callback (Callable[[ScheduleEntry], None] | None): A callback function for the `scheduler.edit` service.
        scheduler_entities (Iterable[MockEntity]): An optional list of mock entities to add to the scheduler component.

    """

    # Prepare hass by adding a weather entity.
    weather_component = EntityComponent[WeatherEntity](
        logger=logging.getLogger("weather"),
        domain=WeatherDomain,
        hass=hass,
        scan_interval=timedelta(seconds=-1),
    )

    # Stop timers when HA stops.
    weather_component.register_shutdown()

    # Add fake weather entity.
    entity: WeatherEntity = MockWeatherEntity(entity_id="weather.fake_weather")
    await weather_component.async_add_entities([entity])

    weather_component.async_register_entity_service(
        name=SERVICE_GET_FORECASTS,
        schema={vol.Required("type"): vol.In(("daily", "hourly", "twice_daily"))},
        func=async_get_forecasts_service,
        required_features=[
            WeatherEntityFeature.FORECAST_DAILY,
            WeatherEntityFeature.FORECAST_HOURLY,
            WeatherEntityFeature.FORECAST_TWICE_DAILY,
        ],
        supports_response=SupportsResponse.ONLY,
    )

    hass.data.setdefault(DOMAIN, {})

    # Add the scheduler component
    scheduler_component = SchedulerPlatformStub(
        add_schedule_callback=add_schedule_callback,
        edit_schedule_callback=edit_schedule_callback,
    )

    await scheduler_component.async_add_to_hass(hass=hass)
    await scheduler_component.async_add_entities(entities=scheduler_entities)

    config_entry.add_to_hass(hass=hass)

    # We don't want lingering timers after the tests are done, so disable the updates of the update coordinator.
    with patch(
        "custom_components.remeha_modbus.coordinator.RemehaUpdateCoordinator.update_interval",
        0,
    ):
        await hass.config_entries.async_setup(entry_id=config_entry.entry_id)
        await hass.async_block_till_done()

        # Register our services
        register_services(hass, config_entry, config_entry.runtime_data["coordinator"])

    # Ensure hass and RemehaApi are using the same time zone.
    await hass.config.async_update(time_zone=TESTING_TIME_ZONE)


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
        CONF_TYPE: RTUOVERTCP,
        MODBUS_DEVICE_ADDRESS: device_address,
        CONF_HOST: "does.not.matter",
        CONF_PORT: 8899,
    }

    # v1.1, v1.2
    if version[1] in [1, 2]:
        entry_data |= {CONFIG_AUTO_SCHEDULE: auto_scheduling}

        if auto_scheduling is True:
            entry_data |= {
                WEATHER_ENTITY_ID: "weather.fake_weather",
                AUTO_SCHEDULE_SELECTED_SCHEDULE: REMEHA_PRESET_SCHEDULE_1,
                PV_CONFIG_SECTION: {
                    PV_NOMINAL_POWER_WP: 5720,
                    PV_ORIENTATION: "S",
                    PV_TILT: 30.0,
                    PV_ANNUAL_EFFICIENCY_DECREASE: 0.42,
                    PV_INSTALLATION_DATE: str(dt.now(time_zone=time_zone).date()),
                },
                DHW_BOILER_CONFIG_SECTION: {
                    DHW_BOILER_VOLUME: dhw_boiler_volume,
                    DHW_BOILER_HEAT_LOSS_RATE: dhw_boiler_heat_loss_rate,
                },
            }

            if dhw_energy_label is not None:
                entry_data[DHW_BOILER_CONFIG_SECTION] |= {DHW_BOILER_ENERGY_LABEL: dhw_energy_label}

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Remeha Modbus {hub_name}",
        unique_id=str(uuid.uuid4()),
        data=entry_data,
        version=version[0],
        minor_version=version[1],
    )

    config_entry.runtime_data = {}

    return config_entry
