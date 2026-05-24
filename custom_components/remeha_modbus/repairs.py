"""Repairs for Remeha Modbus."""

from typing import Any

import voluptuous as vol
from homeassistant.components.homeassistant.const import SERVICE_HOMEASSISTANT_RESTART
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


class RestartRequiredFixFlow(RepairsFlow):
    """Implementation of the restart repair fix."""

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the initial step."""

        return await self.async_step_confirm_restart()

    async def async_step_confirm_restart(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Allow the user to restart HA."""

        if user_input is not None:
            await self.hass.services.async_call(
                domain=HA_DOMAIN, service=SERVICE_HOMEASSISTANT_RESTART
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm_restart", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None = None,
    *args: Any,
    **kwargs: Any,
):
    """Create the restart flow."""

    if issue_id is not None and issue_id.startswith("restart_required"):
        return RestartRequiredFixFlow()

    return None
