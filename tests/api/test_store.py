"""Tests for the RemehaModbusStore."""

from uuid import UUID
from uuid import uuid4 as UUIDv4

from custom_components.remeha_modbus.api import (
    RemehaModbusStorage,
    RemehaModbusStore,
    ScheduleAttributesEntry,
    WaitingListEntry,
)
from custom_components.remeha_modbus.const import ClimateZoneScheduleId


def test_waiting_list(test_store: RemehaModbusStore):
    """Test that an entry can be added and popped from the waiting list."""

    storage = RemehaModbusStorage(store=test_store)

    uuid: UUID = UUIDv4()
    storage.add_to_waiting_list(uuid=uuid, zone_id=1, schedule_id=ClimateZoneScheduleId.SCHEDULE_3)

    assert storage.pop_from_waiting_list(uuid=uuid) == WaitingListEntry(
        uuid=uuid, zone_id=1, schedule_id=ClimateZoneScheduleId.SCHEDULE_3
    )


async def test_get_all_from_empty_store(test_store: RemehaModbusStore):
    """Test that retrieving all entries from an empty store returns an empty list."""

    assert await RemehaModbusStorage(store=test_store).async_get_all() == []


async def test_remove_all(test_store: RemehaModbusStore):
    """Test that removing all entries and then retrieving them back from storage returns an empty list."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=str(UUIDv4())
        )

    assert len(await storage.async_get_all()) == len(ClimateZoneScheduleId)

    await storage.async_remove_all()
    await storage.async_load()

    assert len(await storage.async_get_all()) == 0


async def test_get_attributes_by_entity_id(test_store: RemehaModbusStore):
    """Test the retrieval of entries by their entity_id."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=f"entity_{schedule_id.value}"
        )

    entity_id: str = f"entity_{ClimateZoneScheduleId.SCHEDULE_3.value}"
    assert await storage.async_get_attributes_by_entity_id(
        entity_id=entity_id
    ) == ScheduleAttributesEntry(
        zone_id=1, schedule_id=ClimateZoneScheduleId.SCHEDULE_3.value, schedule_entity_id=entity_id
    )


async def test_get_attributes_by_zone(test_store: RemehaModbusStore):
    """Test the retrieval of entries by their zone."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=f"entity_{schedule_id.value}"
        )

    assert await storage.async_get_attributes_by_zone(
        zone_id=1, schedule_id=ClimateZoneScheduleId.SCHEDULE_3
    ) == ScheduleAttributesEntry(
        zone_id=1,
        schedule_id=ClimateZoneScheduleId.SCHEDULE_3.value,
        schedule_entity_id=f"entity_{ClimateZoneScheduleId.SCHEDULE_3.value}",
    )


async def test_load_store(test_store: RemehaModbusStore):
    """Test loading the store contents from its backing file."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=f"entity_{schedule_id.value}"
        )

    await storage.async_load()

    # Inserted data must still be available
    for schedule_id in ClimateZoneScheduleId:
        assert (
            await storage.async_get_attributes_by_entity_id(f"entity_{schedule_id.value}")
            is not None
        )


async def test_remove_schedule_attributes(test_store: RemehaModbusStore):
    """Test that removing an entry does not touch the other entries."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=f"entity_{schedule_id.value}"
        )

    await storage.async_remove_schedule_attributes(
        zone_id=1, schedule_id=ClimateZoneScheduleId.SCHEDULE_2
    )

    assert len(await storage.async_get_all()) == len(ClimateZoneScheduleId) - 1


async def test_remove_non_existing_entry(test_store: RemehaModbusStore):
    """Test removing a non-existing entry has no effect."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=f"entity_{schedule_id.value}"
        )

    assert len(await storage.async_get_all()) == len(ClimateZoneScheduleId)

    assert (
        await storage.async_remove_schedule_attributes(
            zone_id=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_1
        )
        is False
    )

    assert len(await storage.async_get_all()) == len(ClimateZoneScheduleId)


async def test_migrate_store(test_store: RemehaModbusStore):
    """Test store migration."""

    storage = RemehaModbusStorage(store=test_store)

    # Insert some data
    for schedule_id in ClimateZoneScheduleId:
        await storage.async_upsert_schedule_attributes(
            zone_id=1, schedule_id=schedule_id, schedule_entity_id=f"entity_{schedule_id.value}"
        )

    expected_length = len(ClimateZoneScheduleId)
    assert len(await storage.async_get_all()) == expected_length

    migrated_storage = RemehaModbusStorage(
        store=RemehaModbusStore(
            hass=test_store.hass,
            version=test_store.version,
            minor_version=test_store.minor_version + 1,
            key=test_store.key,
        )
    )
    await migrated_storage.async_load()

    assert len(await migrated_storage.async_get_all()) == expected_length
