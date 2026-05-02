"""Platform for switches in the Remeha Modbus integration."""

from typing import Final, cast

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from remeha_modbus.blend.scheduler.helpers import scheduler_is_installed
from remeha_modbus.const import SWITCH_SCHEDULE_SYNC

DESCRIPTIONS: Final[list[SwitchEntityDescription]] = [
    SwitchEntityDescription(key=SWITCH_SCHEDULE_SYNC, name=SWITCH_SCHEDULE_SYNC)
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the sensor entities based on the given config entry."""

    async_add_entities(
        [RemehaModbusSwitch(name=cast(str, description.name)) for description in DESCRIPTIONS]
    )


class RemehaModbusSwitch(RestoreEntity, SwitchEntity):
    """A switch entity that is not backed by a modbus device.

    Its state is only stored in Home Assistant.
    """

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, name: str):
        """Create a new switch instance."""

        super().__init__()

        self._attr_name = name
        self._attr_unique_id = name

    @property
    def translation_key(self) -> str:
        """The translation key for this switch."""

        return cast(str, self.name)

    @property
    def available(self) -> bool:
        """Return whether this switch is available."""

        if self._attr_name == SWITCH_SCHEDULE_SYNC:
            return super().available and scheduler_is_installed(self.hass)

        return super().available

    async def async_added_to_hass(self):
        """Post process after this entity has been added to hass."""
        await super().async_added_to_hass()

        prev_state = await self.async_get_last_state()
        self._attr_is_on = prev_state.state == "on" if prev_state is not None else False

        self.async_schedule_update_ha_state(True)

    def turn_on(self, **kwargs):
        """Turn the switch on."""

        self._attr_is_on = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""

        self._attr_is_on = False
