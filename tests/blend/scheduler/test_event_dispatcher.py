"""Tests for the EventDispatcher."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.remeha_modbus.api import Timeslot, TimeslotSetpointType, ZoneSchedule
from custom_components.remeha_modbus.blend.scheduler import EventDispatcher
from custom_components.remeha_modbus.const import WEEKDAY_TO_MODBUS_VARIABLE, Weekday
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from tests.conftest import get_api, setup_platform


async def test_subscribe_to_zone_schedule_updates(
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

        dispatcher: EventDispatcher = EventDispatcher(hass=hass)

        def listener1(_):
            pass

        unsub1 = dispatcher.subscribe_to_zone_schedule_updates(listener=listener1)

        def listener2(_):
            pass

        unsub2 = dispatcher.subscribe_to_zone_schedule_updates(listener=listener2)

        assert callable(unsub1) and callable(unsub2)
        assert unsub1 is not unsub2


async def test_zone_schedule_update_listener_gets_called(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test that subscribers to zone schedule updates are notified of updates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        dispatcher: EventDispatcher = mock_config_entry.runtime_data["event_dispatcher"]

        parameters: dict = {"dhw_listener_calls": 0}

        def _dhw_listener(_):
            parameters["dhw_listener_calls"] = parameters["dhw_listener_calls"] + 1

        # Subscribe to zone schedule updates
        unsub = dispatcher.subscribe_to_zone_schedule_updates(listener=_dhw_listener)

        coordinator: RemehaUpdateCoordinator = mock_config_entry.runtime_data["coordinator"]
        dhw_zone = coordinator.get_climate(id=2)

        # Update the current zone schedule.
        schedule = dhw_zone.current_schedule[Weekday.MONDAY]
        ts_0 = schedule.time_slots[0]
        updated_schedule = ZoneSchedule(
            id=schedule.id,
            zone_id=schedule.zone_id,
            day=schedule.day,
            time_slots=[
                Timeslot(
                    setpoint_type=(
                        TimeslotSetpointType.COMFORT
                        if ts_0.setpoint_type is TimeslotSetpointType.ECO
                        else TimeslotSetpointType.ECO
                    ),
                    activity=ts_0.activity,
                    switch_time=ts_0.switch_time,
                ),
                *[
                    Timeslot(
                        setpoint_type=ts.setpoint_type,
                        activity=ts.activity,
                        switch_time=ts.switch_time,
                    )
                    for ts in schedule.time_slots[1:]
                ],
            ],
        )

        # Write to modbus using the API, to simulate a backend-initiated schedule update.
        await api.async_write_variable(
            variable=WEEKDAY_TO_MODBUS_VARIABLE[updated_schedule.day],
            value=updated_schedule,
            offset=api.get_zone_register_offset(zone=updated_schedule.zone_id)
            + api.get_schedule_register_offset(schedule=updated_schedule.id),
        )
        await coordinator.async_refresh()
        await hass.async_block_till_done(wait_background_tasks=True)

        assert parameters["dhw_listener_calls"] == 1
        unsub()

        # Update it again, the listener must not be called again after unsubscribing.
        await api.async_write_variable(
            variable=WEEKDAY_TO_MODBUS_VARIABLE[schedule.day],
            value=schedule,
            offset=api.get_zone_register_offset(zone=schedule.zone_id)
            + api.get_schedule_register_offset(schedule=schedule.id),
        )
        await coordinator.async_refresh()
        await hass.async_block_till_done(wait_background_tasks=True)

        assert parameters["dhw_listener_calls"] == 1
