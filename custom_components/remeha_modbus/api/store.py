"""Storage for the Remeha Modbus integration."""

import logging
from collections.abc import MutableMapping
from uuid import UUID

from homeassistant.helpers.storage import Store
from pydantic.dataclasses import dataclass

from custom_components.remeha_modbus.const import (
    ClimateZoneScheduleId,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class WaitingListEntry:
    """Entry for the waiting list of schedules to be linked."""

    uuid: UUID
    """The uuid that is listed in the tags of the `scheduler.schedule`."""

    zone_id: int
    """The id of the `ClimateZone`."""

    schedule_id: ClimateZoneScheduleId
    """The id of the `ZoneSchedule`."""


@dataclass(slots=True, frozen=True)
class ScheduleAttributesEntry:
    """Additional attributes to map between a `ZoneSchedule` and a `scheduler.schedule`."""

    zone_id: int
    """The id of the `ClimateZone`."""

    schedule_id: int
    """The id of the `ZoneSchedule`."""

    schedule_entity_id: str
    """The entity id of the `scheduler.schedule`."""


class RemehaModbusStore(Store):
    """Store for the remeha_modbus integration."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict
    ):
        return old_data


class RemehaModbusStorage:
    """Storage for additional data for the remeha_modbus integration."""

    def __init__(self, store: RemehaModbusStore):
        """Create a new storage instance."""
        self._waiting_list: MutableMapping[UUID, WaitingListEntry] = {}
        """A list for zone schedule identifiers, waiting to be linked to a `scheduler.schedule`.

        The waiting list is not persisted into the backing file, but only in memory.
        """

        self._cache_by_entity_id: MutableMapping[str, ScheduleAttributesEntry] = {}
        self._cache_by_climate_key: MutableMapping[str, ScheduleAttributesEntry] = {}
        self._store = store

    def _climate_key(self, zone_id: int, schedule_id: ClimateZoneScheduleId) -> str:
        return f"{zone_id}.{schedule_id.value}"

    def add_to_waiting_list(self, uuid: UUID, zone_id: int, schedule_id: ClimateZoneScheduleId):
        """Add a new entry to the list of zone schedules waiting to be linked.

        If an equal entry exists on the waiting list, this method has no effect.

        Args:
            uuid (UUID): The unique identifier added to the list of tags in the `scheduler.schedule`.
            zone_id (int): The id of the related `ClimateZone`.
            schedule_id (ClimateZoneScheduleId): The id of the related `ZoneSchedule`.

        """

        if uuid not in self._waiting_list:
            self._waiting_list[uuid] = WaitingListEntry(
                uuid=uuid, zone_id=zone_id, schedule_id=schedule_id
            )

    def pop_from_waiting_list(self, uuid: UUID) -> WaitingListEntry | None:
        """Pops the entry with `uuid` from the waiting list.

        Args:
            uuid: The uuid of the `WaitingListEntry`.

        Returns:
            The waiting list entry, or `None` if no such entry exists.

        """
        return self._waiting_list.pop(uuid, None)

    async def async_load(self):
        """Load the data from the backing file."""

        data: dict = await self._store.async_load()
        attrs_by_climate_key: MutableMapping[str, ScheduleAttributesEntry] = {}
        attrs_by_entity_id: MutableMapping[str, ScheduleAttributesEntry] = {}

        if data is not None:
            for entry in data.get("schedule_attributes", {}):
                attrs_entry = ScheduleAttributesEntry(
                    zone_id=int(entry["zone_id"]),
                    schedule_id=int(entry["schedule_id"]),
                    schedule_entity_id=entry["schedule_entity_id"],
                )
                climate_key = self._climate_key(
                    zone_id=attrs_entry.zone_id,
                    schedule_id=ClimateZoneScheduleId(attrs_entry.schedule_id),
                )

                attrs_by_climate_key[climate_key] = attrs_entry
                attrs_by_entity_id[attrs_entry.schedule_entity_id] = attrs_entry

        self._cache_by_climate_key = attrs_by_climate_key
        self._cache_by_entity_id = attrs_by_entity_id

    async def async_save(self):
        """Save the current cache to the backing file."""

        await self._store.async_save(
            {"schedule_attributes": list(self._cache_by_climate_key.values())}
        )

    async def async_get_all(self) -> list[ScheduleAttributesEntry]:
        """Get all schedule attributes entries."""

        return list(self._cache_by_entity_id.values())

    async def async_remove_all(self):
        """Remove all entries from storage."""

        await self._store.async_remove()

        self._cache_by_climate_key = {}
        self._cache_by_entity_id = {}

    async def async_get_attributes_by_zone(
        self, zone_id: int, schedule_id: ClimateZoneScheduleId
    ) -> ScheduleAttributesEntry | None:
        """Get the schedule attributes for the given `schedule_id` of `ClimateZone` with `zone_id`.

        Args:
            zone_id (int): The id of the zone the schedule belongs to.
            schedule_id (ClimateZoneScheduleId): The id of the schedule within the zone.

        Returns:
            (ScheduleAttributesEntry | None) The requested schedule attributes, or `None` if no such attributes exist.

        """

        return self._cache_by_climate_key.get(
            self._climate_key(zone_id=zone_id, schedule_id=schedule_id)
        )

    async def async_get_attributes_by_entity_id(
        self, entity_id: str
    ) -> ScheduleAttributesEntry | None:
        """Get the schedule attributes having the given `entity_id`.

        Args:
            entity_id (str): The id of the related `scheduler.schedule` entity.

        Returns:
            (ScheduleAttributesEntry | None) The requested schedule attributes, or `None` if no such entity id exists.

        """

        return self._cache_by_entity_id.get(entity_id)

    async def async_upsert_schedule_attributes(
        self, zone_id: int, schedule_id: ClimateZoneScheduleId, schedule_entity_id: str
    ) -> ScheduleAttributesEntry:
        """Create a new, or update an existing `ScheduleAttributesEntry`.

        If created, the entry is stored before it is returned. If the entry exists, it is updated
        if `schedule_entity_id` is different.

        Args:
            zone_id (int): The id of the zone the schedule belongs to.
            schedule_id (ClimateZoneScheduleId): The id of the schedule within the zone.
            schedule_entity_id (str): The entity id of the related `scheduler.schedule`.

        """

        entry = ScheduleAttributesEntry(
            zone_id=zone_id, schedule_id=schedule_id.value, schedule_entity_id=schedule_entity_id
        )

        self._cache_by_climate_key[self._climate_key(zone_id=zone_id, schedule_id=schedule_id)] = (
            entry
        )
        self._cache_by_entity_id[schedule_entity_id] = entry
        await self.async_save()

        return entry

    async def async_remove_schedule_attributes(
        self, zone_id: int, schedule_id: ClimateZoneScheduleId
    ) -> bool:
        """Remove the attributes of the schedule in the given zone.

        Returns:
            bool: `True` if the store contents changed due to this removal, `False` otherwise.

        """

        entry = await self.async_get_attributes_by_zone(zone_id=zone_id, schedule_id=schedule_id)
        if entry is None:
            return False

        del self._cache_by_climate_key[self._climate_key(zone_id=zone_id, schedule_id=schedule_id)]
        del self._cache_by_entity_id[entry.schedule_entity_id]

        await self.async_save()
        return True
