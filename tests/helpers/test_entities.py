"""Test entities helper methods."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remeha_modbus.helpers.entities import integration_entities


async def test_integration_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test integration_entities function.

    The original source of this test is located at
    https://github.com/home-assistant/core/blob/2026.4.4/tests/helpers/template/test_init.py#L1821
    """
    # test entities for untitled config entry
    config_entry = MockConfigEntry(domain="mock", title="")
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create("sensor", "mock", "untitled", config_entry=config_entry)

    assert integration_entities(hass, "") == []

    # test entities for given config entry title
    config_entry = MockConfigEntry(domain="mock", title="Mock bridge 2")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor", "mock", "test", config_entry=config_entry
    )
    assert integration_entities(hass, "Mock bridge 2") == [entity_entry.entity_id]

    # test entities for given non unique config entry title
    config_entry = MockConfigEntry(domain="mock", title="Not unique")
    config_entry.add_to_hass(hass)
    entity_entry_not_unique_1 = entity_registry.async_get_or_create(
        "sensor", "mock", "not_unique_1", config_entry=config_entry
    )
    config_entry = MockConfigEntry(domain="mock", title="Not unique")
    config_entry.add_to_hass(hass)
    entity_entry_not_unique_2 = entity_registry.async_get_or_create(
        "sensor", "mock", "not_unique_2", config_entry=config_entry
    )
    assert integration_entities(hass, "Not unique") == [
        entity_entry_not_unique_1.entity_id,
        entity_entry_not_unique_2.entity_id,
    ]

    # test integration entities not in entity registry
    mock_entity = entity.Entity()
    mock_entity.hass = hass
    mock_entity.entity_id = "light.test_entity"
    mock_entity.platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="light",
        platform_name="entryless_integration",
        platform=None,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    await mock_entity.async_internal_added_to_hass()
    assert integration_entities(hass, "entryless_integration") == ["light.test_entity"]

    # Test non existing integration/entry title
    assert integration_entities(hass, "abc123") == []
