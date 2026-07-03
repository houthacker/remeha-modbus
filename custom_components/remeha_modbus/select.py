"""Platform for select entities in the Remeha Modbus integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.remeha_modbus.api import DeviceInstance, RemehaApi
from custom_components.remeha_modbus.const import MetaRegisters
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.entity import RemehaApplianceEntity

_LOGGER = logging.getLogger(__name__)

# Heat pump quiet mode level (register value <-> option).
QUIET_MODE_OPTIONS: dict[int, str] = {0: "off", 1: "level_1", 2: "level_2"}
QUIET_MODE_VALUES: dict[str, int] = {v: k for k, v in QUIET_MODE_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the select entities based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(lambda device: device.is_mainboard())

    if not mainboards:
        _LOGGER.debug("No mainboard found so not adding any select entities.")
        return

    async_add_entities(
        [RemehaQuietModeSelect(api=api, coordinator=coordinator, parent_device_id=mainboards[0].id)]
    )


class RemehaQuietModeSelect(RemehaApplianceEntity, SelectEntity):
    """Select entity for the heat pump quiet mode level (parameter HP058)."""

    _attr_options = list(QUIET_MODE_OPTIONS.values())

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create the quiet mode select entity."""

        super().__init__(
            api=api, coordinator=coordinator, parent_device_id=parent_device_id, name="quiet_mode"
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently selected quiet mode level."""

        return QUIET_MODE_OPTIONS.get(self._appliance.quiet_mode_level)

    async def async_select_option(self, option: str) -> None:
        """Change the quiet mode level."""

        level = QUIET_MODE_VALUES[option]
        await self._api.async_write_variable(variable=MetaRegisters.QUIET_MODE_LEVEL, value=level)

        # Reflect the change immediately, until the next coordinator refresh.
        self._appliance.quiet_mode_level = level
        self.async_write_ha_state()
