"""Tests for NumberEntity instances in the Remeha Modbus integration."""

from unittest.mock import patch

import pytest
from homeassistant.components.number.const import DOMAIN as NumberDomain
from homeassistant.core import HomeAssistant

from .conftest import get_api, setup_platform


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climates(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test climates."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        # One DhwHysteresisEntity + one appliance-level RemehaTransitionSeasonNumber.
        assert len(hass.states.async_all(domain_filter="number")) == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_dhw_hysteresis(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test a single DhwHysteresisEntity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        hysteresis = hass.states.get("number.remeha_modbus_test_hub_dhw_hysteresis")
        assert hysteresis is not None
        assert hysteresis.state == "3.0"
        assert hysteresis.domain == "number"
        assert hysteresis.name == "Remeha Modbus test_hub dhw_hysteresis"

        # Update the state
        # Update some attributes
        await hass.services.async_call(
            domain=NumberDomain,
            service="set_value",
            service_data={
                "entity_id": hysteresis.entity_id,
                "value": 20.0,
            },
            blocking=True,
        )

        hysteresis = hass.states.get(hysteresis.entity_id)
        assert hysteresis is not None
        assert hysteresis.state == "20.0"


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_transition_season(hass: HomeAssistant, mock_modbus_client, mock_config_entry):
    """Test the appliance transition-season number entity (AP075)."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        transition = hass.states.get("number.remeha_modbus_test_hub_transition_season")
        assert transition is not None
        assert transition.state == "4.0"

        await hass.services.async_call(
            domain=NumberDomain,
            service="set_value",
            service_data={"entity_id": transition.entity_id, "value": 5.0},
            blocking=True,
        )

        transition = hass.states.get(transition.entity_id)
        assert transition is not None
        assert transition.state == "5.0"


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store_no_dhw_climate.json"], indirect=True)
async def test_dhw_hysteresis_unavailable(
    hass: HomeAssistant, mock_modbus_client, mock_config_entry
):
    """Test a single DhwHysteresisEntity."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        hysteresis = hass.states.get("number.remeha_modbus_test_hub_dhw_hysteresis")
        assert hysteresis is None
