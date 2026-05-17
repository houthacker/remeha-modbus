"""Implementation of scenario 3 where a new `scheduler.schedule` was added."""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, override

from homeassistant.core import HomeAssistant, State

from custom_components.remeha_modbus.blend.blender import Scenario
from custom_components.remeha_modbus.blend.scheduler.const import SCHEDULER_TAG_PREFIX
from custom_components.remeha_modbus.blend.scheduler.helpers import decompose_scheduler_tag
from custom_components.remeha_modbus.const import ATTR_SCHEDULER_TAGS, DOMAIN

if TYPE_CHECKING:
    from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator  # noqa: TC004
from custom_components.remeha_modbus.errors import ScenarioExecutionError

_LOGGER = logging.getLogger(__name__)


class SchedulerScheduleAdded(Scenario):
    """Handle a new schedule in the scheduler integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: RemehaUpdateCoordinator,
        schedule_state: State | None,
        track_schedule_state: Callable[[], None],
    ) -> None:
        """Create a new SchedulerScheduleAdded scenario."""

        if schedule_state is None:
            raise ScenarioExecutionError(
                translation_domain=DOMAIN,
                translation_key="scenario_execution_error_missing_required_state",
                translation_placeholders={
                    "scenario": "scheduler_schedule_added",
                    "component": "scheduler",
                },
            )

        self._hass = hass
        self._coordinator = coordinator
        self._schedule_state = schedule_state
        self._track_schedule_state = track_schedule_state

    @override
    async def async_execute(self) -> None:
        """Start listening to changes of the `scheduler.schedule`.

        The entity id must be on the waiting list for it to be processed here.
        If it's not on the waiting list, that means that the schedule was added
        manually instead of triggered by a modbus update. That scenario is not
        supported.
        """

        tag = next(
            (
                tag
                for tag in list[str](self._schedule_state.attributes[ATTR_SCHEDULER_TAGS])
                if tag.startswith(SCHEDULER_TAG_PREFIX)
            ),
            None,
        )

        if tag is None:
            raise ScenarioExecutionError(
                translation_domain=DOMAIN,
                translation_key="scenario_execution_error_no_tag_in_attrs",
                translation_placeholders={
                    "scenario": "scheduler_schedule_added",
                    "entity": self._schedule_state.entity_id,
                },
            )

        try:
            uuid = decompose_scheduler_tag(tag)

            # Can assert here because if tag is not None, it *must* be suffixed by a valid UUID.
            assert uuid is not None

            waiting_list_entry = self._coordinator.remove_from_linking_waiting_list(uuid)
            if waiting_list_entry is not None:
                await self._coordinator.async_upsert_scheduler_link(
                    waiting_list_entry.zone_schedule_uid, self._schedule_state.entity_id
                )

                self._track_schedule_state()

        except ValueError as e:
            _LOGGER.exception(
                "Invalid schedule tag when executing scenario schedule_added",
                exc_info=e,
                stack_info=True,
            )
