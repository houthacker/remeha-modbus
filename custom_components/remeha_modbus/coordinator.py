"""Coordinator for fetching modbus data of Remeha devices."""

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus import ModbusException

from custom_components.remeha_modbus.api import Appliance, ClimateZone, DeviceInstance, RemehaApi
from custom_components.remeha_modbus.const import DOMAIN, REMEHA_SENSORS, ModbusVariableDescription

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
        self._device_instances: dict[int, DeviceInstance] = {}

    def _before_first_update(self) -> bool:
        return not self.data or "climates" not in self.data

    async def _async_setup(self):
        try:
            self._device_instances = {
                instance.id: instance for instance in await self._api.async_read_device_instances()
            }
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

    async def _async_update_data(self) -> dict[str, dict[int, ClimateZone]]:
        try:
            zones: list[ClimateZone] = []
            is_cooling_forced: bool = await self._api.async_is_cooling_forced
            appliance: Appliance = await self._api.async_read_appliance()
            sensors = await self._api.async_read_sensor_values(REMEHA_SENSORS)
            if self._before_first_update():
                zones = await self._api.async_read_zones()
            else:
                zones = [
                    await self._api.async_read_zone_update(zone)
                    for zone in list(self.data["climates"].values())
                ]
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

        return {
            "appliance": appliance,
            "climates": {zone.id: zone for zone in zones},
            "cooling_forced": is_cooling_forced,
            "sensors": sensors,
        }

    def is_cooling_forced(self) -> bool:
        """Return whether the appliance is in forced cooling mode."""

        return self.data["cooling_forced"]

    def get_device(self, id: int) -> DeviceInstance | None:
        """Return the device instance with `id` (0-based).

        Returns
            `DeviceInstance | None`: The device instance, or `None` if no device has the given `id`.

        """

        return self._device_instances.get(id, None)

    def get_devices(
        self, predicate: Callable[[DeviceInstance], bool] = lambda _: True
    ) -> list[DeviceInstance]:
        """Return all device instances that match the given predicate.

        Args:
            predicate (Callable[[DeviceInstance], bool]): The predicate to evanuate on all device instances. Defaults to `True`.

        Returns:
            `list[DeviceInstance]`: The list of all matching device instances.

        """

        return [d for d in self._device_instances.values() if predicate(d) is True]

    def get_appliance(self) -> Appliance:
        """Return the appliance status info."""

        return self.data["appliance"]

    def get_climate(self, id: int) -> ClimateZone | None:
        """Return the climate instance with `id`.

        Returns
            `ClimateZone | None`: The climate instance, or `None` if no climate has the given `id`.

        """

        return self.data["climates"][id] if self.data["climates"] else None

    def get_climates(self, predicate: Callable[[ClimateZone], bool]) -> list[ClimateZone]:
        """Return all climate that match the given predicate."""

        return [climate for climate in self.data["climates"].values() if predicate(climate) is True]

    def get_sensor_value(self, variable: ModbusVariableDescription) -> Any:
        """Get the current value of a sensor."""

        return self.data["sensors"][variable]

    async def async_shutdown(self):
        """Shutdown this coordinator."""

        await self._api.async_close()
        return await super().async_shutdown()
