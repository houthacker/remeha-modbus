"""Platform for number entities in the Remeha Modbus integration."""

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import ClimateZone, DeviceInstance, RemehaApi
from custom_components.remeha_modbus.const import DOMAIN, TEMPERATURE_STEP, Limits, ZoneRegisters
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Instantiate a new Remeha Modbus climate entity based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]

    climates: list[ClimateZone] = coordinator.get_climates(lambda c: c.is_domestic_hot_water())
    if climates:
        async_add_entities(
            [
                DhwHysteresisEntity(api=api, coordinator=coordinator, zone_id=climate.id)
                for climate in climates
            ]
        )
    else:
        _LOGGER.debug("No DHW climates found so not adding any DhwHysteresis entities.")


class DhwHysteresisEntity(CoordinatorEntity, NumberEntity):
    """Hysteresis entity linked to a RemehaDhwClimate."""

    _attr_has_entity_name = True
    _attr_device_class: NumberDeviceClass = NumberDeviceClass.TEMPERATURE
    _attr_native_max_value = Limits.HYSTERESIS_MAX_TEMP
    _attr_native_min_value = Limits.HYSTERESIS_MIN_TEMP
    _attr_native_step = TEMPERATURE_STEP
    _attr_native_unit_of_measurement = "°C"
    _attr_should_poll = False
    _attr_translation_key = DOMAIN

    def __init__(self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, zone_id: int):
        """Create a new DHW hysteresis entity."""

        super().__init__(coordinator)

        self._api: RemehaApi = api
        self._climate_zone_id = zone_id
        self._attr_unique_id = f"hysteresis_{zone_id}"
        self._attr_name = "dhw_hysteresis"

    @property
    def _zone(self) -> ClimateZone:
        """Return the modbus climate zone."""
        return self.coordinator.data["climates"][self._climate_zone_id]

    @property
    def native_value(self) -> float:
        """Return the current hysteris."""

        return self._zone.dhw_calorifier_hysteresis

    async def async_set_native_value(self, value: float) -> None:
        """Update the current hysteris value."""

        zone: ClimateZone = self._zone
        offset: int = self._api.get_zone_register_offset(zone=zone)
        await self._api.async_write_primitive(
            variable=ZoneRegisters.DHW_CALORIFIER_HYSTERESIS, value=value, offset=offset
        )

        # Update the value so users don't have to wait until the next sync.
        zone.dhw_calorifier_hysteresis = value

        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this instance belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this instance is not owned by any device.

        """
        zone: ClimateZone = self._zone

        if zone.owning_device is None:
            return None

        device_instance: DeviceInstance = self.coordinator.get_device(id=zone.owning_device)
        return DeviceInfo(
            identifiers={(DOMAIN, device_instance.article_number)},
            hw_version=f"HW{device_instance.hw_version[0]:02d}.{device_instance.hw_version[1]:02d}",
            manufacturer="Remeha",
            model=str(device_instance.board_category),
            sw_version=f"SW{device_instance.sw_version[0]:02d}.{device_instance.sw_version[1]:02d}",
        )
