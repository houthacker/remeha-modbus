"""Platform for switches in the Remeha Modbus integration."""

import logging
from typing import Any, cast

from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    PRESET_ECO,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.components.climate.const import DOMAIN as ClimateDomain
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from propcache.api import cached_property

from custom_components.remeha_modbus.blend.scheduler.helpers import scheduler_is_installed
from custom_components.remeha_modbus.const import (
    DOMAIN,
    HEATPUMP_MANAGED_SCHEDULES,
    SWITCH_SCHEDULE_SYNC,
    UNEXPECTED_ACTION_ISSUE_URL,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.helpers.entities import get_climate_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensor entities based on the given config entry."""

    async_add_entities(
        [
            RemehaScheduleSynchronizationSwitch(SWITCH_SCHEDULE_SYNC, entry),
            RemehaHeatpumpManagedSchedulesSwitch(HEATPUMP_MANAGED_SCHEDULES, entry),
        ]
    )


class RemehaModbusSwitch(RestoreEntity, SwitchEntity):
    """A switch entity that is not backed by a modbus device.

    Its state is only stored in Home Assistant and defaults to
    False if unset by the user.
    """

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, name: str, config: ConfigEntry):
        """Create a new switch instance."""

        super().__init__()

        self._attr_name = name
        self._attr_unique_id = name
        self._config_entry = config

    @cached_property
    def translation_key(self) -> str:
        """Retrieve the translation key for this switch."""

        return cast(str, self.unique_id)

    @cached_property
    def available(self) -> bool:
        """Return whether this switch is available."""

        # Currently all switches require the scheduler-component integration to be installed.
        return super().available and scheduler_is_installed(self.hass)

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""

        self._attr_is_on = False
        self.async_write_ha_state()


class RemehaScheduleSynchronizationSwitch(RemehaModbusSwitch):
    """A `switch` entity that controls whether to sync time schedules.

    If set to 'on', the time schedules from the Remeha appliance are synchronized
    with the `scheduler` component. If the components is not installed, this switch
    is disabled.
    """

    async def async_added_to_hass(self):
        """Restore previous state or set to default ('off')."""
        await super().async_added_to_hass()

        prev_state = await self.async_get_last_state()
        self._attr_is_on = prev_state is not None and prev_state.state == STATE_ON


class RemehaHeatpumpManagedSchedulesSwitch(RemehaModbusSwitch):
    """A `switch` entity that controls whether the heat pump manages schedule execution.

    If set to 'on' (the default), the heat pump will manage time schedule execution.
    Using this default state enables the heat pump to use its own heating/cooling
    alrogithms, for example pre-heating an hour before the setpoint must be reached.
    Using the default state is the recommended setting.

    If set to 'off', the affected climate zones are put in a preset allowing external
    schedule management. If schedules are synchronized with the `scheduler` component,
    the presets will be set once a schedule timer expires. This effectively disables
    any heat pump heating/cooling algorithms like pre-heating for example. Therefore
    this setting is not recommended.
    """

    async def _async_switch_dhw_climates_to_eco_mode(self) -> dict[str, Any]:
        """Switches all DHW climate presets to ECO.

        This prevents the appliance from running time schedules, allowing time schedule
        management from Home Assistant directly.

        Returns:
            A dict of entity ids, mapped to their preset before switching to eco mode.
            This allows users to apply the issue fix that is proposed when disabling heat pump managed schedules.

        """

        prev_presets: dict[str, str] = {}
        coordinator: RemehaUpdateCoordinator = self._config_entry.runtime_data["coordinator"]
        for climate in coordinator.get_climates(lambda c: c.is_domestic_hot_water()):
            entity_id = get_climate_entity_id(self.hass, climate)
            state = self.hass.states.get(entity_id)

            # get_climate_entity_id already raises an exception if the entity doesn't exst.
            if state is None:
                _LOGGER.warning(
                    "Cannot switch climate %s to eco mode: its state cannot be retrieved.",
                    entity_id,
                )
                continue

            prev_presets[entity_id] = state.attributes[ATTR_PRESET_MODE]

            _LOGGER.debug(
                "Setting preset_mode of %s to %s to prevent scheduling conflicts between heat pump and Home Assistant.",
                entity_id,
                PRESET_ECO,
            )
            await self.hass.services.async_call(
                domain=ClimateDomain,
                service=SERVICE_SET_PRESET_MODE,
                service_data={"preset_mode": PRESET_ECO},
                target={"entity_id": entity_id},
            )

        return prev_presets

    async def async_added_to_hass(self):
        """Restore previous state or set to default ('on')."""
        await super().async_added_to_hass()

        prev_state = await self.async_get_last_state()
        self._attr_is_on = prev_state.state == STATE_ON if prev_state is not None else True

        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""

        await super().async_turn_off()

        # Put all DHW climates in eco mode and create an issue.
        undo_presets = await self._async_switch_dhw_climates_to_eco_mode()

        ir.async_create_issue(
            hass=self.hass,
            domain=DOMAIN,
            data={"switch": self.entity_id, **undo_presets},
            issue_id="heatpump_managed_schedules_off",
            is_fixable=True,
            is_persistent=True,
            issue_domain=DOMAIN,
            learn_more_url=UNEXPECTED_ACTION_ISSUE_URL,
            severity=ir.IssueSeverity.WARNING,
            translation_key="heatpump_managed_schedules_turned_off",
        )
