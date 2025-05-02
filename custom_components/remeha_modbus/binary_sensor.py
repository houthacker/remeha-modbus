"""Platform for binary sensor entities in the Remeha Modbus integration."""

import logging
from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import DeviceInstance
from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensor entities based on the given config entry."""

    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(
        predicate=lambda device: device.is_mainboard()
    )
    parent_device_id: int = mainboards[0].id if mainboards else None

    async_add_entities(
        [
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="flame_on",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.flame_on,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="heat_pump_on",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.heat_pump_on,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="electrical_backup_on",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.electrical_backup_on,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="electrical_backup2_on",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.electrical_backup2_on,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="dhw_electrical_backup_on",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.dhw_electrical_backup_on,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="service_required",
                device_class=BinarySensorDeviceClass.PROBLEM,
                state_func=lambda: coordinator.get_appliance().status.service_required,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="power_down_reset_needed",
                device_class=BinarySensorDeviceClass.PROBLEM,
                state_func=lambda: coordinator.get_appliance().status.power_down_reset_needed,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="water_pressure_low",
                device_class=BinarySensorDeviceClass.PROBLEM,
                state_func=lambda: coordinator.get_appliance().status.water_pressure_low,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="appliance_pump_on",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.appliance_pump_on,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="three_way_valve_open",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.three_way_valve_open,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="three_way_valve",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.three_way_valve,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="three_way_valve_closed",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.three_way_valve_closed,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="dhw_active",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.dhw_active,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="ch_active",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.ch_active,
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="cooling_active",
                device_class=None,
                state_func=lambda: coordinator.get_appliance().status.cooling_active,
            ),
        ]
    )


class RemehaBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor entity to describe the different appliance status fields in the Remeha Modbus integration."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
        device_class: BinarySensorDeviceClass,
        state_func: Callable[[], bool | None],
    ):
        """Create a new binary sensor entity."""

        super().__init__(coordinator=coordinator)

        if parent_device_id is None:
            _LOGGER.warning("Binary sensor [%s] not linked to a parent device.", name)
        else:
            self._parent_device_id = parent_device_id

        self._attr_name = name
        self._attr_unique_id = name
        self._attr_device_class = device_class
        self._state_func: Callable[[], bool | None] = state_func

    @property
    def translation_key(self) -> str:
        """The translation key."""

        return self.name

    @property
    def is_on(self) -> bool | None:
        """Return whether this sensor is on.

        Returns:
            `bool`: `If this sensor is currently on or off. If the state cannot be determined, return `None`.

        """

        return self._state_func()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this sensor belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this sensor is not owned by any device.

        """

        if self._parent_device_id is None:
            return None

        device_instance: DeviceInstance = self.coordinator.get_device(id=self._parent_device_id)
        return (
            DeviceInfo(
                identifiers={(DOMAIN, device_instance.article_number)},
                hw_version=f"HW{device_instance.hw_version[0]:02d}.{device_instance.hw_version[1]:02d}",
                manufacturer="Remeha",
                model=str(device_instance.board_category),
                sw_version=f"SW{device_instance.sw_version[0]:02d}.{device_instance.sw_version[1]:02d}",
            )
            if device_instance is not None
            else None
        )
