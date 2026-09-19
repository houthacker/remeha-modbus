"""Test component setup."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from custom_components.remeha_modbus import async_remove_config_entry_device
from custom_components.remeha_modbus.const import DOMAIN

from .conftest import setup_platform


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_remove_config_entry_device(hass: HomeAssistant, remeha_api, mock_config_entry):
    """Stale devices may be removed from the UI; devices still in use may not."""

    with patch(
        "custom_components.remeha_modbus.RemehaApi",
        new=lambda *args, **kwargs: remeha_api,
    ):
        await setup_platform(hass=hass, config_entry=mock_config_entry)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        remeha_devices = [
            device
            for device in device_registry.devices
            if any(domain == DOMAIN for domain, _ in device.identifiers)
        ]
        assert remeha_devices, "expected at least one remeha_modbus device"

        # A device the integration still provides must not be removable.
        for device in remeha_devices:
            assert await async_remove_config_entry_device(hass, mock_config_entry, device) is False

        # A stale device (its identifier is no longer known) may be removed.
        stale_device = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, "no-longer-present")},
        )
        assert await async_remove_config_entry_device(hass, mock_config_entry, stale_device) is True
