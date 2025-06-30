"""The Remeha Modbus integration."""

import logging
from typing import TypedDict
from zoneinfo import ZoneInfo

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.const import CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from pymodbus import ModbusException

from custom_components.remeha_modbus.api import (
    ConnectionType,
    RemehaApi,
    RemehaModbusStorage,
    RemehaModbusStore,
)
from custom_components.remeha_modbus.blend.scheduler import EventDispatcher
from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SELECTED_SCHEDULE,
    CONFIG_AUTO_SCHEDULE,
    REMEHA_PRESET_SCHEDULE_1,
    STORAGE_FILE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.schedule_sync.synchronizer import ScheduleSynchronizer
from custom_components.remeha_modbus.services import register_services

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


class RuntimeData(TypedDict):
    """Describe the type of `ConfigEntry.runtime_data` in the remeha_modbus integration."""

    api: RemehaApi
    """The api instance to interact with the modbus interface."""

    coordinator: RemehaUpdateCoordinator
    """The data update coordinator."""

    schedule_synchronizer: ScheduleSynchronizer
    """Synchronization methods for schedules between the modbus interface and the `scheduler` integration."""

    event_dispatcher: EventDispatcher
    """Dispatch incoming events to subscribers."""


type RemehaModbusConfig = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: RemehaModbusConfig) -> bool:
    """Set up Remeha Modbus based on a config entry."""

    modbus_hub_name = entry.data[CONF_NAME]
    modbus_type = entry.data[CONF_TYPE]

    if modbus_type not in ConnectionType:
        connection_types: str = ", ".join(e.value for e in ConnectionType)
        raise ConfigEntryError(
            f"{modbus_type} is not a valid connection type. Use one of [{connection_types}]"
        )

    api: RemehaApi = RemehaApi.create(
        name=modbus_hub_name, config=entry.data, time_zone=ZoneInfo(key=hass.config.time_zone)
    )

    # Ensure the modbus device is reachable and actually talking Modbus
    # before forwarding setup to other platforms.
    try:
        await api.async_connect()
        await api.async_health_check()
    except ModbusException as ex:
        raise ConfigEntryNotReady(f"Error while executing modbus health check: {ex}") from ex

    coordinator = RemehaUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api=api,
        store=RemehaModbusStorage(
            store=RemehaModbusStore.create(
                hass=hass,
                version=STORAGE_VERSION,
                minor_version=STORAGE_MINOR_VERSION,
                key=STORAGE_FILE_KEY,
            )
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    synchronizer = ScheduleSynchronizer(hass=hass, coordinator=coordinator)
    entry.runtime_data = RuntimeData(
        api=api,
        coordinator=coordinator,
        schedule_synchronizer=synchronizer,
        event_dispatcher=EventDispatcher(hass=hass),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services only if everything else has been set up successfully.
    register_services(hass=hass, config=entry)

    await synchronizer.async_refresh_subscriptions()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemehaModbusConfig) -> bool:
    """Unload the Remeha Modbus configuration."""

    # Close the connection to the modbus server.
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    await coordinator.async_shutdown()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: RemehaModbusConfig) -> bool:
    """Migrate config entry to latest version."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        _LOGGER.error("Cannot downgrade from future version.")
        return False

    new_data = {**config_entry.data}
    if config_entry.minor_version == 0:
        # version 1.1 adds auto-scheduling configuration.
        # For the migration, setting the parameter `auto_schedule` to `False` is enough:
        # fully configuring auto scheduling, if desired, can be done by reconfiguring
        # the integration.
        new_data[CONFIG_AUTO_SCHEDULE] = False

    if config_entry.minor_version < 2:
        # Version 1.2 adds a configurable schedule id to the auto-scheduling configuration.
        # It defaults to SCHEDULE_1, so use that if CONFIG_AUTO_SCHEDULE is True
        # (i.e. auto-scheduling) is used.
        if new_data[CONFIG_AUTO_SCHEDULE] is True:
            new_data[AUTO_SCHEDULE_SELECTED_SCHEDULE] = REMEHA_PRESET_SCHEDULE_1

    hass.config_entries.async_update_entry(config_entry, data=new_data, minor_version=2, version=1)
    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
