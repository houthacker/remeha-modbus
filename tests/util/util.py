"""Testing utilities."""

import logging
from collections.abc import Callable, Coroutine
from datetime import timedelta
from inspect import iscoroutinefunction
from secrets import token_hex
from typing import Any

import attr
import voluptuous as vol
from homeassistant.components.switch import DOMAIN as ScheduleEntityPlatform
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from custom_components.scheduler import switch as SwitchPlatformModule
from custom_components.scheduler.const import (
    ADD_SCHEDULE_SCHEMA,
    ATTR_TAGS,
    EDIT_SCHEDULE_SCHEMA,
    EVENT_ITEM_UPDATED,
    SERVICE_ADD,
    SERVICE_EDIT,
)
from custom_components.scheduler.const import DOMAIN as SchedulerDomain
from custom_components.scheduler.store import ScheduleEntry, parse_schedule_data
from custom_components.scheduler.switch import ScheduleEntity

_LOGGER = logging.getLogger(__name__)


def async_add_mock_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    schema: vol.Schema | None = None,
    user_callback: (
        Callable[[ServiceCall], None] | Callable[[ServiceCall], Coroutine[Any, Any, None]] | None
    ) = None,
    response: ServiceResponse | None = None,
    supports_response: SupportsResponse | None = None,
) -> list[ServiceCall]:
    """Add a mock service to home assistant.

    Args:
        hass (HomeAssistant): Home Assistant instance.
        domain (str): The domain of the mock service.
        service (str): The name of the mock service.
        schema (vol.Schema | None): The schema of the mock service.
        user_callback (Callable[[ServiceCall], None] | None): An optional callback method.
        response (ServiceResponse): An optional response object.
        supports_response (SupportsResponse): The type of response supported by the service.

    """

    call_log: list[ServiceCall] = []

    @callback
    async def _cb(call: ServiceCall) -> None:
        call_log.append(call)

        if user_callback is not None:
            if iscoroutinefunction(user_callback):
                await user_callback(call)
            else:
                user_callback(call)

    if supports_response is None:
        if response is not None:
            supports_response = SupportsResponse.OPTIONAL
        else:
            supports_response = SupportsResponse.NONE

    hass.services.async_register(
        domain,
        service,
        _cb,
        schema=schema,
        supports_response=supports_response,
    )

    return call_log


class SchedulerCoordinatorStub(DataUpdateCoordinator):
    """Stubbed data coordinator for the scheduler component."""

    def __init__(self, hass: HomeAssistant):
        """Create a stubbed scheduler coordinator with in-memory storage only."""

        super().__init__(hass, _LOGGER, name="test_scheduler", update_interval=None)

        self._schedules: dict[str, ScheduleEntry] = {}
        self._tags: dict[str, list[str]] = {}

        self.state = "ready"
        """Stub state of scheduler coordinator."""

    def clear_schedules(self):
        """Clear all stored schedules."""

        self._schedules = {}
        self._tags = {}

    def async_get_tags_for_schedule(self, schedule_id: str):
        """Retrieve the tags for a schedule."""

        return sorted(self._tags.get(schedule_id, []))

    def get_schedule(self, schedule_id: str) -> dict:
        """Get an existing ScheduleEntry by id."""
        s = self._schedules.get(schedule_id)
        return attr.asdict(s) if s else None

    def get_schedules(self) -> dict:
        """Get all ScheduleEntries."""

        return {key: attr.asdict(value) for key, value in self._schedules.items()}

    async def async_create_schedule(
        self,
        call: ServiceCall,
        async_add_entities: (
            Callable[[list[ScheduleEntity]], None]
            | Callable[[list[ScheduleEntity]], Coroutine[Any, Any, None]]
            | None
        ) = None,
        user_callback: Callable[[ScheduleEntry], None] | None = None,
    ) -> None:
        """Create a new schedule and add it to the scheduler domain entities.

        Note: `user_callback` is called _before_ the created entry is stored, enabling users to raise
        an exception to prevent storage of the entity.

        Args:
            call (ServiceCall): The service call.
            async_add_entities (Callable[[ScheduleEntry], None] | None): The callback to add the entities to hass.
            user_callback (Callable[[ScheduleEntry], None] | None): An optional callback which provides the `ScheduleEntry`.

        """

        data: dict = parse_schedule_data(dict(call.data))
        schedule_id = token_hex(3)
        while schedule_id in self._schedules:
            schedule_id = token_hex(3)

        # Store any linked tags and remove them from the data, since a ScheduleEntry
        # does not allow for tags.
        if ATTR_TAGS in data:
            tags = data[ATTR_TAGS]
            del data[ATTR_TAGS]
        else:
            tags = []

        new_schedule = ScheduleEntry(**data, schedule_id=schedule_id)

        # If there is a user callback, execute that first to enable these callbacks
        # to raise an exception, which will prevent us from adding the schedule
        # to the in-memory storage.
        if user_callback is not None:
            user_callback(new_schedule)

        self._tags[schedule_id] = list(tags)
        self._schedules[schedule_id] = new_schedule

        # Add the schedule to hass
        if new_schedule.name and len(slugify(new_schedule.name)):
            entity_id = f"{ScheduleEntityPlatform}.schedule_{slugify(new_schedule.name)}"
        else:
            entity_id = f"{ScheduleEntityPlatform}.schedule_{schedule_id}"

        entity = ScheduleEntity(
            coordinator=self,
            hass=self.hass,
            schedule_id=new_schedule.schedule_id,
            entity_id=entity_id,
        )
        self.hass.data[SchedulerDomain]["schedules"][schedule_id] = entity_id

        await async_add_entities([entity])

    def edit_schedule(
        self, call: ServiceCall, user_callback: Callable[[ScheduleEntry], None] | None = None
    ) -> None:
        """Edit an existing schedule."""

        schedule_id: str | None = next(
            iter(
                [
                    schedule_id
                    for (schedule_id, entity_id) in self.hass.data[SchedulerDomain][
                        "schedules"
                    ].items()
                    if entity_id == call.data[ATTR_ENTITY_ID]
                ]
            ),
            None,
        )

        if schedule_id is None:
            raise vol.Invalid(f"Entity not found: {call.data[ATTR_ENTITY_ID]}")

        data = dict(call.data)
        del data[ATTR_ENTITY_ID]

        if ATTR_TAGS in data:
            tags: list[str] = list(data[ATTR_TAGS])
            del data[ATTR_TAGS]
        else:
            tags = []

        old_schedule = self._schedules.get(schedule_id)
        changes = parse_schedule_data(data)
        new_schedule = attr.evolve(old_schedule, **changes)

        # If there is a user callback, execute that first to enable these callbacks
        # to raise an exception, which will prevent us from adding the schedule
        # to the in-memory storage.
        if user_callback is not None:
            user_callback(new_schedule)

        if tags:
            self._tags[schedule_id] = tags

        self._schedules[schedule_id] = new_schedule

        # Notify scheduler entity of changes.
        async_dispatcher_send(self.hass, EVENT_ITEM_UPDATED, schedule_id)


class SchedulerStorageStub:
    """Duck-typed, stubbed implementation of scheduler.SchedulerStorage."""

    def __init__(self, coordinator: SchedulerCoordinatorStub) -> None:
        """Create a new storage stub for the scheduler integration."""
        self._coordinator = coordinator

    async def async_load(self) -> None:
        """Load the registry of schedule entries. Is a no-op in this implementation."""

    def async_schedule_save(self) -> None:
        """Schedule saving the registry of schedules. Is a no-op in this implementation."""

    async def async_save(self) -> None:
        """Save the registry of schedules. Is a no-op in this implementation."""

    async def async_delete(self):
        """Delete all data in the registry."""

        self._coordinator.clear_schedules()

    def async_get_schedule(self, schedule_id: str) -> dict:
        """Get an existing ScheduleEntry by id."""

        return self._coordinator.get_schedule(schedule_id=schedule_id)

    def async_get_schedules(self) -> dict:
        """Get all existing ScheduleEntries as a dict."""

        return self._coordinator.get_schedules()


def set_storage_stub_return_value(hass: HomeAssistant, scheduler_storage):
    """Mock implementation of scheduler.store.async_get_registry."""

    coordinator: SchedulerCoordinatorStub = hass.data[SchedulerDomain]["coordinator"]
    scheduler_storage.return_value = SchedulerStorageStub(coordinator=coordinator)

    return scheduler_storage


class SchedulerPlatformStub:
    """A stub supporting the scheduler service features used by `remeha_modbus`."""

    def __init__(
        self,
        add_schedule_callback: Callable[[ScheduleEntry], None] | None = None,
        edit_schedule_callback: Callable[[ScheduleEntry], None] | None = None,
    ):
        """Create a new scheduler component.

        Note: Creating a new SchedulerComponentStub overwrites any pre-existing scheduler components in home assistant.

        Args:
            add_schedule_callback: A callback that is called when a new schedule is added.
            edit_schedule_callback: A callback that is called when an existing schedule is edited.

        """
        self._hass: HomeAssistant | None = None
        self._platform: EntityPlatform | None = None
        self._user_callbacks: dict[str, Callable[[ScheduleEntry], None]] = {
            SERVICE_ADD: add_schedule_callback,
            SERVICE_EDIT: edit_schedule_callback,
        }
        self._callback_logs: dict[str, list[ServiceCall]] = {}
        self._coordinator: SchedulerCoordinatorStub | None = None

    def call_logs(self, service: str) -> list[ServiceCall]:
        """Return a copy of the service call logs for the given service."""
        return self._callback_logs.get(service, [])

    async def async_add_to_hass(self, hass: HomeAssistant):
        """Add this service stub to home assistant."""

        self._platform = EntityPlatform(
            hass=hass,
            logger=_LOGGER,
            domain=ScheduleEntityPlatform,
            platform_name=SchedulerDomain,
            platform=SwitchPlatformModule,
            scan_interval=timedelta(seconds=0),
            entity_namespace=None,
        )

        self._coordinator = SchedulerCoordinatorStub(hass)
        hass.data[SchedulerDomain] = {
            "coordinator": self._coordinator,
            "get_call_logs": lambda service: self.call_logs(service),
            "schedules": {},
        }

        async def _async_add_callback(call: ServiceCall):
            await self._coordinator.async_create_schedule(
                call=call,
                async_add_entities=self._platform.async_add_entities,
                user_callback=self._user_callbacks.get(SERVICE_ADD),
            )

        self._callback_logs = {
            SERVICE_ADD: async_add_mock_service(
                hass=hass,
                domain=SchedulerDomain,
                schema=ADD_SCHEDULE_SCHEMA,
                service=SERVICE_ADD,
                user_callback=_async_add_callback,
            ),
            SERVICE_EDIT: async_add_mock_service(
                hass=hass,
                domain=SchedulerDomain,
                schema=EDIT_SCHEDULE_SCHEMA.extend({vol.Required(ATTR_ENTITY_ID): cv.string}),
                service=SERVICE_EDIT,
                user_callback=lambda call: self._coordinator.edit_schedule(
                    call=call, user_callback=self._user_callbacks.get(SERVICE_EDIT)
                ),
            ),
        }
