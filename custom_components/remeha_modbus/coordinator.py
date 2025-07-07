"""Coordinator for fetching modbus data of Remeha devices."""

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import UUID

from dateutil.parser import parse
from homeassistant.components.climate import ClimateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import integration_entities
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from pymodbus import ModbusException

from custom_components.remeha_modbus.api import (
    Appliance,
    ClimateZone,
    DeviceInstance,
    HourlyForecast,
    RemehaApi,
    RemehaModbusStorage,
    WaitingListEntry,
    WeatherForecast,
    ZoneSchedule,
)
from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SELECTED_SCHEDULE,
    DHW_BOILER_CONFIG_SECTION,
    DHW_BOILER_ENERGY_LABEL,
    DHW_BOILER_HEAT_LOSS_RATE,
    DHW_BOILER_VOLUME,
    DOMAIN,
    EVENT_ZONE_SCHEDULE_UPDATED,
    HA_SCHEDULE_TO_REMEHA_SCHEDULE,
    PV_ANNUAL_EFFICIENCY_DECREASE,
    PV_CONFIG_SECTION,
    PV_INSTALLATION_DATE,
    PV_NOMINAL_POWER_WP,
    PV_ORIENTATION,
    PV_TILT,
    REMEHA_SENSORS,
    WEEKDAY_TO_MODBUS_VARIABLE,
    BoilerConfiguration,
    BoilerEnergyLabel,
    ClimateScheduleIdent,
    ClimateZoneScheduleId,
    ModbusVariableDescription,
    PVSystem,
    PVSystemOrientation,
    SchedulerLinkView,
    Weekday,
)
from custom_components.remeha_modbus.errors import (
    RemehaIncorrectServiceCall,
    RemehaModbusError,
    RemehaServiceException,
)

_LOGGER = logging.getLogger(__name__)


def _config_to_boiler_config(config: ConfigEntry) -> BoilerConfiguration:
    section = config.data[DHW_BOILER_CONFIG_SECTION]

    return BoilerConfiguration(
        volume=section.get(DHW_BOILER_VOLUME, None),
        heat_loss_rate=section.get(DHW_BOILER_HEAT_LOSS_RATE, None),
        energy_label=BoilerEnergyLabel(section[DHW_BOILER_ENERGY_LABEL])
        if DHW_BOILER_ENERGY_LABEL in section and section[DHW_BOILER_ENERGY_LABEL] is not None
        else None,
    )


def _config_to_pv_config(config: ConfigEntry) -> PVSystem:
    section = config.data[PV_CONFIG_SECTION]

    return PVSystem(
        nominal_power=section[PV_NOMINAL_POWER_WP],
        orientation=PVSystemOrientation(section[PV_ORIENTATION]),
        tilt=section.get(PV_TILT, None),
        annual_efficiency_decrease=section.get(PV_ANNUAL_EFFICIENCY_DECREASE, None),
        installation_date=parse(section[PV_INSTALLATION_DATE]).date()
        if PV_INSTALLATION_DATE in section
        else None,
    )


def _get_updated_schedules(
    old: dict[str, ClimateZone], new: dict[str, ClimateZone]
) -> list[ZoneSchedule]:
    """Get the updated zone schedules from `new`."""

    updated_new_schedules: list[ZoneSchedule] = []
    for key, old_zone in old.items():
        new_zone: ClimateZone = new[key]

        # Either both zones have a selected schedule,
        if old_zone.selected_schedule is not None and new_zone.selected_schedule is not None:
            updated_new_schedules += [
                schedule
                for key, schedule in new_zone.current_schedule.items()
                if old_zone.current_schedule[key] != schedule
            ]
        elif new_zone.selected_schedule is not None:
            updated_new_schedules += [
                schedule for schedule in new_zone.current_schedule.values() if schedule is not None
            ]

    return updated_new_schedules


class RemehaUpdateCoordinator(DataUpdateCoordinator):
    """Remeha Modbus coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: RemehaApi,
        store: RemehaModbusStorage,
    ):
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
        self._store: RemehaModbusStorage = store
        self._api: RemehaApi = api
        self._device_instances: dict[int, DeviceInstance] = {}

        # This list is populated by the added_to_hass() callback of the climate entities.
        self._climate_entity_ids: list[str] = []

    def _before_first_update(self) -> bool:
        return not self.data or "climates" not in self.data

    async def _async_setup(self):
        try:
            self._device_instances = {
                instance.id: instance for instance in await self._api.async_read_device_instances()
            }
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

        await self._store.async_load()

    async def _async_update_data(self) -> dict[str, dict[int, ClimateZone]]:
        try:
            zones: list[ClimateZone] = []
            is_cooling_forced: bool = await self._api.async_is_cooling_forced
            appliance: Appliance = await self._api.async_read_appliance()
            sensors = await self._api.async_read_sensor_values(list(REMEHA_SENSORS.keys()))
            if self._before_first_update():
                zones = await self._api.async_read_zones()
            else:
                zones = [
                    await self._api.async_read_zone_update(zone)
                    for zone in list(self.data["climates"].values())
                ]

                # Fire an event for each updated climate schedule.
                self._fire_schedule_update_events(
                    old_zones=self.data["climates"], new_zones={zone.id: zone for zone in zones}
                )
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

        return {
            "appliance": appliance,
            "climates": {zone.id: zone for zone in zones},
            "cooling_forced": is_cooling_forced,
            "sensors": sensors,
        }

    def _fire_schedule_update_events(
        self, old_zones: dict[str, ClimateZone], new_zones: dict[str, ClimateZone]
    ) -> None:
        # Assume that both dicts contain the same keys. If not, that would indicate
        # a zone has been added or removed in the Remeha appliance.
        # This scenario is explicitly not supported.

        for schedule in _get_updated_schedules(old=old_zones, new=new_zones):
            event_data = {"schedule": schedule}
            self.hass.bus.async_fire(EVENT_ZONE_SCHEDULE_UPDATED, event_data)

    @property
    def climate_entities(self) -> list[str]:
        """Return the list of owned climate entity ids."""
        return list(self._climate_entity_ids)

    def register_entity_id_of(self, entity: ClimateEntity) -> None:
        """Cache the entity_id of the given climate entity.

        Args:
            entity (RemehaClimateEntity): The entity to cache the id of.

        Raises:
            RemehaModbusError if the given entity is not owned by this integration.

        """

        if not entity.platform or entity.platform.platform_name != DOMAIN:
            raise RemehaModbusError(
                translation_domain=DOMAIN,
                translation_key="non_owned_entity",
                translation_placeholders={"entity_id": entity.entity_id},
            )

        self._climate_entity_ids.append(entity.entity_id)

    def is_remeha_modbus_entity(self, entity_id: str) -> bool:
        """Given an entity id, return whether it originates from this integration.

        Args:
            entity_id (str): The entity id.

        Returns:
            `True` if this entity originates from this integration, `False` otherwise.

        """

        return entity_id in integration_entities(hass=self.hass, entry_name=DOMAIN)

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

    def enqueue_for_linking(
        self, uuid: UUID, zone_id: int, schedule_id: ClimateZoneScheduleId, weekday: Weekday
    ):
        """Store the given identifiers, preparing them for linking a `ZoneSchedule` to a `scheduler.schedule`.

        If an equal entry already exists, this method has no effect.

        Args:
            uuid (UUID): The unique identifier added to the list of tags in the `scheduler.schedule`.
            zone_id (int): The id of the related `ClimateZone`.
            schedule_id (ClimateZoneScheduleId): The id of the related `ZoneSchedule`.
            weekday (Weekday): The weekday at which the zone schedule is active.

        """

        self._store.add_to_waiting_list(
            uuid=uuid, zone_id=zone_id, schedule_id=schedule_id, weekday=weekday
        )

    def pop_from_linking_waiting_list(self, uuid: UUID) -> WaitingListEntry | None:
        """Pop the waiting identifiers with uuid `uuid` from the waiting list.

        Args:
            uuid (UUID): The uuid listed in the tags of the `scheduler.schedule`

        Returns:
            A tuple containing the requested identifiers to be linked, or `None` if no such item exists.

        """

        return self._store.pop_from_waiting_list(uuid=uuid)

    async def async_get_scheduler_links(self) -> list[SchedulerLinkView]:
        """Return a list of all current scheduler links."""
        return [
            SchedulerLinkView(
                zone_id=entry.zone_id,
                schedule_id=ClimateZoneScheduleId(entry.schedule_id),
                weekday=entry.weekday,
                scheduler_entity_id=entry.schedule_entity_id,
            )
            for entry in await self._store.async_get_all()
        ]

    async def async_get_linked_scheduler_entity(
        self, zone_id: int, schedule_id: ClimateZoneScheduleId, weekday: Weekday
    ) -> str | None:
        """Get the entity id of the `scheduler.schedule` that is linked to the `ZoneSchedule` having the given id values.

        Args:
            zone_id (int): The id of the `ClimateZone`.
            schedule_id (ClimateZoneScheduleId): The id of the `ZoneSchedule` within the containing `ClimateZone`.
            weekday (Weekday): The weekday at which the zone schedule is active.

        Returns:
            str | None: The entity id of the linked `scheduler.schedule`, or `None` if no such entity exists.

        """

        entry = await self._store.async_get_attributes_by_zone(
            zone_id=zone_id, schedule_id=schedule_id, weekday=weekday
        )
        return entry.schedule_entity_id if entry else None

    async def async_get_linked_climate_schedule_identifiers(
        self, scheduler_entity_id: str
    ) -> ClimateScheduleIdent | None:
        """Get the id of the schedule linked to the given scheduler entity id.

        Args:
            scheduler_entity_id (str): The entity id of the `scheduler.schedule`.

        Returns:
            ClimateZoneScheduleId | None: The climate schedule id, or `None` if no such climate schedule exists.

        """

        entry = await self._store.async_get_attributes_by_entity_id(entity_id=scheduler_entity_id)
        return (
            ClimateScheduleIdent(
                entry.zone_id, ClimateZoneScheduleId(entry.schedule_id), entry.weekday
            )
            if entry
            else None
        )

    async def async_link_scheduler_entity(
        self, zone_id: int, schedule_id: ClimateZoneScheduleId, weekday: Weekday, entity_id: str
    ):
        """Link the given `entity_id` to `schedule`.

        Args:
            zone_id (int): The zone id of the schedule to link the entity to.
            schedule_id (ClimateZoneScheduleId): The schedule id to link the entity to.
            weekday (Weekday): The weekday at which the zone schedule is active.
            entity_id (str): The entity id of the related `scheduler.schedule`.

        """

        await self._store.async_upsert_schedule_attributes(
            zone_id=zone_id, schedule_id=schedule_id, schedule_entity_id=entity_id, weekday=weekday
        )

    async def async_unlink_climate_schedule(
        self, zone_id: int, schedule_id: ClimateZoneScheduleId, weekday: Weekday
    ) -> bool:
        """Unlink the given climate zone schedule from the related scheduler entity.

        Args:
            zone_id (int): The zone id of the schedule to link the entity to.
            schedule_id (ClimateZoneScheduleId): The schedule id to link the entity to.
            weekday (Weekday): The weekday at which the zone schedule is active.

        Returns:
            bool: `True` if the link store was updated due to this unlink, `False` otherwise.

        """
        return await self._store.async_remove_schedule_attributes(
            zone_id=zone_id, schedule_id=schedule_id, weekday=weekday
        )

    async def async_write_schedule(self, schedule: ZoneSchedule):
        """Write the given schedule to the modbus interface.

        If the schedule is successfully written to the modbus interface, the current
        state cache is also updated until the next refresh.

        Args:
            schedule (ZoneSchedule): The schedule to write.

        Raises:
            ModbusException: if writing `schedule` to the modbus interface fails.

        """
        await self._api.async_write_variable(
            variable=WEEKDAY_TO_MODBUS_VARIABLE[schedule.day],
            value=schedule,
            offset=self._api.get_zone_register_offset(zone=schedule.zone_id)
            + self._api.get_schedule_register_offset(schedule=schedule.id),
        )

        # Update the schedule in the related climate zone, until the next refresh.
        if schedule.zone_id in self.data["climates"]:
            zone: ClimateZone = self.data["climates"][schedule.zone_id]
            zone.current_schedule[schedule.day] = schedule

    async def async_read_registers(
        self, start_register: int, register_count: int, struct_format: str
    ) -> tuple[Any, ...]:
        """Read registers directly from the modbus interface.

        Args:
            start_register (int): The register to start reading at.
            register_count (int): The amount of registers to read.
            struct_format (str | bytes): The struct format to convert the register bytes to.

        Returns:
            A tuple containing values unpacked according to the format string.

        Raises:
            ModbusException: if a modbus error occurred while reading the registers.
            struct.error: if `struct_format` is an illegal struct format.

        """

        return await self._api.async_read_registers(
            start_register=start_register,
            register_count=register_count,
            struct_format=struct_format,
        )

    async def async_dhw_auto_schedule(
        self,
        hourly_forecasts: list[dict],
        temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS,
    ) -> None:
        """Create a schedule for tomorrow based on the given forecast.

        `hourly_forecasts` is a partial result of the `weather.get_forecasts` service, namely the list of forecasted conditions
        of the next 24 hours.

        ### Example hourly forecast
        ```
            {
                'datetime': '2025-05-13T15:00:00+02:00',
                'condition': 'sunny',
                'temperature': 22.0,
                'precipitation': 0.0,
                'wind_bearing': 92,
                'wind_speed': 14.0,
                'wind_speed_bft': 3,
                'solar_irradiance': 806
            }
        ```
        Attrs:
            hourly_forecasts (list[dict]): A list containing hourly forecasts for the next 24 hours.
            temperature_unit (UnitOfTemperature): The temperature of the weather unit providing the forecast. Converted to `UnitOfTemperature.CELSIUS` if necessary.
        """

        _LOGGER.debug("Searching for DHW zones")
        dhw_zones: list[ClimateZone] = self.get_climates(lambda zone: zone.is_domestic_hot_water())

        if not dhw_zones:
            raise RemehaIncorrectServiceCall(
                translation_domain=DOMAIN, translation_key="auto_schedule_no_dhw_climate"
            )
        if len(dhw_zones) > 1:
            _LOGGER.warning(
                "Found multiple DHW climate entities, using the first for auto scheduling."
            )

        dhw_zone: ClimateZone = dhw_zones[0]
        _LOGGER.debug("Using DHW zone with id=%d", dhw_zone.id)

        weather_forecast: WeatherForecast = WeatherForecast(
            unit_of_temperature=temperature_unit,
            forecasts=[HourlyForecast.from_dict(e) for e in hourly_forecasts],
        )

        # Exit if weather_forecast does not contain a `solar_irradiance` field.
        if not weather_forecast.forecasts or weather_forecast.forecasts[0].solar_irradiance is None:
            raise RemehaIncorrectServiceCall(
                translation_domain=DOMAIN, translation_key="auto_schedule_no_solar_irradiance"
            )

        schedule: ZoneSchedule = ZoneSchedule.generate(
            weather_forecast=weather_forecast,
            pv_system=_config_to_pv_config(self.config_entry),
            boiler_config=_config_to_boiler_config(self.config_entry),
            boiler_zone=dhw_zone,
            appliance_seasonal_mode=self.get_appliance().season_mode,
            schedule_id=HA_SCHEDULE_TO_REMEHA_SCHEDULE[
                self.config_entry.data[AUTO_SCHEDULE_SELECTED_SCHEDULE]
            ],
        )

        _LOGGER.debug("Schedule generated:\n\n%s\n\n, now pushing it to the appliance.", schedule)

        try:
            await self._api.async_write_variable(
                variable=WEEKDAY_TO_MODBUS_VARIABLE[schedule.day],
                value=schedule,
                offset=self._api.get_zone_register_offset(zone=dhw_zone)
                + self._api.get_schedule_register_offset(schedule=schedule.id),
            )
        except ModbusException as e:
            raise RemehaServiceException(
                translation_domain=DOMAIN, translation_key="auto_schedule_modbus_error"
            ) from e
        except ValueError as e:
            raise RemehaServiceException(
                translation_domain=DOMAIN, translation_key="auto_schedule_value_error"
            ) from e

    async def async_shutdown(self):
        """Shutdown this coordinator."""

        await self._api.async_close()
        return await super().async_shutdown()
