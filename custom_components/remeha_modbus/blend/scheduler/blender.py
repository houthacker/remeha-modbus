"""Module for synchronization between a `scheduler.schedule` and a `remeha_modbus.ZoneSchedule`."""

import logging
from enum import Enum

from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from pydantic import ValidationError

from custom_components.remeha_modbus.blend import Blender
from custom_components.remeha_modbus.blend.scheduler.scenarios import (
    ModbusScheduleUpdated,
    ScheduleCreated,
)
from custom_components.remeha_modbus.const import SchedulerState
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

from .event_dispatcher import EventDispatcher, UnsubscribeCallback, ZoneScheduleUpdatedData
from .helpers import links_exclusively_to_remeha_climate, to_scheduler_state

_LOGGER = logging.getLogger(__name__)


class BlenderState(Enum):
    """Enumerate the states a `Blender` can be in."""

    INITIAL = 1
    """The initial state, just after the blender has been created."""

    STARTING = 2
    """The `Blender` is subscribing to relevant events and must not be disturbed."""

    STARTED = 3
    """The `Blender` has successfully subscribed to relevant events and is running."""

    STOPPING = 4
    """The `Blender` is unsubscribing from all events and must not be disturbed."""

    STOPPED = 5
    """The `Blender` has unsubscribed from all relevant events and will not execute any scenarios."""


class SchedulerBlender(Blender):
    """The `Blender` runs the required scenarios to integrate between the `remeha_modbus` and `scheduler` schedules.

    In general, the schedule entities from the `scheduler` integration live in the `switch` domain, whereas schedules
    from _this_ integration are `ZoneSchedule` objects in a `ClimateZone`.

    The following scenario's are supported:
    1. A new schedule is created in the `scheduler` integration, and is exclusively linked to a climate
          entity from `remeha_modbus`.
    2. A linked `scheduler.schedule` is updated. The link must be exclusive and need not
          exist before the update.
    3. A linked `scheduler.schedule` is removed.
    4. A `remeha_modbus` schedule is updated through an external source (e.g. from the Remeha Home app).
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: RemehaUpdateCoordinator, dispatcher: EventDispatcher
    ):
        """Create a new `Blender` instance.

        Args:
            hass (HomeAssistant): The current Home Assistant instance.
            coordinator (RemehaUpdateCoordinator): The coordinator required to retrieve `ClimateZone` instances.
            dispatcher (EventDispatcher): The dispatcher to subscribe to for entity events.

        """

        self._hass: HomeAssistant = hass
        self._coordinator: RemehaUpdateCoordinator = coordinator
        self._dispatcher: EventDispatcher = dispatcher
        self._state: BlenderState = BlenderState.INITIAL

        self._subscriptions: list[UnsubscribeCallback] = []

    def _ready_for_scenario_execution(self) -> bool:
        """Return whether a scenario can be executed according to the current blender state."""

        return self._state is BlenderState.STARTED

    def _scheduler_entity_added(self, event: Event[EventStateChangedData]) -> None:
        """Handle a new scheduler.schedule.

        Args:
            event (Event[EventStateChangedData]): The event containing the data of the new schedule.

        """
        if self._ready_for_scenario_execution():
            try:
                schedule: SchedulerState = to_scheduler_state(state=event.data["new_state"])
                if links_exclusively_to_remeha_climate(hass=self._hass, scheduler_state=schedule):
                    scenario = ScheduleCreated(
                        hass=self._hass, schedule=schedule, coordinator=self._coordinator
                    )

                    # Execute the scenario in a separate task since it requires I/O.
                    self._coordinator.config_entry.async_create_task(
                        self._hass, scenario.async_execute()
                    )
                else:
                    _LOGGER.warning(
                        "'%s' entity %s does not link exclusively to a remeha_modbus climate; ignoring its changes.",
                        SwitchDomain,
                        event.data["entity_id"],
                    )
            except ValidationError as e:
                _LOGGER.warning(
                    "Scheduler entity %s cannot be converted to a SchedulerState",
                    event.data["entity_id"],
                    exc_info=e,
                )

                # return
        else:
            _LOGGER.debug(
                "Ignoring event (type=%s, entity_id=%s) because current blender state %s prevents us from handling it.",
                event.event_type,
                event.data["entity_id"],
                self._state.name,
            )

    def _zone_schedule_updated(self, event: Event[ZoneScheduleUpdatedData]) -> None:
        """Handle a modbus `ZoneSchedule` update.

        Args:
            event (Event[ZoneScheduleUpdatedData]): The event containing the updated zone schedule.

        """

        schedule = event.data["schedule"]
        if self._ready_for_scenario_execution():
            scenario = ModbusScheduleUpdated(
                hass=self._hass, coordinator=self._coordinator, schedule=schedule
            )

            # Execute the scenario in a separate task since it requires I/O.
            self._coordinator.config_entry.async_create_task(self._hass, scenario.async_execute())
        else:
            _LOGGER.debug(
                "Ignoring ZoneSchedule-update event (zone_id=%d, schedule_id=%d, day=%s) because current blender state %s\
                    prevents us from handling it.",
                schedule.zone_id,
                schedule.id.value,
                schedule.day.name,
                self._state.name,
            )

    @property
    def state(self) -> BlenderState:
        """Return the current state of the Blender."""
        return self._state

    def blend(self):
        """Start listening for relevant events to enable executing the defined scenarios.

        If already started, this method has no effect. If stopped, this instance re-subscribes
        to the events.
        """

        if self._state in [BlenderState.INITIAL, BlenderState.STOPPED]:
            _LOGGER.debug("Going to subscribe to relevant scheduler- and remeha_modbus events.")
            self._state = BlenderState.STARTING

            # Subscribe to state changes required to blend in.
            self._subscriptions = [
                self._dispatcher.subscribe_to_added_entities(
                    domain=SwitchDomain, listener=self._scheduler_entity_added
                ),
                self._dispatcher.subscribe_to_zone_schedule_updates(
                    listener=self._zone_schedule_updated
                ),
            ]

            # TODO Create an initial scenario because the blender
            # is started _after_ the first coordinator refresh.

            self._state = BlenderState.STARTED
            _LOGGER.debug(
                "Successfully subscribed to relevant scheduler- and remeha_modbus events."
            )
        else:
            _LOGGER.debug(
                "Not going to (re)subscribe to events since we're in an unsupported state (%s) to do so.",
                self._state.name,
            )

    def unblend(self):
        """Stop listening for all events and stop executing scenarios."""

        if self._state is BlenderState.STARTED:
            _LOGGER.debug("Going to unsubscribe from all entity- and domain events.")
            self._state = BlenderState.STOPPING

            # Unsubscribe from all subscriptions, then clear the list.
            for unsub in self._subscriptions:
                unsub()

            self._subscriptions = []
            self._state = BlenderState.STOPPED
            _LOGGER.debug("Successfully stopped listening for events.")
        else:
            _LOGGER.debug(
                "Not going to unsubscribe from events since we're in an unsupported state (%s) to do so.",
                self._state.name,
            )
