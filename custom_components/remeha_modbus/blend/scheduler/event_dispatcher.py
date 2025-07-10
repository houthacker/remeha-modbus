"""Module for event listening and -dispatching."""

import logging
from collections.abc import Callable
from typing import Final, Literal, TypedDict

from homeassistant.components.climate.const import DOMAIN as ClimateEntityPlatform
from homeassistant.components.switch.const import DOMAIN as SchedulerEntityPlatform
from homeassistant.core import CALLBACK_TYPE as HomeAssistantCallback
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity import entity_sources
from homeassistant.helpers.event import (
    async_track_state_added_domain,
    async_track_state_removed_domain,
)

from custom_components.remeha_modbus.api import ZoneSchedule
from custom_components.remeha_modbus.const import DOMAIN, EVENT_ZONE_SCHEDULE_UPDATED
from custom_components.remeha_modbus.helpers.iterators import UnmodifiableDict
from custom_components.scheduler.const import DOMAIN as SchedulerDomain

_LOGGER = logging.getLogger(__name__)


ATTR_SCHEDULER_ENTITY_ADDED: Final[str] = "scheduler_entity_added"
ATTR_SCHEDULER_ENTITY_REMOVED: Final[str] = "scheduler_entity_removed"
ATTR_CLIMATE_ENTITY_ADDED: Final[str] = "climate_entity_added"
ATTR_CLIMATE_ENTITY_REMOVED: Final[str] = "climate_entity_removed"
ATTR_ZONE_SCHEDULE_UPDATED: Final[str] = "zone_schedule_updated"


class ZoneScheduleUpdatedData(TypedDict):
    """Event data for an `EVENT_ZONE_SCHEDULE_UPDATED`."""

    schedule: ZoneSchedule


type EntityEventCallback = Callable[[Event[EventStateChangedData]], None]
type ZoneScheduleEventCallback = Callable[[Event[ZoneScheduleUpdatedData]], None]
type UnsubscribeCallback = Callable[[], None]

ACCEPTED_DOMAINS: Final[tuple[str, str]] = (ClimateEntityPlatform, SchedulerEntityPlatform)


class EventDispatcher:
    """The event dispatcher listens for scheduler-related events and dispatches them."""

    def __init__(self, hass: HomeAssistant):
        """Create a new event dispatcher."""

        self._hass: HomeAssistant = hass

        self._domain_subscriptions: UnmodifiableDict[str, HomeAssistantCallback] = (
            UnmodifiableDict.create(
                {
                    ATTR_SCHEDULER_ENTITY_ADDED: async_track_state_added_domain(
                        hass=hass,
                        domains=SchedulerEntityPlatform,
                        action=lambda event: self._dispatch_entity_added_event(
                            domain=SchedulerEntityPlatform, event=event
                        ),
                    ),
                    ATTR_SCHEDULER_ENTITY_REMOVED: async_track_state_removed_domain(
                        hass=hass,
                        domains=SchedulerEntityPlatform,
                        action=lambda event: self._dispatch_entity_removed_event(
                            domain=SchedulerEntityPlatform, event=event
                        ),
                    ),
                    ATTR_CLIMATE_ENTITY_ADDED: async_track_state_added_domain(
                        hass=hass,
                        domains=ClimateEntityPlatform,
                        action=lambda event: self._dispatch_entity_added_event(
                            domain=ClimateEntityPlatform, event=event
                        ),
                    ),
                    ATTR_CLIMATE_ENTITY_REMOVED: async_track_state_removed_domain(
                        hass=hass,
                        domains=ClimateEntityPlatform,
                        action=lambda event: self._dispatch_entity_removed_event(
                            domain=ClimateEntityPlatform, event=event
                        ),
                    ),
                    ATTR_ZONE_SCHEDULE_UPDATED: self._hass.bus.async_listen(
                        EVENT_ZONE_SCHEDULE_UPDATED,
                        lambda event: self._dispatch_zone_schedule_updated_event(event=event),
                    ),
                }
            )
        )
        """Subscriptions to entities added/removed from either the `switch` or the `climate` domain."""

        self._add_entity_listeners: dict[str, list[EntityEventCallback]] = {
            ClimateEntityPlatform: [],
            SchedulerEntityPlatform: [],
        }
        """Listeners to entity-added events for either domain."""

        self._remove_entity_listeners: dict[str, list[EntityEventCallback]] = {
            ClimateEntityPlatform: [],
            SchedulerEntityPlatform: [],
        }
        """Listeners to entity-removal events for either domain."""

        self._zone_schedule_update_listeners: list[ZoneScheduleEventCallback] = []
        """Listeners to zone schedule updates."""

    def _is_acceptable(self, entity_id: str) -> bool:
        """Return whether the given entity_id is allowed to be listened to for updates."""
        state = self._hass.states.get(entity_id=entity_id)

        # Only these two domains are accepted.
        if state.domain not in [SchedulerEntityPlatform, ClimateEntityPlatform]:
            return False

        required_domain = SchedulerDomain if state.domain == SchedulerEntityPlatform else DOMAIN
        entity_info = entity_sources(self._hass).get(entity_id, None)
        return entity_info["domain"] == required_domain if entity_info else False

    @callback
    def _dispatch_entity_added_event(
        self, domain: Literal["switch", "climate"], event: Event[EventStateChangedData]
    ) -> None:
        """Notify all listeners that a new entity was added to the domain they subscribed to."""

        if self._is_acceptable(entity_id=event.data["entity_id"]):
            for cb in self._add_entity_listeners[domain]:
                cb(event)
        else:
            _LOGGER.debug(
                "Ignoring event for added entity %s since it's not owned by one of these integrations: [%s, %s].",
                event.data["entity_id"],
                SchedulerDomain,
                DOMAIN,
            )

    @callback
    def _dispatch_entity_removed_event(
        self, domain: Literal["switch", "climate"], event: Event[EventStateChangedData]
    ) -> None:
        """Notify all listeners that an entity was removed from the domain they subscribed to."""

        if self._is_acceptable(entity_id=event.data["entity_id"]):
            for cb in self._remove_entity_listeners[domain]:
                cb(event)
        else:
            _LOGGER.debug(
                "Ignoring event for removed entity %s since it was not owned by one of these integrations: [%s, %s].",
                event.data["entity_id"],
                SchedulerDomain,
                DOMAIN,
            )

    @callback
    def _dispatch_zone_schedule_updated_event(self, event: Event[ZoneScheduleUpdatedData]) -> None:
        """Notify all listeners that a zone schedule was updated."""

        for cb in self._zone_schedule_update_listeners:
            cb(event)

    def subscribe_to_added_entities(
        self, domain: Literal["switch", "climate"], listener: EntityEventCallback
    ) -> UnsubscribeCallback:
        """Register the listener for entities that are added to the given domain.

        Note: events are only dispatched to the listener if its related entity is owned by either
        the `scheduler`- or `remeha_modbus` integration.

        Args:
            domain (Literal['switch', 'climate']): The domain to listen to.
            listener (EntityEventCallback): The callback to call when an entity was added.

        Returns:
            A callback which unsibscribes the listener from receiving updates about added entities.

        """

        self._add_entity_listeners[domain].append(listener)

        return lambda: self._add_entity_listeners[domain].remove(listener)

    def subscribe_to_removed_entities(
        self, domain: Literal["switch", "climate"], listener: EntityEventCallback
    ) -> UnsubscribeCallback:
        """Register the listener for entities that are removed from the given domain.

        Note: events are only dispatched to the listener if its related entity is owned by either
        the `scheduler`- or `remeha_modbus` integration.

        Args:
            domain (Literal['switch', 'climate']): The domain to listen to.
            listener (EntityEventCallback): The callback to call when an entity was removed.

        Returns:
            A callback which unsibscribes the listener from receiving updates about removed entities.

        """

        self._remove_entity_listeners[domain].append(listener)

        return lambda: self._remove_entity_listeners[domain].remove(listener)

    def subscribe_to_zone_schedule_updates(
        self, listener: ZoneScheduleEventCallback
    ) -> UnsubscribeCallback:
        """Register the listener to receive updates of all zone schedules.

        Note: The `RemehaApi` only tracks zone schedules of the currently selected time program. So if for example
        the selected schedule is `SCHEDULE_1`, no updates will be fired for schedules in `SCHEDULE_2` or `SCHEDULE_3`.

        Args:
            listener (ZoneScheduleEventCallback): The callback to call when a `ZoneSchedule` was updated.

        """

        self._zone_schedule_update_listeners.append(listener)

        return lambda: self._zone_schedule_update_listeners.remove(listener)
