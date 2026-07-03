"""Platform for number entities in the Remeha Modbus integration."""

import logging
from typing import cast

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import DeviceInstance, RemehaApi
from custom_components.remeha_modbus.api.climate_zone import ClimateZone
from custom_components.remeha_modbus.const import (
    DOMAIN,
    TEMPERATURE_STEP,
    Limits,
    MetaRegisters,
    ZoneRegisters,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add all Remeha Modbus number entities based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]

    entities: list[NumberEntity] = []

    mainboards: list[DeviceInstance] = coordinator.get_devices(lambda device: device.is_mainboard())
    if mainboards:
        entities.append(
            RemehaSummerWinterNumber(
                api=api, coordinator=coordinator, parent_device_id=mainboards[0].id
            )
        )
        entities.append(
            RemehaNeutralBandNumber(
                api=api, coordinator=coordinator, parent_device_id=mainboards[0].id
            )
        )

    climates: list[ClimateZone] = coordinator.get_climates(lambda c: c.is_domestic_hot_water())
    if climates:
        entities.extend(
            DhwHysteresisEntity(api=api, coordinator=coordinator, zone_id=climate.id)
            for climate in climates
        )
    else:
        _LOGGER.debug("No DHW climates found so not adding any DhwHysteresis entities.")

    async_add_entities(entities)


class DhwHysteresisEntity(CoordinatorEntity[RemehaUpdateCoordinator], NumberEntity):
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

        return cast(float, self._zone.dhw_calorifier_hysteresis)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current hysteris value."""

        zone: ClimateZone = self._zone
        offset: int = self._api.get_zone_register_offset(zone=zone)
        await self._api.async_write_variable(
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

        device_instance: DeviceInstance | None = self.coordinator.get_device(id=zone.owning_device)
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


class RemehaSummerWinterNumber(CoordinatorEntity[RemehaUpdateCoordinator], NumberEntity):
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
    _attr_translation_key = DOMAIN

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create a new summer/winter threshold entity."""

        super().__init__(coordinator)

        self._api: RemehaApi = api
        self._parent_device_id = parent_device_id
        self._attr_unique_id = "summer_winter"
        self._attr_name = "summer_winter"

    @property
    def native_value(self) -> float:
        """Return the current summer/winter threshold."""

        return cast(float, self.coordinator.get_appliance().summer_winter)

    async def async_set_native_value(self, value: float) -> None:
        """Update the summer/winter threshold."""

        await self._api.async_write_variable(variable=MetaRegisters.SUMMER_WINTER, value=value)

        # Update the value so users don't have to wait until the next sync.
        self.coordinator.get_appliance().summer_winter = value
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this instance belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this instance is not owned by any device.

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


class RemehaNeutralBandNumber(CoordinatorEntity[RemehaUpdateCoordinator], NumberEntity):
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
    _attr_translation_key = DOMAIN

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create a new neutral-band entity."""

        super().__init__(coordinator)

        self._api: RemehaApi = api
        self._parent_device_id = parent_device_id
        self._attr_unique_id = "neutral_band_summer_winter"
        self._attr_name = "neutral_band_summer_winter"

    @property
    def native_value(self) -> float:
        """Return the current neutral band."""

        return cast(float, self.coordinator.get_appliance().neutral_band_summer_winter)

    async def async_set_native_value(self, value: float) -> None:
        """Update the neutral band."""

        await self._api.async_write_variable(
            variable=MetaRegisters.NEUTRAL_BAND_SUMMER_WINTER, value=value
        )

        # Update the value so users don't have to wait until the next sync.
        self.coordinator.get_appliance().neutral_band_summer_winter = value
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this instance belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this instance is not owned by any device.

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
