"""Module for event listening and -dispatching."""

import logging
from collections.abc import Callable
from typing import Final, Literal

from homeassistant.components.climate.const import DOMAIN as ClimateEntityPlatform
from homeassistant.components.switch.const import DOMAIN as SchedulerEntityPlatform
from homeassistant.core import CALLBACK_TYPE as HomeAssistantCallback
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_added_domain,
    async_track_state_change_event,
    async_track_state_removed_domain,
)
from homeassistant.helpers.template import integration_entities

from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.helpers.iterators import UnmodifiableDict
from custom_components.scheduler.const import DOMAIN as SchedulerDomain

_LOGGER = logging.getLogger(__name__)


ATTR_SCHEDULER_ENTITY_ADDED: Final[str] = "scheduler_entity_added"
ATTR_SCHEDULER_ENTITY_REMOVED: Final[str] = "scheduler_entity_removed"
ATTR_CLIMATE_ENTITY_ADDED: Final[str] = "climate_entity_added"
ATTR_CLIMATE_ENTITY_REMOVED: Final[str] = "climate_entity_removed"

type EntityEventCallback = Callable[[Event[EventStateChangedData]], None]
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

        self._entity_update_subscriptions: dict[
            str, tuple[HomeAssistantCallback, list[EntityEventCallback]]
        ] = {}
        """Tuples of an unsubscribe callback and a list of event listeners, indexed by entity id."""

    def _is_acceptable(self, entity_id: str) -> bool:
        """Return whether the given entity_id is allowed to be listened to for updates."""
        state = self._hass.states.get(entity_id=entity_id)

        # Only these two domains are accepted.
        if state.domain not in [SchedulerEntityPlatform, ClimateEntityPlatform]:
            return False

        required_domain = SchedulerDomain if state.domain == SchedulerEntityPlatform else DOMAIN
        return entity_id in integration_entities(hass=self._hass, entry_name=required_domain)

    @callback
    def _dispatch_entity_added_event(
        self, domain: Literal["switch", "climate"], event: Event[EventStateChangedData]
    ) -> None:
        """Notify all listeners that a new entity was added to the domain they subscribed to."""
        for cb in self._add_entity_listeners[domain]:
            cb(event)

    @callback
    def _dispatch_entity_removed_event(
        self, domain: Literal["switch", "climate"], event: Event[EventStateChangedData]
    ) -> None:
        """Notify all listeners that an entity was removed from the domain they subscribed to."""
        for cb in self._remove_entity_listeners[domain]:
            cb(event)

    def subscribe_to_added_entities(
        self, domain: Literal["switch", "climate"], listener: EntityEventCallback
    ) -> UnsubscribeCallback:
        """Register the listener for entities that are added to the given domain.

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

        Args:
            domain (Literal['switch', 'climate']): The domain to listen to.
            listener (EntityEventCallback): The callback to call when an entity was removed.

        Returns:
            A callback which unsibscribes the listener from receiving updates about removed entities.

        """

        self._remove_entity_listeners[domain].append(listener)

        return lambda: self._remove_entity_listeners[domain].remove(listener)

    def subscribe_to_entity_updates(
        self, entity_id: str, listener: EntityEventCallback
    ) -> UnsubscribeCallback:
        """Register the listener to receive updates if the entity with `entity_id` changed.

        Args:
            entity_id (str): The entity id to listen to. This must be either a `switch` from the `scheduler` integration
                or a `climate` from the `remeha_modbus` integration.
            listener (EntityEventCallback): The callback to call when the entity was updated.

        Returns:
            A callback which unsubscribes the listener from receiving updates about the entity.

        Raises:
            ValueError: if `entity_id` is not the id of an entity of an accepted domain.

        """

        if not self._is_acceptable(entity_id=entity_id):
            raise ValueError(
                f"Not registering listener for updates of {entity_id}: entity domain or originating platform not acceptable."
            )

        have_listeners: bool = entity_id in self._entity_update_subscriptions
        if have_listeners:
            _, subscriptions = self._entity_update_subscriptions[entity_id]
            subscriptions.append(listener)
        else:

            def _notify_all(event: Event[EventStateChangedData]):
                """Notify all subscribers of the change event."""
                _, all_subscribers = self._entity_update_subscriptions.get(entity_id, [])
                for subscriber in all_subscribers:
                    subscriber(event)

            unsubscribe = async_track_state_change_event(
                hass=self._hass, entity_ids=entity_id, action=_notify_all
            )
            self._entity_update_subscriptions[entity_id] = (unsubscribe, [listener])

        def _unsubscribe_and_remove():
            """Unsubscribe the listener and if no listeners exist after that, stop listening to updates of the related entity."""
            unsubscribe_all, all_listeners = self._entity_update_subscriptions[entity_id]
            all_listeners.remove(listener)

            # If the callback-list is empty, unsubscribe from the entity updates and remove its entry.
            if not all_listeners:
                unsubscribe_all()
                del self._entity_update_subscriptions[entity_id]

        return _unsubscribe_and_remove
