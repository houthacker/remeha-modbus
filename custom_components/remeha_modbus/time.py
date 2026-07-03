"""Platform for time entities in the Remeha Modbus integration."""

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.remeha_modbus.api import DeviceInstance, RemehaApi
from custom_components.remeha_modbus.const import MetaRegisters, ModbusVariableDescription
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.entity import RemehaApplianceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the time entities based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(lambda device: device.is_mainboard())

    if not mainboards:
        _LOGGER.debug("No mainboard found so not adding any time entities.")
        return

    parent_device_id: int = mainboards[0].id
    async_add_entities(
        [
            RemehaQuietModeStartTime(
                api=api, coordinator=coordinator, parent_device_id=parent_device_id
            ),
            RemehaQuietModeEndTime(
                api=api, coordinator=coordinator, parent_device_id=parent_device_id
            ),
        ]
    )


class RemehaQuietModeTime(RemehaApplianceEntity, TimeEntity):
    """Base class for the heat pump quiet mode start/end time.

    The appliance stores the time in 10-minute units from midnight.
    """

    _register: ModbusVariableDescription
    _field: str

    @property
    def native_value(self) -> time | None:
        """Return the configured time."""

        total_minutes = int(getattr(self._appliance, self._field)) * 10
        return time(hour=total_minutes // 60, minute=total_minutes % 60)

    async def async_set_value(self, value: time) -> None:
        """Update the configured time (rounded to 10-minute resolution)."""

        register_value = (value.hour * 60 + value.minute) // 10
        await self._api.async_write_variable(variable=self._register, value=register_value)

        # Reflect the change immediately, until the next coordinator refresh.
        setattr(self._appliance, self._field, register_value)
        self.async_write_ha_state()


class RemehaQuietModeStartTime(RemehaQuietModeTime):
    """Start of the heat pump quiet period (parameter HP094)."""

    _register = MetaRegisters.QUIET_MODE_START
    _field = "quiet_mode_start"

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create the quiet mode start time entity."""

        super().__init__(
            api=api,
            coordinator=coordinator,
            parent_device_id=parent_device_id,
            name="quiet_mode_start",
        )


class RemehaQuietModeEndTime(RemehaQuietModeTime):
    """End of the heat pump quiet period (parameter HP095)."""

    _register = MetaRegisters.QUIET_MODE_END
    _field = "quiet_mode_end"

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create the quiet mode end time entity."""

        super().__init__(
            api=api,
            coordinator=coordinator,
            parent_device_id=parent_device_id,
            name="quiet_mode_end",
        )
