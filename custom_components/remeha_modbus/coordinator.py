"""Coordinator for fetching modbus data of Remeha devices."""

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus import ModbusException

from custom_components.remeha_modbus.api import (
    ClimateZone,
    DeviceInstance,
    RemehaApi,
)
from custom_components.remeha_modbus.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RemehaUpdateCoordinator(DataUpdateCoordinator):
    """Remeha Modbus coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, api: RemehaApi):
        """Create a new instance the Remeha Modbus update coordinator."""

        # Update every 20 seconds. This is not user-configurable, since it depends on the amount of
        # configured (hard-coded) modbus entities
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=20),
            always_update=False,
            config_entry=config_entry,
        )
        self._api: RemehaApi = api
        self._device_instances: list[DeviceInstance] = []

    async def _async_setup(self):
        try:
            self._device_instances = await self._api.async_read_device_instances()
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

    async def _async_update_data(self) -> dict[str, dict[int, ClimateZone]]:
        try:
            zones: list[ClimateZone] = []
            if self.data is None:
                zones = await self._api.async_read_zones()
            else:
                zones = [
                    await self._api.async_read_zone_update(zone)
                    for zone in list(self.data["climates"].values())
                ]
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

        return {"climates": {zone.id: zone for zone in zones}}

    def get_device(self, id: int) -> DeviceInstance | None:
        """Return the device instance with `id`.

        Returns
            `DeviceInstance | None`: The device instance, or `None` if no device has the given `id`.

        """

        return self._device_instances[id] if self._device_instances[id] else None

    def get_climate(self, id: int) -> ClimateZone | None:
        """Return the climate instance with `id`.

        Returns
            `ClimateZone | None`: The climate instance, or `None` if no climate has the given `id`.

        """

        return self.data["climates"][id] if self.data["climates"] else None

    def get_climates(self, predicate: Callable[[ClimateZone], bool]) -> list[ClimateZone]:
        """Return all climate that match the given predicate."""

        return [climate for climate in self.data["climates"].values() if predicate(climate) is True]
