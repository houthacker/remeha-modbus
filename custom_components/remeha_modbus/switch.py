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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from propcache.api import cached_property

from custom_components.remeha_modbus.api import DeviceInstance, RemehaApi
from custom_components.remeha_modbus.api.appliance import CoolingType
from custom_components.remeha_modbus.blend.scheduler.helpers import scheduler_is_installed
from custom_components.remeha_modbus.const import (
    DOMAIN,
    HEATPUMP_MANAGED_SCHEDULES,
    ISSUE_HEATPUMP_MANAGED_SCHEDULES_LEARN_MORE_URL,
    ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF,
    SWITCH_SCHEDULE_SYNC,
    MetaRegisters,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.helpers.entities import get_climate_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the switch entities based on the given config entry."""

    api: RemehaApi = entry.runtime_data["api"]
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    mainboards: list[DeviceInstance] = coordinator.get_devices(lambda device: device.is_mainboard())
    parent_device_id: int | None = mainboards[0].id if mainboards else None

    async_add_entities(
        [
            RemehaScheduleSynchronizationSwitch(SWITCH_SCHEDULE_SYNC, entry),
            RemehaHeatpumpManagedSchedulesSwitch(HEATPUMP_MANAGED_SCHEDULES, entry),
            RemehaChEnabledSwitch(
                api=api, coordinator=coordinator, parent_device_id=parent_device_id
            ),
            RemehaCoolingEnabledSwitch(
                api=api, coordinator=coordinator, parent_device_id=parent_device_id
            ),
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
                service_data={ATTR_PRESET_MODE: PRESET_ECO},
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
            issue_id=ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF,
            is_fixable=True,
            is_persistent=False,
            issue_domain=DOMAIN,
            learn_more_url=ISSUE_HEATPUMP_MANAGED_SCHEDULES_LEARN_MORE_URL,
            severity=ir.IssueSeverity.WARNING,
            translation_key="heatpump_managed_schedules_turned_off",
        )


class RemehaApplianceSwitch(CoordinatorEntity[RemehaUpdateCoordinator], SwitchEntity):
    """Base class for appliance-level switches backed by a modbus register."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        api: RemehaApi,
        coordinator: RemehaUpdateCoordinator,
        parent_device_id: int | None,
        name: str,
    ):
        """Create a new appliance switch."""

        super().__init__(coordinator=coordinator)

        self._api = api
        self._parent_device_id = parent_device_id
        self._attr_name = name
        self._attr_unique_id = name

    @property
    def translation_key(self) -> str:
        """The translation key."""

        return cast(str, self.name)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device this switch belongs to.

        Returns
            `DeviceInfo | None`: The device info, or `None` if this switch is not owned by any device.

        """

        if self._parent_device_id is None:
            return None

        device_instance: DeviceInstance | None = self.coordinator.get_device(
            id=self._parent_device_id
        )
        return (
            DeviceInfo(
                identifiers={(DOMAIN, str(device_instance.article_number))},
                hw_version=f"HW{device_instance.hw_version[0]:02d}.{device_instance.hw_version[1]:02d}",
                manufacturer="Remeha",
                model=str(device_instance.board_category),
                sw_version=f"SW{device_instance.sw_version[0]:02d}.{device_instance.sw_version[1]:02d}",
            )
            if device_instance is not None
            else None
        )


class RemehaChEnabledSwitch(RemehaApplianceSwitch):
    """Switch that enables/disables central heating demand processing (parameter AP016)."""

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create the central heating switch."""

        super().__init__(
            api=api,
            coordinator=coordinator,
            parent_device_id=parent_device_id,
            name="ch_enabled",
        )

    @property
    def is_on(self) -> bool:
        """Return whether central heating demand processing is enabled."""

        return self.coordinator.get_appliance().ch_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable central heating demand processing."""

        await self._async_set_enabled(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable central heating demand processing."""

        await self._async_set_enabled(enabled=False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        await self._api.async_write_variable(variable=MetaRegisters.CH_ENABLED, value=enabled)

        # Reflect the change immediately, until the next coordinator refresh.
        self.coordinator.get_appliance().ch_enabled = enabled
        self.async_write_ha_state()


class RemehaCoolingEnabledSwitch(RemehaApplianceSwitch):
    """Switch that enables/disables cooling (parameter AP028).

    Turning the switch on selects active cooling; turning it off disables cooling.
    """

    def __init__(
        self, api: RemehaApi, coordinator: RemehaUpdateCoordinator, parent_device_id: int | None
    ):
        """Create the cooling switch."""

        super().__init__(
            api=api,
            coordinator=coordinator,
            parent_device_id=parent_device_id,
            name="cooling_enabled",
        )

    @property
    def is_on(self) -> bool:
        """Return whether cooling is enabled."""

        return self.coordinator.get_appliance().cooling_type is not CoolingType.OFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable active cooling."""

        await self._async_set_cooling(CoolingType.ACTIVE_COOLING)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable cooling."""

        await self._async_set_cooling(CoolingType.OFF)

    async def _async_set_cooling(self, cooling_type: CoolingType) -> None:
        await self._api.async_write_variable(
            variable=MetaRegisters.COOLING_ENABLED, value=cooling_type
        )

        self.coordinator.get_appliance().cooling_type = cooling_type
        self.async_write_ha_state()
