"""Platform for climate entities over modbus."""

import logging
from typing import Final, Self

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.api import (
    ClimateZone,
    ClimateZoneHeatingMode,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    DeviceInstance,
    RemehaApi,
)
from custom_components.remeha_modbus.const import (
    CLIMATE_DEFAULT_PRESETS,
    CLIMATE_DHW_EXTRA_PRESETS,
    DOMAIN,
    HA_PRESET_ANTI_FROST,
    HA_PRESET_MANUAL,
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
    TEMPERATURE_STEP,
    MetaRegisters,
    ZoneRegisters,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import InvalidClimateContext

HA_SCHEDULE_TO_REMEHA_SCHEDULE: Final[dict[str, ClimateZoneScheduleId]] = {
    REMEHA_PRESET_SCHEDULE_1: ClimateZoneScheduleId.SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2: ClimateZoneScheduleId.SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3: ClimateZoneScheduleId.SCHEDULE_3,
}

HA_CLIMATE_PRESET_TO_REMEHA_ZONE_MODE: Final[dict[str, ClimateZoneMode]] = {
    HA_PRESET_ANTI_FROST: ClimateZoneMode.ANTI_FROST,
    HA_PRESET_MANUAL: ClimateZoneMode.MANUAL,
    PRESET_COMFORT: ClimateZoneMode.MANUAL,
    PRESET_ECO: ClimateZoneMode.ANTI_FROST,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Instantiate a new Remeha Modbus climate entity based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]

    entities = [
        RemehaClimateEntity.create_instance(api, coordinator, zone_id)
        for zone_id in coordinator.data["climates"]
    ]
    async_add_entities(entities)


class RemehaClimateEntity(CoordinatorEntity, ClimateEntity):
    """Climate entity backed by a Remeha Modbus implementation."""

    _attr_has_entity_name = True
    _attr_precision = PRECISION_TENTHS
    _attr_should_poll: bool = False
    _attr_target_temperature_step: float = TEMPERATURE_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    def __init__(self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new climate entity."""
        super().__init__(coordinator)
        self.api: RemehaApi = api
        self.coordinator: RemehaUpdateCoordinator = coordinator
        self.climate_zone_id: int = climate_zone_id

        self._attr_unique_id = f"zone_{climate_zone_id}"

        _LOGGER.debug("Creating new RemehaModbusClimate entity [%s]", self._attr_unique_id)

    @classmethod
    def create_instance(
        cls, api: RemehaApi, coordinator: RemehaUpdateCoordinator, climate_zone_id: int
    ) -> Self:
        """Create the correct climate entity instance type."""

        zone: ClimateZone = coordinator.get_climate(climate_zone_id)
        if zone.is_domestic_hot_water():
            return RemehaDhwEntity(
                api=api, coordinator=coordinator, climate_zone_id=climate_zone_id
            )

        if zone.is_central_heating():
            return RemehaChEntity(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

        raise ValueError(f"Unsupported zone type {zone.type.name}")

    @property
    def _zone(self) -> ClimateZone:
        """Return the modbus climate zone."""
        return self.coordinator.data["climates"][self.climate_zone_id]

    @property
    def current_temperature(self) -> float | None:
        """Return the current zone temperature."""

        return self._zone.current_temparature

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this climate belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this climate is not owned by any device.

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

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature of this climate."""

        return self._zone.max_temp

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature of this climate."""

        return self._zone.min_temp

    @property
    def name(self) -> str:
        """Return the name of this climate."""

        return self._zone.short_name

    @property
    def target_temperature(self) -> float | None:
        """The current temperature setpoint."""

        return self._zone.current_setpoint


class RemehaDhwEntity(RemehaClimateEntity):
    """Remeha climate entity for Domestic Hot Water climates."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new RemehaDhwEntity."""
        super().__init__(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

    @property
    def calorifier_hysteresis(self) -> float:
        """Return the hysteresis to start the tank load.

        This means the DHW tank starts heating up once `self.target_temperature - self.current_temperature >= self.calorifier_hysteresis`.
        """

        return self._zone.dhw_calorifier_hysteresis

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action.

        For a DHW climate, the action is based on whether the pump is running.
        """

        zone: ClimateZone = self._zone
        return HVACAction.HEATING if zone.pump_running is True else HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""

        zone: ClimateZone = self._zone
        match zone.mode:
            case ClimateZoneMode.SCHEDULING:
                return HVACMode.AUTO
            case ClimateZoneMode.MANUAL:
                return HVACMode.HEAT
            case ClimateZoneMode.ANTI_FROST:
                return HVACMode.OFF
            case _:
                _LOGGER.warning(
                    "Cannot derive hvac_mode from ClimateZoneMode %s; falling back to OFF.",
                    zone.mode.name,
                )
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the available HVAC modes for this zone."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

    @property
    def preset_mode(self) -> str | None:
        """Return the current active preset.

        Notes
        -----
        * The last two preset modes are always called `manual` and `anti_frost`, following the naming
            of the GTW-08 parameters. However, in a DHW zone these actually correspond to `COMFORT` and `ECO`.

        """

        zone: ClimateZone = self._zone
        match zone.mode:
            case ClimateZoneMode.SCHEDULING:
                return self.preset_modes[zone.selected_schedule.value]
            case ClimateZoneMode.MANUAL | ClimateZoneMode.ANTI_FROST:
                return CLIMATE_DHW_EXTRA_PRESETS[zone.mode.value - 1]
            case _:
                _LOGGER.warning(
                    "Cannot derive preset_mode for ClimateZoneMode %s, falling back to 'none'.",
                    zone.mode.name,
                )
                return PRESET_NONE

    @property
    def preset_modes(self) -> list[str]:
        """Return the presets available for Remeha DHW climates."""
        return [*CLIMATE_DEFAULT_PRESETS, *CLIMATE_DHW_EXTRA_PRESETS]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set the new HVAC mode."""

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        if hvac_mode == HVACMode.OFF:
            # There is no real 'off' mode, but 'eco' mode comes as close as possible to it.
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.ANTI_FROST,
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.ANTI_FROST
        elif hvac_mode == HVACMode.HEAT:
            # Also, there is no real 'heat' mode to force, like 'go heat now',
            # although you could play with setpoint and hysteresis in comfort mode.
            # HVACMode.HEAT translates best to 'comfort' mode since that keeps the DHW boiler
            # at the configured comfort(able) temperature.
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.MANUAL,
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.MANUAL
        elif hvac_mode == HVACMode.AUTO:
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.SCHEDULING,
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.SCHEDULING
        else:
            raise InvalidClimateContext(
                translation_domain=DOMAIN,
                translation_key="climate_invalid_operation_ctx_hvac",
                translation_placeholders={
                    "hvac_mode": hvac_mode.name,
                    "zone_name": self.name,
                },
            )

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str):
        """Set the preset mode."""

        if self.preset_mode == preset_mode:
            _LOGGER.debug("Ignoring requested preset mode since this is the current mode already.")
            return

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        if preset_mode in [PRESET_COMFORT, PRESET_ECO]:
            zone_mode: ClimateZoneMode = HA_CLIMATE_PRESET_TO_REMEHA_ZONE_MODE[preset_mode]
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE, value=zone_mode, offset=zone_offset
            )

            zone.mode = zone_mode
        elif preset_mode in CLIMATE_DEFAULT_PRESETS:
            # Scheduling: set active schedule first, then set mode to scheduling.
            # This prevents the user ending up with an invalid zone state if the latter fails.
            schedule_id: ClimateZoneScheduleId = HA_SCHEDULE_TO_REMEHA_SCHEDULE[preset_mode]

            await self.api.async_write_variable(
                variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
                value=schedule_id,
                offset=zone_offset,
            )
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.SCHEDULING,
                offset=zone_offset,
            )

            zone.mode = ClimateZoneMode.SCHEDULING
            zone.selected_schedule = schedule_id
        else:
            # Unknown preset mode
            raise InvalidClimateContext(
                translation_domain=DOMAIN,
                translation_key="climate_unsupported_preset_mode",
                translation_placeholders={"preset_mode": preset_mode},
            )

        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set the temperature setpoint."""

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        target_temperature: float = float(kwargs[ATTR_TEMPERATURE])
        if self.preset_mode == PRESET_COMFORT:
            await self.api.async_write_variable(
                variable=ZoneRegisters.DHW_COMFORT_SETPOINT,
                value=target_temperature,
                offset=zone_offset,
            )
        elif self.preset_mode == PRESET_ECO:
            await self.api.async_write_variable(
                variable=ZoneRegisters.DHW_REDUCED_SETPOINT,
                value=target_temperature,
                offset=zone_offset,
            )
        else:
            raise InvalidClimateContext(
                translation_domain=DOMAIN,
                translation_key="climate_invalid_operation_ctx",
                translation_placeholders={
                    "operation": "set_temperature",
                    "preset_mode": self.preset_mode,
                },
            )

        # Update HA state until next poll
        zone.current_setpoint = target_temperature
        self.async_write_ha_state()


class RemehaChEntity(RemehaClimateEntity):
    """Remeha climate entity for Central Heating climates."""

    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new RemehaDhwEntity."""
        super().__init__(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action.

        There only is a current HVAC action if the zone pump is running.
        If that is the case, the HVAC action is determined by the current HVAC mode.
        """

        zone: ClimateZone = self._zone
        if zone.pump_running:
            match zone.heating_mode:
                case ClimateZoneHeatingMode.HEATING:
                    return HVACAction.HEATING
                case ClimateZoneHeatingMode.COOLING:
                    return HVACAction.COOLING

        return HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""

        zone: ClimateZone = self._zone
        cooling_forced: bool = self.coordinator.is_cooling_forced()

        match zone.mode:
            case ClimateZoneMode.SCHEDULING:
                return HVACMode.AUTO
            case ClimateZoneMode.ANTI_FROST:
                return HVACMode.OFF
            case ClimateZoneMode.MANUAL:
                return HVACMode.COOL if cooling_forced else HVACMode.HEAT_COOL

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the available HVAC modes for this zone."""
        return [HVACMode.OFF, HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.AUTO]

    @property
    def preset_mode(self) -> str | None:
        """Return the current active preset.

        Notes
        -----
        * The last two preset modes are always called `manual` and `anti_frost`, following the naming
            of the GTW-08 parameters. However, in a DHW zone these actually correspond to `COMFORT` and `ECO`.

        """

        zone: ClimateZone = self._zone
        if zone.mode == ClimateZoneMode.SCHEDULING:
            return self.preset_modes[zone.selected_schedule.value]

        return zone.mode.name.lower()

    @property
    def preset_modes(self) -> list[str]:
        """Return the presets available for Remeha DHW climates."""
        return [
            *CLIMATE_DEFAULT_PRESETS,
            ClimateZoneMode.MANUAL.name.lower(),
            ClimateZoneMode.ANTI_FROST.name.lower(),
        ]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set the new HVAC mode."""

        if self.hvac_mode == hvac_mode:
            _LOGGER.debug("Ignoring requested HVAC mode since this is the current mode already.")
            return

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        if hvac_mode == HVACMode.AUTO:
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.SCHEDULING,
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.SCHEDULING
        elif hvac_mode in [HVACMode.HEAT_COOL, HVACMode.COOL]:
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE, value=ClimateZoneMode.MANUAL, offset=zone_offset
            )
            await self.api.async_write_variable(
                variable=MetaRegisters.COOLING_FORCED,
                value=bool(hvac_mode == HVACMode.COOL),
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.MANUAL
        elif hvac_mode == HVACMode.OFF:
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.ANTI_FROST,
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.ANTI_FROST
        else:
            raise InvalidClimateContext(
                translation_domain=DOMAIN,
                translation_key="climate_invalid_operation_ctx_hvac",
                translation_placeholders={
                    "hvac_mode": hvac_mode.name,
                    "zone_name": self.name,
                },
            )

        # ClimateZone variables updated, tell that to HA
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str):
        """Set the preset mode."""

        if self.preset_mode == preset_mode:
            _LOGGER.debug("Ignoring requested preset mode since this is the current mode already.")
            return

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        if preset_mode in [HA_PRESET_MANUAL, HA_PRESET_ANTI_FROST]:
            zone_mode: ClimateZoneMode = HA_CLIMATE_PRESET_TO_REMEHA_ZONE_MODE[preset_mode]
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE, value=zone_mode, offset=zone_offset
            )
            zone.mode = zone_mode
        elif preset_mode in CLIMATE_DEFAULT_PRESETS:
            # Scheduling: set active schedule first, then set mode to scheduling.
            # This prevents the user ending up with an invalid zone state if the latter fails.
            schedule_id: ClimateZoneScheduleId = HA_SCHEDULE_TO_REMEHA_SCHEDULE[preset_mode]

            await self.api.async_write_variable(
                variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
                value=schedule_id,
                offset=zone_offset,
            )
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.SCHEDULING,
                offset=zone_offset,
            )
            zone.mode = ClimateZoneMode.SCHEDULING
            zone.selected_schedule = ClimateZoneScheduleId(schedule_id)
        else:
            # Unknown preset mode
            raise InvalidClimateContext(
                translation_domain=DOMAIN,
                translation_key="climate_unsupported_preset_mode",
                translation_placeholders={"preset_mode": preset_mode},
            )

        # ClimateZone variables updated, tell that to HA
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set the room temperature."""

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        if self.preset_mode != ClimateZoneMode.MANUAL.name.lower():
            raise InvalidClimateContext(
                translation_domain=DOMAIN,
                translation_key="climate_invalid_operation_ctx",
                translation_placeholders={
                    "operation": "set_temperature",
                    "preset_mode": self.preset_mode,
                },
            )

        target_temperature: float = float(kwargs[ATTR_TEMPERATURE])
        await self.api.async_write_variable(
            variable=ZoneRegisters.ROOM_MANUAL_SETPOINT,
            value=target_temperature,
            offset=zone_offset,
        )

        # TODO if mode is scheduling, do a temporary override

        # Update HA state until next poll
        zone.current_setpoint = target_temperature
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn the climate zone off."""

        zone: ClimateZone = self._zone
        zone_offset: int = self.api.get_zone_register_offset(zone)
        if self.preset_mode != HA_PRESET_ANTI_FROST:
            await self.api.async_write_variable(
                variable=ZoneRegisters.MODE,
                value=ClimateZoneMode.ANTI_FROST,
                offset=zone_offset,
            )
        else:
            _LOGGER.debug("Turning off climate %s that is already off; ignoring.", self.name)

        # Update HA state until next poll
        zone.mode = ClimateZoneMode.ANTI_FROST
        self.async_write_ha_state()
