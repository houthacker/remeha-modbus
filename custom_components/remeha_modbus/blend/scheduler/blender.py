"""Module for synchronization between a `scheduler.schedule` and a `remeha_modbus.ZoneSchedule`."""

import logging
from typing import Any, cast, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from remeha_modbus.blend.blender import BlenderState
from remeha_modbus.blend.scheduler.const import SCHEDULER_INSTALLATION_URL, SchedulerDomain
from remeha_modbus.blend.scheduler.helpers import scheduler_is_installed
from remeha_modbus.const import DOMAIN
from remeha_modbus.errors import MissingExternalComponent

from custom_components.remeha_modbus.blend import Blender
from custom_components.remeha_modbus.blend.scheduler.scenarios import (
    ModbusScheduleUpdated,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

from .event_dispatcher import EventDispatcher, UnsubscribeCallback, ZoneScheduleUpdatedData

_LOGGER = logging.getLogger(__name__)


class SchedulerBlender(Blender):
    """The `Blender` runs the scenarios required to integrate between the `remeha_modbus` and `scheduler` schedules.

    In general, the schedule entities from the `scheduler` integration live in the `switch` domain, whereas schedules
    from _this_ integration are `ZoneSchedule` objects in a `ClimateZone`.

    The following scenario's exist:
    1. The `push_zone_schedules` service is called. This causes all schedules from modbus to be
        pushed to the scheduler component, ignoring any pre-existing non-linked schedules.
        This scenario will only push schedules if the related climates are in `auto` mode.
    2. The `remove_synced_schedules` service is called. All synchronized schedules are removed from
        the `scheduler` component.
    3. A linked `scheduler.schedule` is updated. This pushes the updated schedule to modbus.
    4. A linked `scheduler.schedule` is removed. This unlinks the schedule and leaves the modbus schedule
        unmodified.
    5. A `remeha_modbus` schedule is updated through an external source (e.g. from the Remeha Home app).
        This pushes the updated schedule to the `scheduler` integration.

    Scenario 1 and 2 are exclusively called from HA services, while scenario 3 through 5 are automatically executed
    using event listeners in this blender.
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
            cast(ConfigEntry[Any], self._coordinator.config_entry).async_create_task(
                self._hass, scenario.async_execute()
            )
        else:
            _LOGGER.debug(
                "Ignoring ZoneSchedule-update event (zone_id=%d, schedule_id=%d, day=%s) because current blender state %s\
                    prevents us from handling it.",
                schedule.zone_id,
                schedule.id.value,
                schedule.day.name,
                self._state.name,
            )

    def _home_assistant_started(self, _: Event) -> None:
        """Sync schedules after HA started."""

        if self._ready_for_scenario_execution():
            _LOGGER.debug("Executing initial modbus schedule synchronization")

            for climate in [
                c
                for c in self._coordinator.get_climates(predicate=lambda _: True)
                if c.selected_schedule is not None
            ]:
                for schedule in [s for s in climate.current_schedule.values() if s is not None]:
                    scenario = ModbusScheduleUpdated(
                        hass=self._hass, coordinator=self._coordinator, schedule=schedule
                    )

                    # Create a background task to synchronize the schedules between modbus
                    # and the scheduler component.
                    # Waiting on it is not required, so a background task is sufficient.
                    cast(ConfigEntry[Any], self._coordinator.config_entry).async_create_task(
                        self._hass, scenario.async_execute()
                    )
        else:
            _LOGGER.warning(
                "Not executing initial modbus schedule synchronization because current blender state %s\
                prevents us from doing that.",
                self._state.name,
            )

    @property
    def state(self) -> BlenderState:
        """Return the current state of the Blender."""
        return self._state

    @override
    def bootstrap(self):
        """Start listening for relevant events to enable executing the defined scenarios.

        If already started, this method has no effect. If stopped, this method will re-subscribe
        to the required events.

        Raises:
            MissingExternalComponent: if the scheduler component hasn't been installed.

        """

        if not scheduler_is_installed(self._hass):
            raise MissingExternalComponent(
                translation_domain=DOMAIN,
                translation_key="missing_external_component",
                translation_placeholders={
                    "component": SchedulerDomain,
                    "url": SCHEDULER_INSTALLATION_URL,
                },
            )

        if self._state in [BlenderState.INITIAL, BlenderState.STOPPED]:
            _LOGGER.debug("Starting SchedulerBlender.")
            self._state = BlenderState.STARTING

            # TODO subscribe to events required to run the scenarios.
            # Subscribe to state changes required to blend in.
            # self._subscriptions = [
            #     self._dispatcher.subscribe_to_added_entities(
            #         domain=SwitchDomain, listener=self._scheduler_entity_added
            #     ),
            #     self._dispatcher.subscribe_to_zone_schedule_updates(
            #         listener=self._zone_schedule_updated
            #     ),
            # ]

            self._state = BlenderState.STARTED
            _LOGGER.debug("Starting SchedulerBlender successful.")
        else:
            _LOGGER.debug(
                "Not going start SchedulerBlender since its current state (%s) doesn't allow me to do so.",
                self._state.name,
            )

    @override
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
