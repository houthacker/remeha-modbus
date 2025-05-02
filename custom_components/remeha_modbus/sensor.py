"""Platform for sensor entities in the Remeha Modbus integration."""

import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import DeviceInstance
from custom_components.remeha_modbus.const import (
    DOMAIN,
    REMEHA_SENSORS,
    ModbusVariableDescription,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensor entities based on the given config entry."""

    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(lambda device: device.is_mainboard())

    async_add_entities(
        [
            RemehaSensorEntity(
                coordinator=coordinator,
                parent_device_id=mainboards[0].id if mainboards else None,
                description=sensor_description,
                variable=modbus_description,
            )
            for modbus_description, sensor_description in REMEHA_SENSORS.items()
        ]
    )


class RemehaSensorEntity(CoordinatorEntity, SensorEntity):
    """Entity class to represent the different sensors of a Remeha appliance.

    All sensors that do not have a `owning_device` are linked to the first discovered device.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = DOMAIN

    def __init__(
        self,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        description: SensorEntityDescription,
        variable: ModbusVariableDescription,
    ):
        """Create a new sensor entity."""

        super().__init__(coordinator=coordinator)

        if parent_device_id is None:
            _LOGGER.warning("Sensor [%s] not attached to a parent device.", variable.name)
        else:
            self._parent_device_id = parent_device_id

        self._variable = variable
        self._attr_name = description.name
        self._attr_unique_id = description.name
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = description.state_class

    @property
    def native_value(self):
        """Return the value of this sensor."""

        return cast(RemehaUpdateCoordinator, self.coordinator).get_sensor_value(
            variable=self._variable
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this sensor belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this sensor is not owned by any device.

        """

        if self._parent_device_id is None:
            return None

        device_instance: DeviceInstance = self.coordinator.get_device(id=self._parent_device_id)
        return DeviceInfo(
            identifiers={(DOMAIN, device_instance.article_number)},
            hw_version=f"HW{device_instance.hw_version[0]:02d}.{device_instance.hw_version[1]:02d}",
            manufacturer="Remeha",
            model=str(device_instance.board_category),
            sw_version=f"SW{device_instance.sw_version[0]:02d}.{device_instance.sw_version[1]:02d}",
        )
