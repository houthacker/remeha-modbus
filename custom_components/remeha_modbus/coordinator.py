"""Coordinator for fetching modbus data of Remeha devices."""

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from dateutil.parser import parse
from homeassistant.components.switch.const import DOMAIN as SwitchPlatform
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus import ModbusException

from custom_components.remeha_modbus.api import (
    DeviceInstance,
    RemehaApi,
)
from custom_components.remeha_modbus.api.appliance import Appliance
from custom_components.remeha_modbus.api.climate_zone import ClimateZone, ZoneSchedule
from custom_components.remeha_modbus.api.schedule import HourlyForecast, WeatherForecast
from custom_components.remeha_modbus.api.store import RemehaModbusStorage, WaitingListEntry
from custom_components.remeha_modbus.blend.scheduler.const import SchedulerLinkView, ZoneScheduleUID
from custom_components.remeha_modbus.blend.scheduler.helpers import get_updated_dhw_schedules
from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SELECTED_SCHEDULE,
    DHW_BOILER_CONFIG_SECTION,
    DHW_BOILER_ENERGY_LABEL,
    DHW_BOILER_HEAT_LOSS_RATE,
    DHW_BOILER_VOLUME,
    DOMAIN,
    HA_SCHEDULE_TO_REMEHA_SCHEDULE,
    ISSUE_DISCOVERY_TABLE_CORRUPTED,
    ISSUE_DISCOVERY_TABLE_CORRUPTED_LEARN_MORE_URL,
    ISSUE_INVALID_ZONE_SCHEDULE,
    ISSUE_TRACKER_URL,
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
    ClimateZoneScheduleId,
    MetaRegisters,
    ModbusVariableDescription,
    PVSystem,
    PVSystemOrientation,
    UnsubscribeCallback,
)
from custom_components.remeha_modbus.errors import (
    DiscoveryTableCorruptedError,
    IncorrectEntityPlatformError,
    InvalidZoneSchedule,
    RemehaIncorrectServiceCall,
    RemehaServiceError,
)
from custom_components.remeha_modbus.helpers.entities import is_scheduler_switch

_LOGGER = logging.getLogger(__name__)


def _config_to_boiler_config(config: ConfigEntry) -> BoilerConfiguration:
    section = config.data[DHW_BOILER_CONFIG_SECTION]

    return BoilerConfiguration(
        volume=section.get(DHW_BOILER_VOLUME, None),
        heat_loss_rate=section.get(DHW_BOILER_HEAT_LOSS_RATE, None),
        energy_label=(
            BoilerEnergyLabel(section[DHW_BOILER_ENERGY_LABEL])
            if DHW_BOILER_ENERGY_LABEL in section and section[DHW_BOILER_ENERGY_LABEL] is not None
            else None
        ),
    )


def _config_to_pv_config(config: ConfigEntry) -> PVSystem:
    section = config.data[PV_CONFIG_SECTION]

    return PVSystem(
        nominal_power=section[PV_NOMINAL_POWER_WP],
        orientation=PVSystemOrientation(section[PV_ORIENTATION]),
        tilt=section.get(PV_TILT, None),
        annual_efficiency_decrease=section.get(PV_ANNUAL_EFFICIENCY_DECREASE, None),
        installation_date=(
            parse(section[PV_INSTALLATION_DATE]).date() if PV_INSTALLATION_DATE in section else None
        ),
    )


class Subscriber[T]:
    """An internal class to store event subscribers in."""

    _callback: Callable[[T], None]
    """The original callback function."""

    has_been_called: bool
    """Whether this subscriber has been called at least once."""

    def __init__(self, fn: Callable[[T], None]):
        """Create a new subscriber."""

        self._callback = fn
        self.has_been_called = False

    @callback
    async def async_notify(self, arg: T) -> None:
        """Notify the subscriber of an event."""

        self._callback(arg)
        self.has_been_called = True


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

        # Update every 30 seconds. This is not user-configurable, since it depends on the amount of
        # configured (hard-coded) modbus entities
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            always_update=False,
            config_entry=config_entry,
        )

        self._store: RemehaModbusStorage = store
        self._api: RemehaApi = api
        self._device_instances: dict[int, DeviceInstance] = {}

        # This list is populated by the added_to_hass() callback of the climate entities.
        self._climate_entity_ids: list[str] = []

        self._schedule_subscribers: set[Subscriber[ZoneSchedule]] = set()

    def _is_before_first_update(self) -> bool:
        return not self.data or "climates" not in self.data

    async def _async_setup(self):
        try:
            self._device_instances = {
                instance.id: instance for instance in await self._api.async_read_device_instances()
            }
        except ModbusException as ex:
            raise UpdateFailed("Error while communicating with modbus device.") from ex

        await self._store.async_load()

    async def _async_update_data(
        self,
    ) -> dict[
        str, Appliance | dict[int, ClimateZone] | bool | dict[ModbusVariableDescription, Any]
    ]:
        try:
            before_first_update = self._is_before_first_update()
            zones: list[ClimateZone] = []
            is_cooling_forced: bool = await self._api.async_is_cooling_forced
            appliance: Appliance = await self._api.async_read_appliance()
            sensors = await self._api.async_read_sensor_values(list(REMEHA_SENSORS.keys()))
            if before_first_update:
                zones = await self._api.async_read_zones()
            else:
                zones = [
                    await self._api.async_read_zone_update(zone)
                    for zone in list(self.data["climates"].values())
                ]

            # Fire an event for each updated ZoneSchedule, but only after the
            # initial refresh.
            # The reason for this is that any known listeners register themselves
            # only after HA has started. At that point, at least one update has been
            # executed causing both old_zones and new_zones to have a value.
            if not before_first_update:
                await self._async_fire_dhw_schedule_update_events(
                    old_zones=self.data["climates"],
                    new_zones={zone.id: zone for zone in zones},
                )

        except DiscoveryTableCorruptedError as ex:
            ir.async_create_issue(
                hass=self.hass,
                domain=DOMAIN,
                issue_domain=DOMAIN,
                issue_id=ISSUE_DISCOVERY_TABLE_CORRUPTED,
                is_fixable=True,
                is_persistent=False,
                learn_more_url=ISSUE_DISCOVERY_TABLE_CORRUPTED_LEARN_MORE_URL,
                severity=ir.IssueSeverity.ERROR,
                translation_key="discovery_table_corrupted",
            )
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed_discovery_table_corrupted"
            ) from ex
        except ModbusException as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_modbus_exception",
                translation_placeholders={"modbus_message": ex.string},
            ) from ex
        except InvalidZoneSchedule as ex:
            ir.async_create_issue(
                hass=self.hass,
                domain=DOMAIN,
                data={"zone_id": ex.zone, "schedule_id": ex.schedule_id.name.lower()},
                issue_domain=DOMAIN,
                issue_id=ISSUE_INVALID_ZONE_SCHEDULE,
                is_fixable=True,
                is_persistent=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="invalid_zone_schedule",
                translation_placeholders={"issue_tracker_url": ISSUE_TRACKER_URL},
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_invalid_zone_schedule",
                translation_placeholders={
                    "zone": str(ex.zone),
                    "selected_schedule": ex.schedule_id,
                },
            ) from ex

        return {
            "appliance": appliance,
            "climates": {zone.id: zone for zone in zones},
            "cooling_forced": is_cooling_forced,
            "sensors": sensors,
        }

    async def _async_fire_dhw_schedule_update_events(
        self, old_zones: dict[int, ClimateZone], new_zones: dict[int, ClimateZone]
    ) -> None:
        updated_schedules = get_updated_dhw_schedules(old=old_zones, new=new_zones)
        for subscriber in self._schedule_subscribers:
            # Subscribers that haven't been called before receive all zone schedules
            # while subscribers that do have been called before receive only updated
            # zone schedules.
            schedules = (
                updated_schedules
                if subscriber.has_been_called
                else [
                    schedule
                    for zone in new_zones.values()
                    if zone.is_domestic_hot_water()
                    for schedule in zone.current_schedule.values()
                    if schedule is not None
                ]
            )

            for schedule in schedules:
                await subscriber.async_notify(schedule)

    def track_zone_schedule_updates(
        self, callback: Callable[[ZoneSchedule], None]
    ) -> UnsubscribeCallback:
        """Register `callback` to be called when updated `ZoneSchedule`s are received from modbus.

        The `callback` is only called if the related zone is a DHW zone.
        Since they're internal events and not domain events, zone schedule updates do not trigger
        an HA event and therefore are not visible as such in `remeha_modbus` entity states.

        The rationale to not expose them as domain events is that the coordinator needs to know
        whether a subscriber has received these updates before to determine what update set to
        send to individual subscribers.

        Args:
            callback (Callable[[ZoneSchedule], None]): The callback to call. If the callback
            raises an exception during its execution, any subsequent callbacks are not executed.

        Returns:
            A zero-argument callable to unsubscribe from these updates. Calling it multiple times
            has no additional effect and does not raise an exception.

        """
        subscriber = Subscriber(callback)
        self._schedule_subscribers.add(subscriber)

        return lambda: (
            self._schedule_subscribers.remove(subscriber)
            if callback in self._schedule_subscribers
            else None
        )

    async def async_force_system_rediscovery(self):
        """Force the Remeha appliance to execute system discovery.

        This instructs the appliance to rebuild the discovery table(registers 128 - 199).

        Raises:
            `ModbusException` if writing the related modbus register fails.

        """

        await self._api.async_write_variable(
            variable=MetaRegisters.RESET_DISCOVERY_TABLE, value=0x5A
        )

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
            predicate (Callable[[DeviceInstance], bool]): The predicate to evaluate on all device instances. Defaults to `True`.

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

    def enqueue_for_linking(self, uuid: UUID, zone_schedule_uid: ZoneScheduleUID):
        """Store the given identifiers, preparing them for linking a `ZoneSchedule` to a `scheduler.schedule`.

        If an equal entry already exists, this method has no effect.

        Args:
            uuid (UUID): The unique identifier added to the list of tags in the `scheduler.schedule`.
            zone_schedule_uid (ZoneScheduleUID): The unique identification of the `ZoneSchedule`.

        """

        self._store.add_to_linking_waiting_list(uuid=uuid, zone_schedule_uid=zone_schedule_uid)

    def remove_from_linking_waiting_list(self, uuid: UUID) -> WaitingListEntry | None:
        """Pop the waiting identifiers with uuid `uuid` from the waiting list.

        Args:
            uuid (UUID): The uuid listed in the tags of the `scheduler.schedule`

        Returns:
            A tuple containing the requested identifiers to be linked, or `None` if no such item exists.

        """

        return self._store.remove_from_linking_waiting_list(uuid=uuid)

    def notify_of_modbus_sourced_update(self, entity_id: str):
        """Notify us that the next update of `entity_id` originates from modbus.

        Args:
            entity_id (str): The entity id from the `scheduler.schedule`.

        """

        # TODO Can this be replaced by an event source?
        self._store.notify_of_modbus_sourced_update(entity_id)

    def is_modbus_sourced_update(self, entity_id: str) -> bool:
        """Return whether an update of `entity_id` is expected.

        Args:
            entity_id (str): The entity id from the `scheduler.schedule`

        Returns:
            `True` if an update is expected, `False` otherwise.

        """

        return self._store.is_modbus_sourced_update(entity_id)

    async def async_upsert_scheduler_link(
        self, uid: ZoneScheduleUID, scheduler_entity_id: str
    ) -> None:
        """Create or update a scheduler link.

        Args:
            uid (ZoneScheduleUID): The unique identifier of the zone schedule.
            scheduler_entity_id (str): The `entity_id` of the `scheduler.schedule`.

        Raises:
            `IncorrectEntityPlatformError` if `scheduler_entity_id` does not refer to
            an entity of `scheduler.schedule`.

        """

        if not is_scheduler_switch(self.hass, scheduler_entity_id):
            raise IncorrectEntityPlatformError(
                translation_domain=DOMAIN,
                translation_key="incorrect_entity_platform",
                translation_placeholders={
                    "entity_id": scheduler_entity_id,
                    "expected_platform": SwitchPlatform,
                    "expected_component": "scheduler",
                },
            )

        await self._store.async_upsert_schedule_attributes(uid, scheduler_entity_id)

    async def async_get_scheduler_links(self) -> list[SchedulerLinkView]:
        """Return a list of all current scheduler links."""
        return [
            SchedulerLinkView(
                zone_schedule_uid=ZoneScheduleUID(
                    zone_id=entry.zone_id,
                    schedule_id=ClimateZoneScheduleId(entry.schedule_id),
                    weekday=entry.weekday,
                ),
                scheduler_entity_id=entry.schedule_entity_id,
            )
            for entry in await self._store.async_get_all()
        ]

    async def async_get_linked_zone_schedule_uid(
        self, schedule_entity_id: str
    ) -> ZoneScheduleUID | None:
        """Get the unique identification of the `ZoneSchedule` that is linked to the given `schedule_entity_id`.

        Args:
            schedule_entity_id (str): The entity id of the linked `scheduler.schedule`.

        Returns:
            ZoneScheduleUID | None: The linked zone schedule identification, or `None` if no such link exists.

        """

        entry = await self._store.async_get_attributes_by_entity_id(schedule_entity_id)
        return (
            ZoneScheduleUID(
                zone_id=entry.zone_id,
                schedule_id=ClimateZoneScheduleId(entry.schedule_id),
                weekday=entry.weekday,
            )
            if entry is not None
            else None
        )

    async def async_get_linked_scheduler_entity(self, uid: ZoneScheduleUID) -> str | None:
        """Get the entity id of the `scheduler.schedule` that is linked to the `ZoneSchedule` having the given id values.

        Args:
            uid: The unique identity of the zone schedule.

        Returns:
            str | None: The entity id of the linked `scheduler.schedule`, or `None` if no such entity exists.

        """

        entry = await self._store.async_get_attributes_by_zone(uid=uid)
        return entry.schedule_entity_id if entry else None

    async def async_write_schedule(self, schedule: ZoneSchedule):
        """Write the given schedule to the modbus interface.

        If the schedule is written successfully, the current state is also
        updated to prevent zone schedule update cycles.

        Args:
            schedule (ZoneSchedule): The schedule to write.

        Raises:
            ModbusException: if writing `schedule` to the modbus interface fails.

        """

        await self._api.async_write_variable(
            variable=WEEKDAY_TO_MODBUS_VARIABLE[schedule.day],
            value=schedule,
            offset=self._api.get_zone_register_offset(schedule.zone_id)
            + self._api.get_schedule_register_offset(schedule.id),
        )

        # Update the current schedule state if the updated schedule
        # is the current schedule. Otherwise no update of current state
        # necessary since we only store the schedules of the selected schedule.
        # Before the first update, data["climates"] doesn't exist yet.
        if not self._is_before_first_update() and schedule.zone_id in self.data["climates"]:
            zone: ClimateZone = self.data["climates"][schedule.zone_id]

            if zone.selected_schedule == schedule.id:
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
            pv_system=_config_to_pv_config(cast(ConfigEntry[Any], self.config_entry)),
            boiler_config=_config_to_boiler_config(cast(ConfigEntry[Any], self.config_entry)),
            boiler_zone=dhw_zone,
            appliance_seasonal_mode=self.get_appliance().season_mode,
            schedule_id=HA_SCHEDULE_TO_REMEHA_SCHEDULE[
                cast(ConfigEntry[Any], self.config_entry).data[AUTO_SCHEDULE_SELECTED_SCHEDULE]
            ],
        )

        _LOGGER.debug("Schedule generated:\n\n%s\n\n, now pushing it to the appliance.", schedule)

        try:
            await self.async_write_schedule(schedule)
        except ModbusException as e:
            raise RemehaServiceError(
                translation_domain=DOMAIN, translation_key="auto_schedule_modbus_error"
            ) from e
        except ValueError as e:
            raise RemehaServiceError(
                translation_domain=DOMAIN, translation_key="auto_schedule_value_error"
            ) from e

    async def async_shutdown(self):
        """Shutdown this coordinator."""

        await self._api.async_close()
        return await super().async_shutdown()
