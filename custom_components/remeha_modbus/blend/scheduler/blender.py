"""Module for synchronization between a `scheduler.schedule` and a `remeha_modbus.ZoneSchedule`."""

import asyncio
import logging
from typing import Final, override

from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.const import STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import EventStateChangedData, async_track_state_change_event

from custom_components.remeha_modbus.api.schedule import ZoneSchedule
from custom_components.remeha_modbus.blend import Blender
from custom_components.remeha_modbus.blend.blender import BlenderState
from custom_components.remeha_modbus.blend.scheduler.const import (
    SCHEDULER_INSTALLATION_URL,
    SchedulerDomain,
)
from custom_components.remeha_modbus.blend.scheduler.helpers import scheduler_is_installed
from custom_components.remeha_modbus.blend.scheduler.scenarios.modbus_schedule_updated import (
    ModbusScheduleUpdated,
)
from custom_components.remeha_modbus.blend.scheduler.scenarios.scheduler_schedule_added import (
    SchedulerScheduleAdded,
)
from custom_components.remeha_modbus.blend.scheduler.scenarios.scheduler_schedule_updated import (
    SchedulerScheduleUpdated,
)
from custom_components.remeha_modbus.const import DOMAIN, SWITCH_SCHEDULE_SYNC
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import MissingExternalComponent
from custom_components.remeha_modbus.helpers.entities import is_scheduler_switch

from .event_dispatcher import EventDispatcher, UnsubscribeCallback

_LOGGER = logging.getLogger(__name__)


_SCHEDULE_SYNC_SWITCH_ENTITY_ID = f"{SwitchDomain}.{SWITCH_SCHEDULE_SYNC}"
"""The entity_id of the switch that controls whether zone schedules are synchronized with the scheduler component."""

_SWITCH_ADDED_SUBSCRIPTION_KEY: Final[str] = "__switch_added__"

_ZONE_SCHEDULE_UPDATED_SUBSCRIPTION_KEY: Final[str] = "__zone_schedule_updated__"


class SchedulerBlender(Blender):
    """The `Blender` runs the scenarios required to integrate between the `remeha_modbus` and `scheduler` schedules.

    In general, the schedule entities from the `scheduler` integration live in the `switch` domain, whereas schedules
    from _this_ integration are `ZoneSchedule` objects in a `ClimateZone`.

    Scenarios are only run if schedule synchronization is enabled. This is done through the switch entity
    `switch.enable_schedule_sync`.

    The following scenario's exist:
    1. An updated `ZoneSchedule` is received from modbus. These updates are pushed to the
       scheduler component. Schedules that are new to the scheduler component are put on the
       waiting list for linking (see schenario 3). Schedules that have been linked are added to
       the waiting list for updating (see schenario 4).
    2. The `remove_synced_schedules` service is called. All synchronized schedules are removed from
        the `scheduler` component.
    3. A `scheduler.schedule` is added. If it's on the waiting list, it is linked to the corresponding
        `ZoneSchedule` and listened to for updates. Otherwise, this schedule is ignored.
    4. A linked `scheduler.schedule` is updated. If on the waiting list for updating, the updated schedule
        is removed from the waiting list and further ignored because the update was caused by an updated
        `ZoneSchedule` from modbus.
        If it's not on the waiting list, the update is pushed to modbus.
    5. A linked `scheduler.schedule` is removed. This unlinks the schedule and leaves the modbus schedule
        unmodified. Update listeners are unsubscribed from.
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

        self._subscriptions: dict[str, UnsubscribeCallback] = {}

    def _ready_for_scenario_execution(self) -> bool:
        """Return whether a scenario can be executed according to the current blender state."""

        return self._state is BlenderState.STARTED

    @callback
    def _switch_entity_added(self, event: Event[EventStateChangedData]) -> None:
        """Handle a newly added `switch` entity."""

        if self._ready_for_scenario_execution():
            if is_scheduler_switch(self._hass, event.data["entity_id"]):

                @callback
                def async_track_schedule_updated():
                    _LOGGER.debug(
                        "Tracking updates for schedule entity %s", event.data["entity_id"]
                    )

                    # Listen to updates of this schedule
                    self._subscriptions[event.data["entity_id"]] = (
                        self._dispatcher.track_updated_entities(
                            event.data["entity_id"], self._switch_entity_updated
                        )
                    )

                scenario = SchedulerScheduleAdded(
                    self._hass,
                    self._coordinator,
                    event.data["new_state"],
                    async_track_schedule_updated,
                )

                # Execute the scenario in a separate task since it requires I/O.
                asyncio.run_coroutine_threadsafe(scenario.async_execute(), self._hass.loop)
        else:
            _LOGGER.debug(
                "Ignoring schedule_added event (entity_id = %s) because current blender state %s\
                prevents us from handling it.",
                event.data["entity_id"],
                self._state.name,
            )

    @callback
    def _switch_entity_updated(self, event: Event[EventStateChangedData]) -> None:
        """Handle an updated scheduler.schedule."""

        if self._ready_for_scenario_execution():
            if is_scheduler_switch(self._hass, event.data["entity_id"]):
                scenario = SchedulerScheduleUpdated(
                    self._hass, self._coordinator, event.data["new_state"]
                )

                # Execute the scenario in a separate task since it requires I/O.
                asyncio.run_coroutine_threadsafe(scenario.async_execute(), self._hass.loop)
        else:
            _LOGGER.debug(
                "Ignoring schedule_updated event (entity_id = %s) because current blender state %s\
                prevents us from handling it.",
                event.data["entity_id"],
                self._state.name,
            )

    @callback
    def _zone_schedule_updated(self, schedule: ZoneSchedule) -> None:
        """Handle a modbus `ZoneSchedule` update.

        Args:
            schedule (ZoneSchedule): The updated zone schedule.

        """

        if self._ready_for_scenario_execution():
            scenario = ModbusScheduleUpdated(
                hass=self._hass, coordinator=self._coordinator, schedule=schedule
            )

            # Execute the scenario in a separate task since it requires I/O.
            asyncio.run_coroutine_threadsafe(scenario.async_execute(), self._hass.loop)
        else:
            _LOGGER.debug(
                "Ignoring ZoneSchedule-update event (zone_id=%d, schedule_id=%d, day=%s) because current blender state %s\
                    prevents us from handling it.",
                schedule.zone_id,
                schedule.id.value,
                schedule.day.name,
                self._state.name,
            )

    async def _enable_zone_synchronization(self) -> None:
        """Enable synchronizing zone schedules with `scheduler.schedule` entities."""

        _LOGGER.debug("Enabling zone update synchronization.")

        # Subscribe to newly added scheduler.schedule entities
        self._subscriptions[_SWITCH_ADDED_SUBSCRIPTION_KEY] = self._dispatcher.track_added_entities(
            SwitchDomain, self._switch_entity_added
        )

        # Subscribe to ZoneSchedule updates if switch entity is enabled.
        self._subscriptions[_ZONE_SCHEDULE_UPDATED_SUBSCRIPTION_KEY] = (
            self._coordinator.track_zone_schedule_updates(self._zone_schedule_updated)
        )

        # Subscribe to updates of linked scheduler.schedule entities.
        for link in await self._coordinator.async_get_scheduler_links():
            self._subscriptions[link.scheduler_entity_id] = self._dispatcher.track_updated_entities(
                link.scheduler_entity_id, self._switch_entity_updated
            )

    async def _disable_zone_synchronization(self) -> None:
        """Disable synchronizing zone schedules with `scheduler.schedule` entities."""

        # Collect all subscription keys we must unsubscribe from.
        subscriptions = [_SWITCH_ADDED_SUBSCRIPTION_KEY, _ZONE_SCHEDULE_UPDATED_SUBSCRIPTION_KEY]
        subscriptions += [
            link.scheduler_entity_id for link in await self._coordinator.async_get_scheduler_links()
        ]

        # Unsubscribe from all
        for key in subscriptions:
            unsubscribe = self._subscriptions.get(key)
            if unsubscribe is not None:
                del self._subscriptions[key]
                unsubscribe()

    @callback
    async def _sync_settings_updated(self, event: Event[EventStateChangedData]) -> None:
        """Handle updates of the sync-required settings."""

        entity_id = event.data["entity_id"]
        if event.data["new_state"] is None:
            _LOGGER.debug(
                "Received state change for entity %s without new_state; ignoring", entity_id
            )
            return

        if event.data["new_state"].state == STATE_ON:
            await self._enable_zone_synchronization()
        elif entity_id in self._subscriptions:
            # state = OFF, so unsubscribe from events.
            await self._disable_zone_synchronization()
        else:
            _LOGGER.warning(
                "Received state change for entity %s we're not subscribed to.", entity_id
            )

    @property
    def state(self) -> BlenderState:
        """Return the current state of the Blender."""
        return self._state

    @override
    async def async_blend(self):
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

            # Enable/disable schedule synchronization based on switch state.
            self._subscriptions[_SCHEDULE_SYNC_SWITCH_ENTITY_ID] = async_track_state_change_event(
                self._hass,
                [_SCHEDULE_SYNC_SWITCH_ENTITY_ID],
                self._sync_settings_updated,
            )

            # If the switch is currently ON, enable schedule synchronization. Otherwise,
            # this is done later when the switch is toggled.
            schedule_sync_state = self._hass.states.get(_SCHEDULE_SYNC_SWITCH_ENTITY_ID)
            if schedule_sync_state is not None and schedule_sync_state.state == STATE_ON:
                await self._enable_zone_synchronization()

            else:
                _LOGGER.info(
                    "Not subscribing to zone schedule updates now, since %s is switched off.",
                    _SCHEDULE_SYNC_SWITCH_ENTITY_ID,
                )

            self._state = BlenderState.STARTED
            _LOGGER.debug("SchedulerBlender started.")
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
            for unsub in self._subscriptions.values():
                unsub()

            self._subscriptions = {}
            self._state = BlenderState.STOPPED
            _LOGGER.debug("Successfully stopped listening for events.")
        else:
            _LOGGER.debug(
                "Not going to unsubscribe from events since we're in an unsupported state (%s) to do so.",
                self._state.name,
            )
