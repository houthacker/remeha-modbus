"""Platform for number entities in the Remeha Modbus integration."""

import logging
from abc import ABC, abstractmethod
from functools import cached_property
from typing import override

from aio_remeha_modbus.gtw08 import GTW08
from aio_remeha_modbus.gtw08.climate_zone import ClimateZone
from aio_remeha_modbus.gtw08.const import Limits
from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoard
from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.const import (
    DOMAIN,
    TEMPERATURE_STEP,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add all Remeha Modbus number entities based on the given config entry."""

    api: GTW08 = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]

    entities: list[NumberEntity] = []

    # TODO Is this the correct parent device board?
    mainboards: list[DeviceBoard] = coordinator.get_devices(lambda device: device.is_mainboard())
    mainboard = mainboards[0] if mainboards else None
    if mainboard:
        entities += [
            RemehaSummerWinterNumber(api, coordinator, mainboard.id),
            RemehaNeutralBandNumber(api, coordinator, mainboard.id),
            RemehaBivalentTemperature(api, coordinator, mainboard.id),
            RemehaCompressorMinTemperature(api, coordinator, mainboard.id),
        ]
    else:
        _LOGGER.warning("No main board detected, skipping appliance-level Number entities.")

    dhw_climates: list[ClimateZone] = coordinator.get_climates(lambda c: c.is_domestic_hot_water())
    if dhw_climates:
        entities += [DhwHysteresisEntity(api, coordinator, climate.id) for climate in dhw_climates]
    else:
        _LOGGER.debug("No DHW zones found, skipping Number entities belonging to a DHW zone.")

    async_add_entities(entities)


class RemehaNumberEntity(CoordinatorEntity[RemehaUpdateCoordinator], NumberEntity, ABC):
    """A generic number entity."""

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator):
        """Create a new number entity."""

        super().__init__(coordinator)

        self._api: GTW08 = api

    @abstractmethod
    def get_owning_device(self) -> int | None:
        """Return the id of the owning device."""

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this instance belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this instance is not owned by any device.

        """

        owning_device = self.get_owning_device()
        if owning_device is None:
            return None

        device_instance: DeviceBoard | None = self.coordinator.get_device(id=owning_device)
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


class RemehaApplianceNumberEntity(RemehaNumberEntity):
    """A number entity that resides on the appliance level."""

    def __init__(
        self, api: GTW08, coordinator: RemehaUpdateCoordinator, owning_device_id: int | None
    ):
        """Create a new appliance-level number entity."""

        super().__init__(api, coordinator)

        self._owning_device_id = owning_device_id

    @override
    def get_owning_device(self) -> int | None:
        return self._owning_device_id


class RemehaZonedNumberEntity(RemehaNumberEntity):
    """A number entity belonging to a climate zone."""

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, zone_id: int):
        """Create a new zoned number entity."""

        super().__init__(api, coordinator)

        self._zone_id = zone_id

    @property
    def _zone(self) -> ClimateZone:
        """Return the modbus climate zone."""
        zone = self.coordinator.get_climate(self._zone_id)
        assert zone is not None

        return zone

    @override
    def get_owning_device(self) -> int | None:
        return self._zone.owning_device


class DhwHysteresisEntity(RemehaZonedNumberEntity):
    """Hysteresis entity linked to a RemehaDhwClimate."""

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_max_value = Limits.HYSTERESIS_MAX_TEMP
    _attr_native_min_value = Limits.HYSTERESIS_MIN_TEMP
    _attr_native_step = TEMPERATURE_STEP
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_should_poll = False
    _attr_translation_key = "dhw_hysteresis"
    _attr_name = "dhw_hysteresis"

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, zone_id: int):
        """Create a new DHW hysteresis entity."""

        super().__init__(api, coordinator, zone_id)

        self._attr_unique_id = f"dhw_zone_{zone_id}_hysteresis"

    @property
    def native_value(self) -> float | None:
        """Return the current hysteris."""

        return self._zone.dhw_calorifier_hysteresis

    async def async_set_native_value(self, value: float) -> None:
        """Update the current hysteris value."""

        zone: ClimateZone = self._zone
        await zone.async_set_dhw_calorifier_hysteresis(value)
        self.async_write_ha_state()


class RemehaBivalentTemperature(RemehaApplianceNumberEntity):
    """Number entity to hold the outside temperature above which the backup generator is blocked."""

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = -10.0
    _attr_native_max_value = 20.0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_should_poll = False
    _attr_translation_key = "bivalent_temperature"
    _attr_name = "bivalent_temperature"

    def __init__(
        self, api: GTW08, coordinator: RemehaUpdateCoordinator, owning_device_id: int | None
    ):
        """Create a bivalent temperature entity."""

        super().__init__(api, coordinator, owning_device_id)

        self._attr_unique_id = "bivalent_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the bivalent temperature (parameter HP000)."""

        return self.coordinator.get_appliance().bivalent_temperature

    @override
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.get_appliance().async_set_bivalent_temperature(int(value))
        self.async_write_ha_state()


class RemehaCompressorMinTemperature(RemehaApplianceNumberEntity):
    """Number entity to hold the minimum outside temperature below which the heat pump compressor is stopped."""

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = -20.0
    _attr_native_max_value = 5.0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_should_poll = False
    _attr_translation_key = "compressor_min_temperature"
    _attr_name = "compressor_min_temperature"

    def __init__(
        self, api: GTW08, coordinator: RemehaUpdateCoordinator, owning_device_id: int | None
    ):
        """Create a bivalent temperature entity."""

        super().__init__(api, coordinator, owning_device_id)

        self._attr_unique_id = "compressor_min_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the minimum outside temperature before the compressor is stopped (parameter HP051)."""

        return self.coordinator.get_appliance().heat_pump_compressor_min_temperature

    @override
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.get_appliance().async_set_heat_pump_compressor_min_temperature(
            int(value)
        )
        self.async_write_ha_state()


class RemehaSummerWinterNumber(RemehaApplianceNumberEntity):
    """Number entity for the summer/winter outdoor temperature threshold (parameter AP073).

    Above this outside temperature the appliance switches to summer mode and stops heating.
    """

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = 10.0
    _attr_native_max_value = 30.5
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"
    _attr_should_poll = False
    _attr_translation_key = "summer_winter_threshold"
    _attr_name = "summer_winter_threshold"

    def __init__(
        self, api: GTW08, coordinator: RemehaUpdateCoordinator, owning_device_id: int | None
    ):
        """Create a new summer/winter threshold entity."""

        super().__init__(api, coordinator, owning_device_id)

        self._attr_unique_id = "summer_winter"

    @property
    def native_value(self) -> float | None:
        """Return the current summer/winter threshold."""

        return self.coordinator.get_appliance().summer_winter

    async def async_set_native_value(self, value: float) -> None:
        """Update the summer/winter threshold."""

        await self.coordinator.get_appliance().async_set_summer_winter(value)
        self.async_write_ha_state()


class RemehaNeutralBandNumber(RemehaApplianceNumberEntity):
    """Number entity for the neutral band below the summer/winter limit (parameter AP075).

    Within this band the appliance neither heats nor cools (transition season).
    """

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = 0.0
    _attr_native_max_value = 20.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"
    _attr_should_poll = False
    _attr_translation_key = "neutral_band_summer_winter"
    _attr_name = "neutral_band_summer_winter"

    def __init__(
        self, api: GTW08, coordinator: RemehaUpdateCoordinator, owning_device_id: int | None
    ):
        """Create a new neutral-band entity."""

        super().__init__(api, coordinator, owning_device_id)

        self._attr_unique_id = "neutral_band_summer_winter"

    @property
    def native_value(self) -> float | None:
        """Return the current neutral band."""

        return self.coordinator.get_appliance().neutral_band_summer_winter

    async def async_set_native_value(self, value: float) -> None:
        """Update the neutral band."""

        await self.coordinator.get_appliance().async_set_neutral_band_summer_winter(value)
        self.async_write_ha_state()
