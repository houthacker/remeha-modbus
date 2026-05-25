"""Repairs for Remeha Modbus."""

import logging
from typing import Any, cast

import voluptuous as vol
from homeassistant.components.climate.const import DOMAIN as ClimateDomain
from homeassistant.components.climate.const import SERVICE_SET_PRESET_MODE
from homeassistant.components.homeassistant.const import SERVICE_HOMEASSISTANT_RESTART
from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.switch.const import DOMAIN as SwitchDomain
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from custom_components.remeha_modbus.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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


class UndoManualScheduleExecutionFixFlow(RepairsFlow):
    """Flow to reset the schedule handling to be handled by the heat pump."""

    def __init__(self, issue_id: str) -> None:
        """Create a new instance."""
        super().__init__()

        self.issue_id = issue_id

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the initial step."""

        return await self.async_step_confirm_undo()

    async def async_step_confirm_undo(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Have the user confirm whether they want to reset the schedule handling method."""

        if user_input is not None:
            registry = ir.async_get(self.hass)
            issue = registry.async_get_issue(domain=DOMAIN, issue_id=self.issue_id)

            if issue is None:
                _LOGGER.warning(
                    "Cannot undo previous action: issue with id %s not found", self.issue_id
                )
            elif issue.data is None:
                _LOGGER.warning("Cannot undo previous action: issue data is missing.")
            else:
                switch_entity = cast(str, issue.data["switch"])

                # Let the heat pump manage schhedule execution
                await self.hass.services.async_call(
                    domain=SwitchDomain, service="turn_on", target={"entity_id": switch_entity}
                )

                # Set the preset mode of the related climates.
                for k, v in issue.data.items():
                    if k != "switch":
                        await self.hass.services.async_call(
                            domain=ClimateDomain,
                            service=SERVICE_SET_PRESET_MODE,
                            service_data={"preset_mode": v},
                            target={"entity_id": k},
                        )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="confirm_undo", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None = None,
    *args: Any,
    **kwargs: Any,
):
    """Create the correct fix flow, based on issue_id."""

    if issue_id is None:
        return None

    if issue_id.startswith("restart_required"):
        return RestartRequiredFixFlow()
    if issue_id == "heatpump_managed_schedules_off":
        return UndoManualScheduleExecutionFixFlow(issue_id)

    return None
