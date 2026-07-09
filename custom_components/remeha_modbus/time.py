"""Platform for time entities in the Remeha Modbus integration."""

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import DeviceInstance
from custom_components.remeha_modbus.api.api import RemehaApi
from custom_components.remeha_modbus.const import (
    DOMAIN,
    TIME_SILENT_MODE_END_TIME,
    TIME_SILENT_MODE_START_TIME,
    MetaRegisters,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.helpers.gtw08 import SteppedTimeOfDay

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the time entities based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(
        predicate=lambda device: device.is_mainboard()
    )
    parent_device_id: int | None = mainboards[0].id if mainboards else None

    async_add_entities(
        [
            SilentModeStartTimeEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name=TIME_SILENT_MODE_START_TIME,
            ),
            SilentModeEndTimeEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name=TIME_SILENT_MODE_END_TIME,
            ),
        ]
    )


class RemehaTimeEntity(CoordinatorEntity[RemehaUpdateCoordinator], TimeEntity):
    """Base class for Remeha time entities."""

    def __init__(
        self,
        api: RemehaApi,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
    ):
        """Entity to set time values."""

        super().__init__(coordinator=coordinator)

        if parent_device_id is None:
            _LOGGER.warning("Select entity [%s] not linked to a parent device.", name)
        else:
            self._parent_device_id = parent_device_id

        self._attr_name = name
        self._attr_unique_id = name
        self._attr_translation_key = name
        self._api = api

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this entity belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this entity is not owned by any device.

        """

        if self._parent_device_id is None:
            return None

        device_instance: DeviceInstance | None = self.coordinator.get_device(
            id=self._parent_device_id
        )
        return (
            DeviceInfo(
                identifiers={(DOMAIN, str(device_instance.article_number))},
                hw_version=f"HW{device_instance.hw_version[0]:02d}.{device_instance.hw_version[1]:02d}",
                manufacturer="Remeha",
                model=str(device_instance.board_category),
                sw_version=f"SW{device_instance.sw_version[0]:02d}.{device_instance.sw_version[1]:02d}",
            )
            if device_instance is not None
            else None
        )


class SilentModeStartTimeEntity(RemehaTimeEntity):
    """Entity to expose the start time for the appliance silent mode."""

    @property
    def native_value(self) -> time:
        """The silent mode start time."""

        return self.coordinator.get_appliance().silent_mode_start_time

    async def async_set_value(self, value: time) -> None:
        """Set the silent mode start time."""

        await self._api.async_write_variable(
            variable=MetaRegisters.SILENT_MODE_START_TIME, value=SteppedTimeOfDay.to_steps(value)
        )

        # Reflect update until current update
        self.coordinator.get_appliance().silent_mode_start_time = value
        self.async_write_ha_state()


class SilentModeEndTimeEntity(RemehaTimeEntity):
    """Entity to expose the end time for the appliance silent mode."""

    @property
    def native_value(self) -> time:
        """The silent mode end time."""

        return self.coordinator.get_appliance().silent_mode_end_time

    async def async_set_value(self, value: time) -> None:
        """Set the silent mode end time."""

        await self._api.async_write_variable(
            variable=MetaRegisters.SILENT_MODE_END_TIME, value=SteppedTimeOfDay.to_steps(value)
        )

        # Reflect update until current update
        self.coordinator.get_appliance().silent_mode_end_time = value
        self.async_write_ha_state()
