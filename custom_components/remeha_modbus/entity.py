"""Base entity for appliance-level Remeha Modbus entities."""

from typing import cast

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import DeviceInstance, RemehaApi
from custom_components.remeha_modbus.api.appliance import Appliance
from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator


class RemehaApplianceEntity(CoordinatorEntity[RemehaUpdateCoordinator]):
    """Base class for appliance-level entities backed by a modbus register.

    Subclasses combine this with a platform entity (e.g. `NumberEntity`) and read
    their value from the shared `Appliance` state, writing changes to the appliance
    through the modbus API.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        api: RemehaApi,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
    ):
        """Create a new appliance entity."""

        super().__init__(coordinator=coordinator)

        self._api = api
        self._parent_device_id = parent_device_id
        self._attr_name = name
        self._attr_unique_id = name

    @property
    def translation_key(self) -> str:
        """The translation key."""

        return cast(str, self.name)

    @property
    def _appliance(self) -> Appliance:
        """Return the current appliance state."""

        return self.coordinator.get_appliance()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the appliance device this entity belongs to.

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
