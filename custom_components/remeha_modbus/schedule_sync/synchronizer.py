"""Implementation of schedule synchronization."""

import logging
from datetime import datetime, time, timedelta
from enum import StrEnum
from typing import Final, TypedDict
from uuid import UUID, uuid4

from homeassistant.components.climate.const import DOMAIN as ClimateDomain
from homeassistant.components.climate.const import PRESET_COMFORT, PRESET_ECO, PRESET_NONE
from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.const import STATE_OFF
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    Event,
    EventStateChangedData,
    async_track_state_added_domain,
    async_track_state_change_event,
    async_track_state_removed_domain,
)
from pydantic import TypeAdapter, ValidationError

from custom_components.remeha_modbus.api import (
    ClimateZone,
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    WaitingListEntry,
    ZoneSchedule,
)
from custom_components.remeha_modbus.const import (
    DOMAIN,
    IMPORT_SCHEDULE_REQUIRED_DOMAIN_NAME,
    IMPORT_SCHEDULE_REQUIRED_SERVICES,
    SWITCH_EXECUTE_SCHEDULING_ACTIONS,
    ClimateZoneScheduleId,
    SchedulerAction,
    SchedulerCondition,
    SchedulerSchedule,
    SchedulerState,
    SchedulerStateAction,
    SchedulerTimeslot,
    Weekday,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import RequiredServiceMissing
from custom_components.remeha_modbus.helpers.validation import require_not_none

_LOGGER = logging.getLogger(__name__)

WEEKDAY_TO_SHORT_DESC: Final[dict[Weekday, str]] = {
    Weekday.MONDAY: "mon",
    Weekday.TUESDAY: "tue",
    Weekday.WEDNESDAY: "wed",
    Weekday.THURSDAY: "thu",
    Weekday.FRIDAY: "fri",
    Weekday.SATURDAY: "sat",
    Weekday.SUNDAY: "sun",
}

SHORT_DESC_TO_WEEKDAY: Final[dict[str, Weekday]] = {
    WEEKDAY_TO_SHORT_DESC[day]: day for day in Weekday
}

SWITCH_ADDED_LISTENER: Final[str] = "switch_added"
SWITCH_REMOVED_LISTENER: Final[str] = "switch_removed"

SCHEDULER_TAG_PREFIX: Final[str] = f"{DOMAIN}_"


def empty_fn() -> None:
    """Empty no-op function."""


def to_scheduler_state(state: State) -> SchedulerState:
    """Convert the given state to a `SchedulerState` instance.

    Args:
        state (State): The state to convert.

    Returns:
        The scheduler state.

    Raises:
        ValidationError: if `state` cannot be converted to a `SchedulerState`.

    """

    validator = TypeAdapter(SchedulerState)
    return validator.validate_python(dict(state.as_dict()))


class ZoneScheduleId(TypedDict):
    """The unique identifier of a `ZoneSchedule`."""

    zone_id: int
    """The id of the `ClimateZone` containing the zone schedule."""

    schedule_id: ClimateZoneScheduleId
    """The id of the `ZoneSchedule` within the containing climate zone."""


class ServiceOperation(StrEnum):
    """Enumerate the required service operation to store a schedule."""

    ADD = "add"
    """The schedule does not exist in the service, so it must be added."""
    EDIT = "edit"
    """The schedule already exists in the service, so it must be edited."""


class ScheduleSynchronizer:
    """Synchronization of schedules between this integration and other HA scheduling services.

    An instance of this class is stored in `config_entry.runtime_data`. This scope is required
    because the synchronizer keeps track of the event listeners for schedules.
    """

    def __init__(self, hass: HomeAssistant, coordinator: RemehaUpdateCoordinator):
        """Create a new synchronizer instance."""

        self._hass: HomeAssistant = hass
        self._coordinator: RemehaUpdateCoordinator = coordinator

        @callback
        def _switch_added(event: Event[EventStateChangedData]):
            self._hass.loop.create_task(self._async_event_switch_added(event=event))

        @callback
        def _switch_removed(event: Event[EventStateChangedData]):
            self._hass.loop.create_task(self._async_event_switch_removed(event=event))

        # Listen to added and removed entities by the scheduler integration.
        self._subscriptions: dict[str, CALLBACK_TYPE] = {
            SWITCH_ADDED_LISTENER: async_track_state_added_domain(
                hass=self._hass, domains=SwitchDomain, action=_switch_added
            ),
            SWITCH_REMOVED_LISTENER: async_track_state_removed_domain(
                hass=self._hass, domains=SwitchDomain, action=_switch_removed
            ),
        }

    def _refers_to_owned_climate_entity(self, state: SchedulerState) -> bool:
        """Determine whether the given entity state contains an action climate entity that is owned by this integration."""
        action_entities: list[str] = state["attributes"]["entities"]
        first_entity: str | None = action_entities[0] if action_entities else None
        first_entity_state: State | None = self._hass.states.get(entity_id=first_entity)

        return (
            first_entity_state is not None
            and first_entity_state.domain == ClimateDomain
            and self._coordinator.is_remeha_modbus_entity(first_entity_state.entity_id)
        )

    async def _async_event_switch_updated(self, event: Event[EventStateChangedData]) -> None:
        # The only way we could get here was through a state-change listener on a single entity.
        # Therefore, assume the state in the event is of a `scheduler.schedule`,
        # otherwise the export method will raise a `ValueError`.

        state: SchedulerState = to_scheduler_state(state=event.data["new_state"])
        if self._refers_to_owned_climate_entity(state):
            await self.async_export_schedule(state=state)
        else:
            _LOGGER.debug(
                "Provided SchedulerState does not refer to a climate entity owned by remeha_modbus."
            )

    async def _async_event_switch_added(self, event: Event[EventStateChangedData]) -> None:
        """Handle a newly added `scheduler.schedule`.

        If this schedule is newly created from the scheduler UI, export it to the modbus interface.
        Otherwise, it just needs to be linked to the correct climate zone schedule and is expected
        to be on the waiting list.
        """

        def _get_waiting_list_tag(scheduler_state: SchedulerState) -> UUID | None:
            tags: list[str] = scheduler_state["attributes"].get("tags", [])
            for tag in tags:
                if tag.startswith(SCHEDULER_TAG_PREFIX):
                    return UUID(tag.removeprefix(SCHEDULER_TAG_PREFIX))

            return None

        try:
            state: SchedulerState = to_scheduler_state(state=event.data["new_state"])

            if self._refers_to_owned_climate_entity(state):
                # Only continue if the linked entity is a remeha_modbus climate entity.
                entity_id: str = event.data["entity_id"]

                # Subscribe to entity changes if not already listening to them.
                @callback
                def _switch_updated(update_event: Event[EventStateChangedData]):
                    self._hass.loop.create_task(
                        self._async_event_switch_updated(event=update_event)
                    )

                if entity_id not in self._subscriptions:
                    self._subscriptions[entity_id] = async_track_state_change_event(
                        hass=self._hass, entity_ids=entity_id, action=_switch_updated
                    )

                # Check if this schedule is on the waiting list to be linked to a ZoneSchedule
                waiting_list_tag: UUID | None = _get_waiting_list_tag(scheduler_state=state)
                waiting_link: WaitingListEntry | None = (
                    self._coordinator.pop_from_linking_waiting_list(uuid=waiting_list_tag)
                    if waiting_list_tag is not None
                    else None
                )

                if waiting_link is not None:
                    # If so, just store that link.
                    await self._coordinator.async_link_scheduler_entity(
                        zone_id=waiting_link.zone_id,
                        schedule_id=waiting_link.schedule_id,
                        entity_id=entity_id,
                    )
                else:
                    # Otherwise export the schedule to the modbus interface.
                    await self.async_export_schedule(state=state)
            else:
                _LOGGER.debug(
                    "Ignoring scheduler.schedule [%s] since its 1st action entity is no Remeha Modbus climate entity.",
                    event.data["entity_id"],
                )

        except ValidationError as e:
            _LOGGER.debug(
                "Ignoring added switch[%s] since it doesn't appear to be a scheduler.schedule.",
                event.data["entity_id"],
                exc_info=e,
            )

    async def _async_event_switch_removed(self, event: Event[EventStateChangedData]) -> None:
        entity_id: str = event.data["entity_id"]

        # Stop listening for updates of this entity.
        if entity_id in self._subscriptions:
            _LOGGER.info("Schedule [%s] removed, unsubscribing from its update events.", entity_id)
            unsubscribe = self._subscriptions.pop(entity_id)
            unsubscribe()

        # And unlink if linked.
        link = await self._coordinator.async_get_linked_climate_schedule_identifiers(
            scheduler_entity_id=entity_id
        )
        if link is not None:
            _LOGGER.info(
                "Schedule [%s] removed, unlinking from climate zone schedule(zone_id=%d, schedule_id=%d)",
                entity_id,
                link.zone_id,
                link.schedule_id,
            )
            await self._coordinator.async_unlink_climate_schedule(
                zone_id=link.zone_id, schedule_id=link.schedule_id
            )

    def _to_schedule_name(self, schedule: ZoneSchedule) -> str:
        return f"zone_{schedule.zone_id}_{schedule.id.name.lower()}_{schedule.day.name.lower()}"

    def _get_durations(self, schedule: ZoneSchedule):
        time_slots = schedule.time_slots
        for idx, ts in enumerate(time_slots):
            if idx == len(time_slots) - 1:
                # Calculate the time delta until tomorrow.
                yield ts, timedelta(hours=24 - ts.switch_time.hour)
            else:
                next_ts: Timeslot = time_slots[idx + 1]
                yield ts, timedelta(hours=next_ts.switch_time.hour - ts.switch_time.hour)

    def _to_preset_mode(self, setpoint_type: TimeslotSetpointType) -> str:
        if setpoint_type is TimeslotSetpointType.ECO:
            return PRESET_ECO
        if setpoint_type is TimeslotSetpointType.COMFORT:
            return PRESET_COMFORT

        return PRESET_NONE

    async def _to_scheduler_schedule(
        self,
        schedule: ZoneSchedule,
        operation: ServiceOperation,
        linked_scheduler_entity: str | None = None,
        linking_tag: UUID | None = None,
    ) -> SchedulerSchedule:
        durations: dict[Timeslot, timedelta] = dict(self._get_durations(schedule=schedule))
        zone: ClimateZone = self._coordinator.get_climate(id=schedule.zone_id)
        climate_entity = next(
            iter(
                [
                    state
                    for state in self._hass.states.async_all(domain_filter="climate")
                    if state.attributes.get("zone_id") == zone.id
                ]
            )
        )

        data = SchedulerSchedule(
            weekdays=[WEEKDAY_TO_SHORT_DESC[schedule.day]],
            repeat_type="repeat",
            timeslots=[
                SchedulerTimeslot(
                    start=ts.switch_time.strftime("%H:%M:%S"),
                    stop=time(
                        hour=int((ts.switch_time.hour + (durations[ts].seconds / 3600)) % 24)
                    ).strftime("%H:%M:%S"),
                    conditions=[
                        SchedulerCondition(
                            entity_id=f"switch.{SWITCH_EXECUTE_SCHEDULING_ACTIONS}",
                            value="on",
                            match_type="is",
                            attribute="state",
                        )
                    ],
                    condition_type="and",
                    actions=[
                        SchedulerAction(
                            entity_id=climate_entity.entity_id,
                            service="climate.set_preset_mode",
                            service_data={
                                "preset_mode": self._to_preset_mode(setpoint_type=ts.setpoint_type)
                            },
                        )
                    ],
                )
                for ts in schedule.time_slots
            ],
        )

        if operation == ServiceOperation.EDIT:
            data["entity_id"] = linked_scheduler_entity
        elif operation == ServiceOperation.ADD:
            # Name must only be set when creating a new schedule.
            data["name"] = self._to_schedule_name(schedule=schedule)

            # When creating a new schedule, a unique tag is added so it can be identified
            # when the new-schedule-event is received. It can then be linked to the correct modbus schedule.
            # This tag can be removed afterward.
            data["tags"] = [f"{SCHEDULER_TAG_PREFIX}{linking_tag}"]

        return data

    async def _async_to_linked_zone_schedule(
        self, state: SchedulerState, zone_id: int, schedule_id: ClimateZoneScheduleId
    ) -> ZoneSchedule:
        """Create a `ZoneSchedule` based on the given entity state.

        The given state must have a domain of `switch` and adhere to the state format
        of a `scheduler.schedule` instance.

        Args:
            state (SchedulerState): The scheduler state.
            zone_id (int): The id of the linked `ClimateZone`.
            schedule_id (ClimateZoneScheduleId): The id of the schedule in the `ClimateZone`.

        Returns:
            ZoneSchedule: The zone schedule.

        Raises:
            ValueError: if the state cannot be parsed to a ZoneSchedule.

        """

        def _to_time_slot(idx: int, time_slot: str) -> Timeslot:
            parts = [s.strip() for s in time_slot.split("-")]
            if len(parts) != 2:
                raise ValueError(
                    "Cannot parse timeslot string [%s] in exactly two parts.", time_slot
                )

            related_action: SchedulerStateAction = state["attributes"]["actions"][idx]
            if (
                related_action["service"] == "climate.set_preset_mode"
                and "preset_mode" in related_action["data"]
            ):
                return Timeslot(
                    setpoint_type=TimeslotSetpointType[
                        related_action["data"]["preset_mode"].upper()
                    ],
                    activity=TimeslotActivity.DHW,
                    switch_time=datetime.strptime(parts[0], "%H:%M:%S").time(),
                )

            raise ValueError("Invalid SchedulerStateAction")

        if len(state["attributes"]["weekdays"]) == 1:
            weekday: Weekday = SHORT_DESC_TO_WEEKDAY[state["attributes"]["weekdays"][0]]
            time_slots: list[Timeslot] = [
                _to_time_slot(idx=idx, time_slot=time_slot)
                for (idx, time_slot) in enumerate(state["attributes"]["timeslots"])
            ]

            return ZoneSchedule(id=schedule_id, zone_id=zone_id, day=weekday, time_slots=time_slots)

        raise ValueError(
            "Cannot parse ZoneSchedule from SchedulerState: require exactly 1 weekdays, got %d",
            len(state["attributes"]["weekdays"]),
        )

    async def _async_add_scheduler_schedule(self, schedule: ZoneSchedule):
        tag: UUID = uuid4()
        operation: ServiceOperation = ServiceOperation.ADD
        data: SchedulerSchedule = await self._to_scheduler_schedule(
            schedule=schedule, operation=operation, linking_tag=tag
        )

        # Add linking information to the waiting list.
        # This info is used to link the schedules when a schedule-added event is received.
        self._coordinator.enqueue_for_linking(
            uuid=tag, zone_id=schedule.zone_id, schedule_id=schedule.id
        )

        await self._hass.services.async_call(
            domain=IMPORT_SCHEDULE_REQUIRED_DOMAIN_NAME,
            service=str(operation),
            blocking=False,
            return_response=False,
            service_data=data,
        )

    async def _async_update_scheduler_schedule(self, schedule: ZoneSchedule, scheduler_entity: str):
        operation = ServiceOperation.EDIT
        data: SchedulerSchedule = await self._to_scheduler_schedule(
            schedule=schedule, operation=operation, linked_scheduler_entity=scheduler_entity
        )

        await self._hass.services.async_call(
            domain=IMPORT_SCHEDULE_REQUIRED_DOMAIN_NAME,
            service=str(operation),
            blocking=False,
            return_response=False,
            service_data=data,
        )

    async def async_refresh_subscriptions(self):
        """Remove all subscriptions to `scheduler.schedule` entity updates and resubscribe to all currently linked entities."""

        retainers: set[str] = {SWITCH_ADDED_LISTENER, SWITCH_REMOVED_LISTENER}
        if self._subscriptions.keys() != retainers:
            for key in self._subscriptions.keys() ^ retainers:
                unsubscribe = self._subscriptions[key]
                unsubscribe()

        @callback
        def _switch_updated(event: Event[EventStateChangedData]):
            self._hass.loop.create_task(self._async_event_switch_updated(event=event))

        refreshed: dict[str, CALLBACK_TYPE] = {key: self._subscriptions[key] for key in retainers}
        for link in await self._coordinator.async_get_scheduler_links():
            refreshed[link.scheduler_entity_id] = async_track_state_change_event(
                hass=self._hass, entity_ids=link.scheduler_entity_id, action=_switch_updated
            )

        self._subscriptions = refreshed

    async def async_import_schedule(self, schedule: ZoneSchedule):
        """Import the given modbus schedule into the scheduler integration.

        If the schedule already exists, it is updated. Otherwise, it is created.
        Imported schedules are kept in sync with the modbus interface.

        Notes:
        * abc

        Args:
          schedule (ZoneSchedule): The schedule to import.

        """

        services: dict | None = self._hass.services.async_services_for_domain(
            IMPORT_SCHEDULE_REQUIRED_DOMAIN_NAME
        )

        if not services or not services.keys() & IMPORT_SCHEDULE_REQUIRED_SERVICES:
            raise RequiredServiceMissing(
                translation_domain=DOMAIN, translation_key="import_schedule_missing_services"
            )

        linked_scheduler_entity: (
            str | None
        ) = await self._coordinator.async_get_linked_scheduler_entity(
            zone_id=schedule.zone_id, schedule_id=schedule.id
        )

        if linked_scheduler_entity is not None:
            await self._async_update_scheduler_schedule(
                schedule=schedule, scheduler_entity=linked_scheduler_entity
            )
        else:
            await self._async_add_scheduler_schedule(schedule=schedule)

    async def async_export_schedule(self, state: SchedulerState):
        """Export the `scheduler.schedule` with the given state to the modbus interface.

        A schedule is only exported if its state is `on` and if it doesn't equal the current
        cached version of the modbus schedule.

        Notes:
        * If the `scheduler.schedule` is not yet linked to a `ZoneSchedule`, a link is created between it
          and the currently selected schedule of the climate entity mentioned in `schedule_state.data['actions']`

        Args:
            state (SchedulerState): The `State` of the schedule.

        Raises:
            ValueError if the scheduler entity is not linked to a climate entity from this integration.

        """

        if state["state"] == STATE_OFF:
            _LOGGER.debug(
                "Not exporting disabled schedule. It will be exported (again) when it is turned on."
            )
            return

        weekday: str = state["attributes"]["weekdays"][0]
        if len(state["attributes"]["weekdays"]) > 1:
            _LOGGER.warning(
                "Schedule [%s] is active for multiple weekdays, which a Remeha schedule does not support. Using only the first day (%s)",
                state["entity_id"],
                weekday,
            )

        scheduler_entity_id: str = state["entity_id"]

        # The scheduler.schedule and the climate schedule must be linked
        link = require_not_none(
            await self._coordinator.async_get_linked_climate_schedule_identifiers(
                scheduler_entity_id=scheduler_entity_id
            )
        )

        # Retrieve the zone_id from the current climate entity state.
        climate_zone: ClimateZone = self._coordinator.get_climate(id=link.zone_id)

        # Bail out if zone is not DHW (not yet supported)
        if not climate_zone.is_domestic_hot_water():
            raise ValueError("Exporting a non-DHW climate schedule is not yet supported.")

        current_schedule: ZoneSchedule = None
        if link.schedule_id == climate_zone.selected_schedule:
            _LOGGER.debug(
                "Schedule [%s] is linked to the current zone schedule.", scheduler_entity_id
            )
            current_schedule = climate_zone.current_schedule.get(SHORT_DESC_TO_WEEKDAY[weekday])
        else:
            _LOGGER.debug(
                "Schedule [%s] is not linked to climate_zone.current_schedule; exporting and linking to climate schedule [%s].",
                scheduler_entity_id,
                link.schedule_id.name,
            )

        updated_schedule: ZoneSchedule = await self._async_to_linked_zone_schedule(
            state=state, zone_id=link.zone_id, schedule_id=link.schedule_id
        )
        if current_schedule is None or updated_schedule != current_schedule:
            # Only update if schedule changed.
            # This also breaks the import/export perpetual cycle. Otherwise, in the case described
            # below, a never-ending cycle of an import followed by an export will occur.
            # 1. Schedule is updated in the Remeha Home app
            # 2. Next coordinator update gets new schedule from modbus
            # 3. Schedule gets imported to the scheduler.schedule
            # 4. update-schedule-listener receives update event and calls `async_export_schedule`
            # 5. GOTO 1
            _LOGGER.info(
                "Exporting scheduler.schedule[%s] to modbus interface.", scheduler_entity_id
            )
            await self._coordinator.async_write_schedule(schedule=updated_schedule)
            await self._coordinator.async_link_scheduler_entity(
                zone_id=link.zone_id,
                schedule_id=link.schedule_id,
                entity_id=scheduler_entity_id,
            )

            _LOGGER.debug(
                "scheduler.schedule[%s] exported and linked to modbus schedule.",
                scheduler_entity_id,
            )
        else:
            _LOGGER.debug("Not exporting schedule since it has not changed.")
