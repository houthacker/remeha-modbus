"""Platform for select entities in the Remeha Modbus integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import DeviceInstance
from custom_components.remeha_modbus.api.api import RemehaApi
from custom_components.remeha_modbus.api.appliance import SilentMode
from custom_components.remeha_modbus.const import DOMAIN, MetaRegisters
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import RemehaModbusError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensor entities based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(
        predicate=lambda device: device.is_mainboard()
    )
    parent_device_id: int | None = mainboards[0].id if mainboards else None

    async_add_entities(
        [
            RemehaSilentModeEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
            )
        ]
    )


class RemehaSelectEntity(CoordinatorEntity[RemehaUpdateCoordinator], SelectEntity):
    """Super class for select entities."""

    def __init__(
        self,
        api: RemehaApi,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
        options: list[str],
    ):
        """Create a new select entity."""

        super().__init__(coordinator=coordinator)

        if parent_device_id is None:
            _LOGGER.warning("Select entity [%s] not linked to a parent device.", name)
        else:
            self._parent_device_id = parent_device_id

        self._attr_name = name
        self._attr_unique_id = name
        self._attr_options = options

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


class RemehaSilentModeEntity(RemehaSelectEntity):
    """Entity to select appliance silent mode."""

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """ABC."""

        super().__init__(
            api=api,
            coordinator=coordinator,
            parent_device_id=parent_device_id,
            name="appliance_silent_mode",
            options=[e.name for e in SilentMode],
        )

        self._attr_translation_key = "appliance_silent_mode"

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""

        return self.coordinator.get_appliance().silent_mode.name

    async def async_select_option(self, option: str) -> None:
        """Set the current option.

        Raises:
          RemehaModbusError if the option is invalid.

        """
        if option not in self._attr_options or option not in [e.name for e in SilentMode]:
            raise RemehaModbusError(
                translation_domain=DOMAIN,
                translation_key="invalid_select_option",
                translation_placeholders={"option": option},
            )

        selected_mode = SilentMode[option]
        await self._api.async_write_variable(
            variable=MetaRegisters.SILENT_MODE, value=selected_mode
        )

        # Update current data to reflect changes immediately
        self.coordinator.get_appliance().silent_mode = selected_mode
