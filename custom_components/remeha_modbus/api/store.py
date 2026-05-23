"""Storage for the Remeha Modbus integration."""

import logging
from collections.abc import MutableMapping
from typing import TypedDict
from uuid import UUID

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from pydantic.dataclasses import dataclass

from custom_components.remeha_modbus.blend.scheduler.const import ZoneScheduleUID
from custom_components.remeha_modbus.const import (
    STORAGE_FILE_KEY,
    STORAGE_MAJOR_VERSION,
    STORAGE_MINOR_VERSION,
    ClimateZoneScheduleId,
    Weekday,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class WaitingListEntry:
    """Entry for the waiting list of schedules to be linked."""

    uuid: UUID
    """The uuid that is listed in the tags of the `scheduler.schedule`."""

    zone_schedule_uid: ZoneScheduleUID
    """The unique identification of the `ZoneSchedule`."""


class _ScheduleAttributesEntry(TypedDict):
    """Storage type for ScheduleAttributes."""

    zone_id: int

    schedule_id: int

    weekday: str

    schedule_entity_id: str


@dataclass(slots=True, frozen=True)
class ScheduleAttributes:
    """Additional attributes to map between a `ZoneSchedule` and a `scheduler.schedule`."""

    zone_id: int
    """The id of the `ClimateZone`."""

    schedule_id: int
    """The id of the `ZoneSchedule`."""

    weekday: Weekday
    """The Weekday of the `ZoneSchedule`"""

    schedule_entity_id: str
    """The entity id of the `scheduler.schedule`."""


def _to_attrs_entry(entry: ScheduleAttributes) -> _ScheduleAttributesEntry:
    """Create a new _ScheduleAttributesEntry from this instance."""
    return _ScheduleAttributesEntry(
        zone_id=entry.zone_id,
        schedule_id=entry.schedule_id,
        weekday=entry.weekday.name,
        schedule_entity_id=entry.schedule_entity_id,
    )


def _from_attrs_entry(entry: _ScheduleAttributesEntry) -> ScheduleAttributes:
    """Create a new `ScheduleAttributes` from an entry."""

    return ScheduleAttributes(
        zone_id=entry["zone_id"],
        schedule_id=entry["schedule_id"],
        weekday=Weekday[entry["weekday"]],
        schedule_entity_id=entry["schedule_entity_id"],
    )


class RemehaModbusStoreType(TypedDict):
    """Type definition for RemehaModbusStore."""

    schedule_attributes: list[_ScheduleAttributesEntry]


class RemehaModbusStore(Store[RemehaModbusStoreType]):
    """Store for the remeha_modbus integration."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict
    ):
        return old_data


class RemehaModbusStorage:
    """Storage for additional data for the remeha_modbus integration."""

    def __init__(self, hass: HomeAssistant):
        """Create a new storage instance."""
        self._hass: HomeAssistant = hass
        self._linking_waiting_list: MutableMapping[UUID, WaitingListEntry] = {}
        """A list for zone schedule identifiers, waiting to be linked to a `scheduler.schedule`.

        The waiting list is not persisted into the backing file, but only in memory.
        """

        self._modbus_sourced_updates: list[str] = []
        """A list containing `scheduler.schedule` entity ids that have been updated through the modbus interface.

        This list is only persisted in memory.
        """

        self._cache_by_entity_id: MutableMapping[str, ScheduleAttributes] = {}
        self._cache_by_climate_key: MutableMapping[str, ScheduleAttributes] = {}
        self._store = RemehaModbusStore(
            hass=hass,
            version=STORAGE_MAJOR_VERSION,
            minor_version=STORAGE_MINOR_VERSION,
            key=STORAGE_FILE_KEY,
        )

    def add_to_linking_waiting_list(self, uuid: UUID, zone_schedule_uid: ZoneScheduleUID):
        """Add a new entry to the list of zone schedules waiting to be linked.

        If an equal entry exists on the waiting list, this method has no effect.

        Args:
            uuid (UUID): The unique identifier added to the list of tags in the `scheduler.schedule`.
            zone_schedule_uid (ZoneScheduleUID): The unique identifier of the `ZoneSchedule`.

        """

        if uuid not in self._linking_waiting_list:
            self._linking_waiting_list[uuid] = WaitingListEntry(
                uuid=uuid, zone_schedule_uid=zone_schedule_uid
            )

    def remove_from_linking_waiting_list(self, uuid: UUID) -> WaitingListEntry | None:
        """Pops the entry with `uuid` from the waiting list.

        Args:
            uuid: The uuid of the `WaitingListEntry`.

        Returns:
            The waiting list entry, or `None` if no such entry exists.

        """
        return self._linking_waiting_list.pop(uuid, None)

    def notify_of_modbus_sourced_update(self, entity_id: str):
        """Add a new entry to the list of expected schedule updates."""

        if entity_id not in self._modbus_sourced_updates:
            self._modbus_sourced_updates.append(entity_id)

    def is_modbus_sourced_update(self, entity_id: str) -> bool:
        """Return whether the update of `entity_id` originated from modbus."""

        if entity_id in self._modbus_sourced_updates:
            self._modbus_sourced_updates.remove(entity_id)
            return True

        return False

    async def async_load(self):
        """Load the data from the backing file."""

        data: RemehaModbusStoreType | None = await self._store.async_load()
        attrs_by_climate_key: MutableMapping[str, ScheduleAttributes] = {}
        attrs_by_entity_id: MutableMapping[str, ScheduleAttributes] = {}

        if data is not None:
            for attrs_entry in data.get("schedule_attributes", {}):
                attrs = _from_attrs_entry(attrs_entry)
                climate_key = str(
                    ZoneScheduleUID(
                        zone_id=attrs_entry["zone_id"],
                        schedule_id=ClimateZoneScheduleId(attrs_entry["schedule_id"]),
                        weekday=Weekday[attrs_entry["weekday"]],
                    )
                )

                attrs_by_climate_key[climate_key] = attrs
                attrs_by_entity_id[attrs_entry["schedule_entity_id"]] = attrs

        self._cache_by_climate_key = attrs_by_climate_key
        self._cache_by_entity_id = attrs_by_entity_id

    async def async_save(self):
        """Save the current cache to the backing file."""

        await self._store.async_save(
            RemehaModbusStoreType(
                schedule_attributes=[
                    _to_attrs_entry(attrs) for attrs in self._cache_by_climate_key.values()
                ]
            )
        )

    async def async_get_all(self) -> list[ScheduleAttributes]:
        """Get all schedule attributes entries."""

        return list(self._cache_by_entity_id.values())

    async def async_remove_all(self):
        """Remove all entries from storage."""

        await self._store.async_remove()

        self._cache_by_climate_key = {}
        self._cache_by_entity_id = {}

    async def async_get_attributes_by_zone(self, uid: ZoneScheduleUID) -> ScheduleAttributes | None:
        """Get the schedule attributes for the given `uid`.

        Args:
            uid: The unique identity of the related climate schedule.

        Returns:
            (ScheduleAttributes | None) The requested schedule attributes, or `None` if no such attributes exist.

        """

        return self._cache_by_climate_key.get(str(uid))

    async def async_get_attributes_by_entity_id(self, entity_id: str) -> ScheduleAttributes | None:
        """Get the schedule attributes having the given `entity_id`.

        Args:
            entity_id (str): The id of the related `scheduler.schedule` entity.

        Returns:
            (ScheduleAttributes | None) The requested schedule attributes, or `None` if no such entity id exists.

        """

        return self._cache_by_entity_id.get(entity_id)

    async def async_upsert_schedule_attributes(
        self, uid: ZoneScheduleUID, schedule_entity_id: str
    ) -> ScheduleAttributes:
        """Create a new, or update an existing `ScheduleAttributesEntry`.

        If created, the entry is stored before it is returned. If the entry exists, it is updated
        if `schedule_entity_id` is different.

        Note: this method does not check if `schedule_entity_id` actually belongs to a
        `scheduler.schedule`. Instead, it assumes that callers have already done that.

        Args:
            uid (ZoneScheduleUID): The unique identification of the zone schedule.
            schedule_entity_id (str): The `entity_id` of the related `scheduler.schedule`.

        Returns:
            `ScheduleAttributesEntry` The upserted entry.

        """

        entry = ScheduleAttributes(
            zone_id=uid.zone_id,
            schedule_id=uid.schedule_id.value,
            weekday=uid.weekday,
            schedule_entity_id=schedule_entity_id,
        )

        self._cache_by_climate_key[str(uid)] = entry
        self._cache_by_entity_id[schedule_entity_id] = entry
        await self.async_save()

        return entry

    async def async_remove_schedule_attributes(self, uid: ZoneScheduleUID) -> bool:
        """Remove the attributes of the schedule in the given zone.

        Args:
            uid (ZoneScheduleUID): The unique identification of the zone schedule.

        Returns:
            bool: `True` if the store contents changed due to this removal, `False` otherwise.

        """

        entry = await self.async_get_attributes_by_zone(uid=uid)
        if entry is None:
            return False

        del self._cache_by_climate_key[str(uid)]
        del self._cache_by_entity_id[entry.schedule_entity_id]

        await self.async_save()
        return True
