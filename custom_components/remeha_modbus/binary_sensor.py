"""Platform for binary sensor entities in the Remeha Modbus integration."""

import logging
from collections.abc import Callable
from enum import IntFlag
from typing import cast

from aio_remeha_modbus.api.main_control_monitoring import ApplianceDemandStatus, ApplianceStatus
from aio_remeha_modbus.api.system_discovery_table import DeviceBoard
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _state_fn(flags: IntFlag | None, state: int) -> Callable[[], bool | None]:

    def _has_state() -> bool | None:
        if flags is None:
            return None

        if flags & state:
            return True

        return False

    return _has_state


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensor entities based on the given config entry."""

    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceBoard] = coordinator.get_devices(
        predicate=lambda device: device.is_mainboard()
    )
    parent_device_id: int | None = mainboards[0].id if mainboards else None

    async_add_entities(
        [
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="unmixed_circuits_released",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.UNMIXED_CIRCUITS_RELEASED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="mixed_circuits_released",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.MIXED_CIRCUITS_RELEASED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="valves_open_or_pump_running_safety",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.VALVES_OPEN_OR_PUMP_RUNNING_SAFETY,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="manual_heat_demand_active",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.MANUAL_HEAT_DEMAND_ACTIVE,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="cooling_allowed",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.COOLING_ALLOWED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="dhw_circuits_released",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.DHW_CIRCUITS_RELEASED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="burner_unit_active",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().demand_status,
                    ApplianceDemandStatus.BURNER_UNIT_ACTIVE,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="flame_on",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status, ApplianceStatus.FLAME_ON
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="heat_pump_on",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status, ApplianceStatus.HEAT_PUMP_ON
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="electrical_backup_on",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.ELECTRICAL_BACKUP_ON,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="electrical_backup2_on",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.ELECTRICAL_BACKUP2_ON,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="dhw_electrical_backup_on",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.DHW_ELECTRICAL_BACKUP_ON,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="service_required",
                device_class=BinarySensorDeviceClass.PROBLEM,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.SERVICE_REQUIRED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="power_down_reset_needed",
                device_class=BinarySensorDeviceClass.PROBLEM,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.POWER_DOWN_RESET_NEEDED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="water_pressure_low",
                device_class=BinarySensorDeviceClass.PROBLEM,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.WATER_PRESSURE_LOW,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="appliance_pump_on",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.APPLIANCE_PUMP_ON,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="three_way_valve_open",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.THREE_WAY_VALVE_OPEN,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="three_way_valve",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.THREE_WAY_VALVE,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="three_way_valve_closed",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status,
                    ApplianceStatus.THREE_WAY_VALVE_CLOSED,
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="dhw_active",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status, ApplianceStatus.DHW_ACTIVE
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="ch_active",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status, ApplianceStatus.CH_ACTIVE
                ),
            ),
            RemehaBinarySensorEntity(
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="cooling_active",
                device_class=None,
                state_func=_state_fn(
                    coordinator.get_main_control_monitoring().status, ApplianceStatus.COOLING_ACTIVE
                ),
            ),
        ]
    )


class RemehaBinarySensorEntity(CoordinatorEntity[RemehaUpdateCoordinator], BinarySensorEntity):
    """Binary sensor entity to describe the different appliance status fields in the Remeha Modbus integration."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
        device_class: BinarySensorDeviceClass | None,
        state_func: Callable[[], bool | None],
    ):
        """Create a new binary sensor entity."""

        super().__init__(coordinator=coordinator)

        if parent_device_id is None:
            _LOGGER.warning("Binary sensor [%s] not linked to a parent device.", name)

        self._parent_device_id = parent_device_id

        self._attr_name = name
        self._attr_unique_id = name
        self._attr_device_class = device_class
        self._state_func: Callable[[], bool | None] = state_func

    @callback
    def _handle_coordinator_update(self) -> None:
        return super()._handle_coordinator_update()

    @property
    def translation_key(self) -> str:
        """The translation key."""

        return cast(str, self.name)

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

        device_instance: DeviceBoard | None = self.coordinator.get_device(id=self._parent_device_id)
        return (
            DeviceInfo(
                identifiers={(DOMAIN, str(device_instance.article_number))},
                hw_version=f"HW{device_instance.hardware_version[0]:02d}.{device_instance.hardware_version[1]:02d}",
                manufacturer="Remeha",
                model=str(device_instance.board_category),
                sw_version=f"SW{device_instance.software_version[0]:02d}.{device_instance.software_version[1]:02d}",
            )
            if device_instance is not None
            and device_instance.hardware_version is not None
            and device_instance.software_version is not None
            else None
        )
