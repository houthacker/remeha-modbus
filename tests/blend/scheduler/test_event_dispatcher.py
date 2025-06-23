"""Tests for the EventDispatcher."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.blend.scheduler import EventDispatcher
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from tests.conftest import get_api, setup_platform


async def test_subscribe_to_entity_updates(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test that registering a new listener returns a unique unsubsribe function."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        entity_id: str = "climate.remeha_modbus_test_hub_dhw"
        dispatcher: EventDispatcher = EventDispatcher(hass=hass)

        def listener1(_):
            pass

        unsub1 = dispatcher.subscribe_to_entity_updates(entity_id=entity_id, listener=listener1)

        def listener2(_):
            pass

        unsub2 = dispatcher.subscribe_to_entity_updates(entity_id=entity_id, listener=listener2)

        assert callable(unsub1) and callable(unsub2)
        assert unsub1 is not unsub2


async def test_entity_update_listener_gets_called(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test that subscribers to entity updates are notified of updates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        entity_id: str = "climate.remeha_modbus_test_hub_dhw"
        dispatcher: EventDispatcher = EventDispatcher(hass=hass)

        parameters: dict = {"dhw_listener_calls": 0}

        def _dhw_listener(_):
            parameters["dhw_listener_calls"] = parameters["dhw_listener_calls"] + 1

        unsub = dispatcher.subscribe_to_entity_updates(entity_id=entity_id, listener=_dhw_listener)

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        dhw_zone = coordinator.get_climate(id=2)

        # Update the DHW climate by setting a new setpoint.
        await hass.services.async_call(
            domain="climate",
            service="set_temperature",
            service_data={"entity_id": entity_id, "temperature": dhw_zone.current_setpoint + 1},
            blocking=False,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

        assert parameters["dhw_listener_calls"] == 1
        unsub()

        # Update it again, the listener must not be called again.
        await hass.services.async_call(
            domain="climate",
            service="set_temperature",
            service_data={"entity_id": entity_id, "temperature": dhw_zone.current_setpoint - 1},
            blocking=False,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

        assert parameters["dhw_listener_calls"] == 1
