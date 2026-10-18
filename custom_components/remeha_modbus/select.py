"""Platform for select entities in the Remeha Modbus integration."""

import logging
from collections.abc import Callable
from enum import Enum
from functools import cached_property
from types import CoroutineType
from typing import Any, override

from aio_remeha_modbus.gtw08 import GTW08
from aio_remeha_modbus.gtw08.appliance import (
    DIContactLogicConfiguration,
    DigitalInputConfiguration,
    SilentMode,
)
from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoard, DeviceBoardType
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import RemehaModbusError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the select entities based on the given config entry."""

    api: GTW08 = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceBoard] = coordinator.get_devices(
        predicate=lambda device: device.is_mainboard()
    )
    mainboard = mainboards[0] if mainboards else None
    parent_device_id: int | None = mainboard.id if mainboard else None

    entities = [
        RemehaSelectEntity(
            api=api,
            coordinator=coordinator,
            parent_device_id=parent_device_id,
            name="appliance_silent_mode",
            options=SilentMode,
            get_current_option_func=lambda a: a.appliance.silent_mode,
            set_current_option_func=api.appliance.async_set_silent_mode,
        )
    ]

    # Add select entities that are only available on CU_HW boards
    if (
        mainboard
        and mainboard.board_category
        and mainboard.board_category.type is DeviceBoardType.CU_HW
    ):
        entities += [
            RemehaSelectEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="digital_input_1_configuration",
                options=DigitalInputConfiguration,
                get_current_option_func=lambda a: a.appliance.digital_input_1_configuration,
                set_current_option_func=api.appliance.async_set_digital_input_1_configuration,
            ),
            RemehaSelectEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="digital_input_2_configuration",
                options=DigitalInputConfiguration,
                get_current_option_func=lambda a: a.appliance.digital_input_2_configuration,
                set_current_option_func=api.appliance.async_set_digital_input_2_configuration,
            ),
            RemehaSelectEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="digital_input_1_contact_logic",
                options=DIContactLogicConfiguration,
                get_current_option_func=lambda a: a.appliance.digital_input_1_contact_logic,
                set_current_option_func=api.appliance.async_set_digital_input_1_contact_logic,
            ),
            RemehaSelectEntity(
                api=api,
                coordinator=coordinator,
                parent_device_id=parent_device_id,
                name="digital_input_2_contact_logic",
                options=DIContactLogicConfiguration,
                get_current_option_func=lambda a: a.appliance.digital_input_2_contact_logic,
                set_current_option_func=api.appliance.async_set_digital_input_2_contact_logic,
            ),
        ]

    async_add_entities(entities)


class RemehaSelectEntity[E: Enum](CoordinatorEntity[RemehaUpdateCoordinator], SelectEntity):
    """Super class for select entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        api: GTW08,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
        options: type[E],
        get_current_option_func: Callable[[GTW08], E | None],
        set_current_option_func: Callable[[E], CoroutineType[Any, Any, None]],
    ):
        """Create a new select entity."""

        super().__init__(coordinator=coordinator)

        if parent_device_id is None:
            _LOGGER.warning("Select entity [%s] not linked to a parent device.", name)

        self._parent_device_id = parent_device_id
        self._enum_type = options
        self._getter = get_current_option_func
        self._setter = set_current_option_func

        self._attr_unique_id = name
        self._attr_options = [e.name.lower() for e in options]
        self._attr_translation_key = name

        self._api = api

    @property
    @override
    def current_option(self) -> str | None:
        value = self._getter(self._api)
        return None if value is None else value.name.lower()

    @override
    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options or option not in [
            e.name.lower() for e in self._enum_type
        ]:
            raise RemehaModbusError(
                translation_domain=DOMAIN,
                translation_key="invalid_select_option",
                translation_placeholders={"option": option},
            )

        value = self._enum_type[option.upper()]
        await self._setter(value)

        # TODO Update current data to reflect changes immediately
        self.async_write_ha_state()

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this entity belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this entity is not owned by any device.

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
