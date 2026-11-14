"""Platform for DHW climate zones over modbus."""

import logging
from datetime import datetime, time
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast, override

from aio_remeha_modbus.gtw08 import GTW08
from aio_remeha_modbus.gtw08.climate_zone import (
    ClimateZoneFunction,
    ClimateZoneMode,
    ClimateZoneRunningMode,
)
from aio_remeha_modbus.gtw08.const import ClimateZoneScheduleId
from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoardType
from dateutil import relativedelta
from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.components.water_heater.const import (
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_GAS,
    STATE_HEAT_PUMP,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.remeha_modbus.const import (
    DOMAIN,
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
    TEMPERATURE_STEP,
    WATER_HEATER_SCHEDULING_PRESETS,
    WATER_HEATER_STATE_OIL,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.helpers.entities import generate_unique_id

if TYPE_CHECKING:
    from aio_remeha_modbus.gtw08.climate_zone import ClimateZone
    from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoard
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Instantiate a new Remeha Modbus climate entity based on the given config entry."""

    api: GTW08 = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]

    entities = [
        RemehaWaterHeaterEntity.create_instance(api, coordinator, zone_id)
        for zone_id in coordinator.data["climates"]
        if (zone := coordinator.get_climate(zone_id)) is not None and zone.is_domestic_hot_water()
    ]
    async_add_entities(entities)


class RemehaWaterHeaterEntity(CoordinatorEntity[RemehaUpdateCoordinator], WaterHeaterEntity):
    """Water heater entity backed by a Remeha DHW zone over modbus."""

    _attr_has_entity_name = True
    _attr_precision = PRECISION_TENTHS
    _attr_should_poll: bool = False
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )
    _attr_target_temperature_step: float | None = TEMPERATURE_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new climate entity."""
        super().__init__(coordinator)
        self.api: GTW08 = api
        self.coordinator: RemehaUpdateCoordinator = coordinator
        self.climate_zone_id: int = climate_zone_id

        self._attr_unique_id = generate_unique_id(climate_zone_id)
        self._attr_extra_state_attributes = {
            "zone_id": climate_zone_id,
            "flow_temperature": None,
        }

        _LOGGER.debug("Creating new RemehaWaterHeater entity [%s]", self._attr_unique_id)

    @staticmethod
    def create_instance(
        api: GTW08, coordinator: RemehaUpdateCoordinator, climate_zone_id: int
    ) -> RemehaWaterHeaterEntity:
        """Create a new `RemehaWaterHeaterEntity`.

        Args:
          api (GTW08): The GTW-08 API instance that talks to modbus.
          coordinator (RemehaUpdateCoordinator): The update coordinator.
          climate_zone_id (int): The one-based climate zone id.

        """

        mainboard: DeviceBoard = coordinator.get_mainboard()
        zone: ClimateZone | None = coordinator.get_climate(climate_zone_id)

        if mainboard.board_category is None:
            raise ValueError(
                "Detected main board does not designate a category: cannot determine correct water_heater entity type to create."
            )

        if zone is None:
            raise ValueError(f"No existing ClimateZone with id {climate_zone_id}")

        if zone.is_domestic_hot_water():
            cls: type[RemehaWaterHeaterEntity]

            match mainboard.board_category.type:
                case DeviceBoardType.CU_GH | DeviceBoardType.EEC:
                    cls = RemehaGasWaterHeaterEntity
                case DeviceBoardType.CU_HW:
                    cls = RemehaHeatPumpBoilerEntity
                case DeviceBoardType.CU_OH:
                    cls = RemehaOilWaterHeaterEntity
                case DeviceBoardType.EHC | DeviceBoardType.EHC_ALT:
                    cls = RemehaElectricWaterHeaterEntity
                case _:
                    raise ValueError(
                        f"Unsupported device board type {mainboard.board_category.type.name}"
                    )

            return cls(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

        if zone.type is None:
            raise ValueError(f"No type defined for zone {zone.id}")

        raise ValueError(f"Unsupported zone type {zone.type.name}")

    @property
    def _zone(self) -> ClimateZone:
        """Return the modbus climate zone."""
        return self.coordinator.data["climates"][self.climate_zone_id]

    @property
    def available(self) -> bool:
        """Return True if the water heater is available.

        If the underlying `ClimateZone.function` is `ClimateZoneFunction.DISABLED`,
        this entity will be unavailable.
        """

        return super().available and self._zone.function is not ClimateZoneFunction.DISABLED

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this climate belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this climate is not owned by any device.

        """
        zone: ClimateZone = self._zone

        if zone.owning_device is None:
            return None

        device_instance: DeviceBoard | None = self.coordinator.get_device(id=zone.owning_device)
        if device_instance is None:
            return None

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

    @property
    def current_temperature(self) -> float | None:
        """Return the current water temperature."""

        return self._zone.current_temparature

    @property
    def target_temperature(self) -> float | None:
        """The current temperature setpoint."""

        return self._zone.current_setpoint

    @property
    def max_temp(self) -> float:
        """The maximum temperature of this water heater."""

        return self._zone.max_temp

    @property
    def min_temp(self) -> float:
        """The minimum temperature of this water heater."""

        return self._zone.min_temp

    @property
    def name(self) -> str | None:
        """The name of this water heater."""

        return self._zone.short_name

    @property
    def calorifier_hysteresis(self) -> float | None:
        """Return the hysteresis to start the tank load.

        This means the DHW tank starts heating up once `self.target_temperature - self.current_temperature >= self.calorifier_hysteresis`.
        """

        return self._zone.dhw_calorifier_hysteresis

    @property
    def is_away_mode_on(self) -> bool | None:
        """Whether this water heater is in away/holiday mode."""

        return self._zone.running_mode is ClimateZoneRunningMode.HOLIDAY

    @property
    def tank_temperature_top(self) -> float | None:
        """Return the temperature measured at the top of the tank.

        Returns:
            The temperature measured by the tank top sensor (`DM001`)

        """

        return self._zone.dhw_tank_temperature_top

    @override
    async def async_added_to_hass(self) -> None:
        """Set extra attributes when being added to HA."""

        self._attr_extra_state_attributes["flow_temperature"] = self._zone.flow_temperature
        return await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Set flow_temperature as an extra attribute."""

        self._attr_extra_state_attributes["flow_temperature"] = self._zone.flow_temperature
        return super()._handle_coordinator_update()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        zone = self._zone

        setpoint: float = kwargs[ATTR_TEMPERATURE]
        await zone.async_set_current_setpoint(setpoint)

        operation_mode: str | None = kwargs.get(ATTR_OPERATION_MODE)
        if operation_mode:
            await self.async_set_operation_mode(operation_mode)

        self.async_write_ha_state()

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        zone = self._zone

        if operation_mode in [STATE_GAS, WATER_HEATER_STATE_OIL, STATE_HEAT_PUMP]:
            await zone.async_set_mode(ClimateZoneMode.MANUAL)
        elif operation_mode == STATE_ECO:
            await zone.async_set_mode(ClimateZoneMode.ANTI_FROST)
        elif operation_mode == REMEHA_PRESET_SCHEDULE_1:
            await zone.async_set_selected_schedule(ClimateZoneScheduleId.SCHEDULE_1)
            await zone.async_set_mode(ClimateZoneMode.SCHEDULING)
        elif operation_mode == REMEHA_PRESET_SCHEDULE_2:
            await zone.async_set_selected_schedule(ClimateZoneScheduleId.SCHEDULE_2)
            await zone.async_set_mode(ClimateZoneMode.SCHEDULING)
        elif operation_mode == REMEHA_PRESET_SCHEDULE_3:
            await zone.async_set_selected_schedule(ClimateZoneScheduleId.SCHEDULE_3)
            await zone.async_set_mode(ClimateZoneMode.SCHEDULING)

        self.async_write_ha_state()

    @override
    async def async_turn_away_mode_on(self) -> None:
        zone = self._zone

        start_time = datetime.now()
        end_time = datetime.combine(
            (start_time + relativedelta.relativedelta(weeks=1)).date(), time.max
        )

        await zone.async_enable_holiday_mode(start_time, end_time)
        self.async_write_ha_state()

    @override
    async def async_turn_away_mode_off(self) -> None:
        zone = self._zone

        await zone.async_disable_holiday_mode()
        self.async_write_ha_state()


class RemehaGasWaterHeaterEntity(RemehaWaterHeaterEntity):
    """An entity for gas based water heaters like the Quinta Ace."""

    _attr_operation_list = [
        STATE_GAS,
        STATE_ECO,
        REMEHA_PRESET_SCHEDULE_1,
        REMEHA_PRESET_SCHEDULE_2,
        REMEHA_PRESET_SCHEDULE_3,
    ]

    _attr_translation_key = "water_heater_gas"

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new `RemehaGasWaterHeaterEntity`."""

        super().__init__(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

    @property
    @override
    def current_operation(self) -> str | None:
        zone = self._zone

        match zone.mode:
            case ClimateZoneMode.ANTI_FROST:
                return STATE_ECO
            case ClimateZoneMode.MANUAL:
                return STATE_GAS
            case ClimateZoneMode.SCHEDULING:
                return WATER_HEATER_SCHEDULING_PRESETS[cast(int, zone.selected_schedule)]
            case _:
                return STATE_ECO


class RemehaOilWaterHeaterEntity(RemehaWaterHeaterEntity):
    """An entity for oil based water heaters like the Hera Condens series."""

    _attr_operation_list = [
        WATER_HEATER_STATE_OIL,
        STATE_ECO,
        REMEHA_PRESET_SCHEDULE_1,
        REMEHA_PRESET_SCHEDULE_2,
        REMEHA_PRESET_SCHEDULE_3,
    ]

    _attr_translation_key = "water_heater_oil"

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new `RemehaOilWaterHeaterEntity`."""

        super().__init__(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

    @property
    @override
    def current_operation(self) -> str | None:
        zone = self._zone

        match zone.mode:
            case ClimateZoneMode.ANTI_FROST:
                return STATE_ECO
            case ClimateZoneMode.MANUAL:
                return WATER_HEATER_STATE_OIL
            case ClimateZoneMode.SCHEDULING:
                return WATER_HEATER_SCHEDULING_PRESETS[cast(int, zone.selected_schedule)]


class RemehaElectricWaterHeaterEntity(RemehaWaterHeaterEntity):
    """An entity for water heaters within an all-electric appliance like the Mercuria Ace."""

    _attr_operation_list = [
        STATE_HEAT_PUMP,  # Manual
        STATE_ECO,  # Eco
        REMEHA_PRESET_SCHEDULE_1,  # Schedule
    ]

    _attr_translation_key = "water_heater_electric"

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new `RemehaElectricWaterHeaterEntity`."""

        super().__init__(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

    @property
    @override
    def current_operation(self) -> str | None:
        zone = self._zone

        match zone.mode:
            case ClimateZoneMode.ANTI_FROST:
                return STATE_ECO
            case ClimateZoneMode.MANUAL:
                return STATE_HEAT_PUMP
            case ClimateZoneMode.SCHEDULING:
                return REMEHA_PRESET_SCHEDULE_1


class RemehaHeatPumpBoilerEntity(RemehaElectricWaterHeaterEntity):
    """An entity for heat pump based boilers like the Azorra Ace."""

    _attr_operation_list = [
        STATE_HEAT_PUMP,  # Manual
        STATE_ECO,  # Eco
        REMEHA_PRESET_SCHEDULE_1,  # Schedule 1
        REMEHA_PRESET_SCHEDULE_2,  # Schedule 2
        REMEHA_PRESET_SCHEDULE_3,  # Schedule 3
    ]

    _attr_translation_key = "heat_pump_boiler"

    def __init__(self, api: GTW08, coordinator: RemehaUpdateCoordinator, climate_zone_id: int):
        """Create a new `RemehaHeatPumpBoilerEntity`."""

        super().__init__(api=api, coordinator=coordinator, climate_zone_id=climate_zone_id)

    @property
    @override
    def current_operation(self) -> str | None:
        zone = self._zone

        match zone.mode:
            case ClimateZoneMode.ANTI_FROST:
                return STATE_ECO
            case ClimateZoneMode.MANUAL:
                return STATE_HEAT_PUMP
            case ClimateZoneMode.SCHEDULING:
                assert zone.selected_schedule is not None
                return WATER_HEATER_SCHEDULING_PRESETS[zone.selected_schedule]
