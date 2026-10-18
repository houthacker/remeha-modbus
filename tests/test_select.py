"""Tests for select entities."""

from unittest.mock import MagicMock, patch

import pytest
from aio_remeha_modbus.gtw08.system_discovery_table import DeviceBoard, DeviceBoardType
from homeassistant.components.select.const import DOMAIN as SelectDomain
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from custom_components.remeha_modbus.const import DOMAIN
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

from .conftest import setup_platform

# Entities are looked up by unique id, since their entity id depends on the translated name.
SILENT_MODE = "appliance_silent_mode"

CU_HW_SELECTS = [
    "digital_input_1_configuration",
    "digital_input_2_configuration",
    "digital_input_1_contact_logic",
    "digital_input_2_contact_logic",
]

DIGITAL_INPUT_CONFIGURATION_OPTIONS = ["off", "smart_grid", "release_compressor", "release_backup"]
CONTACT_LOGIC_OPTIONS = ["normally_open", "normally_closed"]


def _entity_id(hass: HomeAssistant, unique_id: str) -> str:
    """Return the entity id of the select entity with the given unique id."""

    entity_id = er.async_get(hass).async_get_entity_id(SelectDomain, DOMAIN, unique_id)
    assert entity_id is not None

    return entity_id


def _assert_cu_hw_selects(hass: HomeAssistant, expect_cu_hw_selects: bool):
    """Assert which select entities have been added."""

    entity_registry = er.async_get(hass)

    assert hass.states.get(_entity_id(hass, SILENT_MODE)) is not None

    for unique_id in CU_HW_SELECTS:
        entity_id = entity_registry.async_get_entity_id(SelectDomain, DOMAIN, unique_id)
        if expect_cu_hw_selects:
            assert entity_id is not None
            assert hass.states.get(entity_id) is not None
        else:
            assert entity_id is None


async def test_cu_hw_selects_not_added(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that the digital input selects are not added if the mainboard is not CU_HW."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        mainboard = coordinator.get_devices(lambda board: board.is_mainboard())[0]
        assert mainboard.board_category is not None
        assert mainboard.board_category.type is not DeviceBoardType.CU_HW

        assert len(hass.states.async_all(domain_filter=SelectDomain)) == 1
        _assert_cu_hw_selects(hass, expect_cu_hw_selects=False)


@pytest.mark.parametrize(
    "mainboards",
    [
        pytest.param([], id="no_mainboard"),
        pytest.param([MagicMock(spec=DeviceBoard, board_category=None)], id="no_category"),
    ],
)
@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_cu_hw_selects_not_added_without_mainboard_category(
    hass: HomeAssistant,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    mainboards: list[DeviceBoard],
):
    """Test that the digital input selects are not added if the mainboard type is unknown."""

    with (
        patch(
            "aio_remeha_modbus.gtw08.GTW08",
            new=lambda *args, **kwargs: remeha_api,
        ),
        patch(
            "custom_components.remeha_modbus.coordinator.RemehaUpdateCoordinator.get_devices",
            return_value=mainboards,
        ),
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all(domain_filter=SelectDomain)) == 1
        _assert_cu_hw_selects(hass, expect_cu_hw_selects=False)


@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_cu_hw_selects(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test the digital input selects of a heat pump boiler (CU_HW mainboard)."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        mainboard = coordinator.get_devices(lambda board: board.is_mainboard())[0]
        assert mainboard.board_category is not None
        assert mainboard.board_category.type is DeviceBoardType.CU_HW

        assert len(hass.states.async_all(domain_filter=SelectDomain)) == 5
        _assert_cu_hw_selects(hass, expect_cu_hw_selects=True)

        # Registers 9009 and 9010 are 0 in the fixture, registers 9011 and 9012 are NaN (0xff).
        for unique_id, expected_state, expected_options in [
            (CU_HW_SELECTS[0], "off", DIGITAL_INPUT_CONFIGURATION_OPTIONS),
            (CU_HW_SELECTS[1], "off", DIGITAL_INPUT_CONFIGURATION_OPTIONS),
            (CU_HW_SELECTS[2], STATE_UNKNOWN, CONTACT_LOGIC_OPTIONS),
            (CU_HW_SELECTS[3], STATE_UNKNOWN, CONTACT_LOGIC_OPTIONS),
        ]:
            state = hass.states.get(_entity_id(hass, unique_id))
            assert state is not None
            assert state.state == expected_state
            assert state.attributes["options"] == expected_options


@pytest.mark.parametrize(
    ("unique_id", "option"),
    [
        (CU_HW_SELECTS[0], "smart_grid"),
        (CU_HW_SELECTS[1], "release_backup"),
        (CU_HW_SELECTS[2], "normally_closed"),
        (CU_HW_SELECTS[3], "normally_open"),
    ],
)
@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_cu_hw_select_option(
    hass: HomeAssistant,
    *,
    remeha_api,
    mock_config_entry,
    remeha_modbus_unit,
    unique_id: str,
    option: str,
):
    """Test selecting an option on the digital input selects."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        entity_id = _entity_id(hass, unique_id)
        await hass.services.async_call(
            domain=SelectDomain,
            service="select_option",
            service_data={"entity_id": entity_id, "option": option},
            blocking=True,
        )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == option

        # The option must have been written to the appliance.
        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        await coordinator.async_refresh()
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == option


@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_cu_hw_select_invalid_option(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit
):
    """Test that selecting an unsupported option is rejected."""

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        entity_id = _entity_id(hass, CU_HW_SELECTS[0])
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                domain=SelectDomain,
                service="select_option",
                service_data={"entity_id": entity_id, "option": "normally_open"},
                blocking=True,
            )

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"


@pytest.mark.parametrize("language", ["en", "nl"])
@pytest.mark.parametrize("remeha_modbus_unit", ["azorra_ace_store.json"], indirect=True)
async def test_select_translations(
    hass: HomeAssistant, remeha_api, mock_config_entry, remeha_modbus_unit, language: str
):
    """Test that the name and every option of each select entity is translated."""

    await hass.config.async_update(language=language)

    with patch(
        "aio_remeha_modbus.gtw08.GTW08",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(
            hass=hass, config_entry=mock_config_entry, remeha_modbus_unit=remeha_modbus_unit
        )
        await hass.async_block_till_done()

        translations = await async_get_translations(hass, language, "entity", {DOMAIN})
        entity_registry = er.async_get(hass)

        missing: list[str] = []
        for unique_id in [SILENT_MODE, *CU_HW_SELECTS]:
            entity_id = _entity_id(hass, unique_id)
            entry = entity_registry.async_get(entity_id)
            state = hass.states.get(entity_id)
            assert entry is not None
            assert entry.translation_key is not None
            assert state is not None

            prefix = f"component.{DOMAIN}.entity.{SelectDomain}.{entry.translation_key}"
            missing.extend(
                key
                for key in [
                    f"{prefix}.name",
                    *(f"{prefix}.state.{option}" for option in state.attributes["options"]),
                ]
                if key not in translations
            )

            # The entity name must be the translated name.
            name = translations.get(f"{prefix}.name")
            assert state.attributes["friendly_name"] == f"Remeha Modbus test_hub {name}"

        assert missing == []
