"""Constants for integration with scheduler-component."""

from enum import StrEnum
from typing import Any, Final, Literal, NotRequired, Required, TypedDict

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from pydantic.dataclasses import dataclass

from custom_components.remeha_modbus.const import DOMAIN, Weekday, ZoneScheduleUID

SchedulerDomain: Final[str] = "scheduler"
"""The name of the scheduler integration."""

SCHEDULER_INSTALLATION_URL: Final[str] = "https://github.com/nielsfaber/scheduler-card#installation"
"""URL pointing to installation docs of the scheduler component."""

SCHEDULER_TAG_PREFIX: Final[str] = f"{DOMAIN}_"
"""The prefix for a `scheduler.schedule` tag.

This tag is used to link a `scheduler.schedule` to a `ZoneSchedule`.
"""


class ServiceOperation(StrEnum):
    """Enumerate the required service operation to store a schedule."""

    ADD = "add"
    """The schedule does not exist in the service, so it must be added."""
    EDIT = "edit"
    """The schedule already exists in the service, so it must be edited."""


WEEKDAY_TO_SHORT_DESC: Final[
    dict[Weekday, Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]
] = {
    Weekday.MONDAY: "mon",
    Weekday.TUESDAY: "tue",
    Weekday.WEDNESDAY: "wed",
    Weekday.THURSDAY: "thu",
    Weekday.FRIDAY: "fri",
    Weekday.SATURDAY: "sat",
    Weekday.SUNDAY: "sun",
}

SHORT_DESC_TO_WEEKDAY: Final[
    dict[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], Weekday]
] = {WEEKDAY_TO_SHORT_DESC[day]: day for day in Weekday}


@dataclass(frozen=True, slots=True)
class SchedulerLinkView:
    """A view of the link between a scheduler.schedule and a `ZoneSchedule`."""

    zone_schedule_uid: ZoneScheduleUID
    """The unique identity of the related climate entity."""

    scheduler_entity_id: str
    """The entity id of the related scheduler.schedule."""


class SchedulerAction(TypedDict):
    """A `SchedulerAction` represents a Home Assistant action that is executed when a scheduler.schedule timer expires."""

    entity_id: Required[str]
    """Entity against which the actions needs to be executed, e.g. `light.living_table_light`."""

    service: Required[str]
    """HA service that needs to be executed against the entity, e.g. `light.turn_on`."""

    service_data: NotRequired[dict]
    """Extra parameters to use in the service call, e.g. `{'brightness': 200}`"""


class SchedulerCondition(TypedDict):
    """A `SchedulerCondition` is a boolean predicate which allows or denies execution of the related `SchedulerAction`."""

    attribute: Required[Literal["state"]]
    """The entity attribute to check to obtain the condition."""

    entity_id: Required[str]
    """Entity to which the condition applies, e.g. `binary_sensor.my_window`."""

    value: Required[str]
    """Value to compare the entity state to, e.g. `on`."""

    match_type: Required[Literal["is", "not", "below", "above"]]
    """Logic to apply for the comparison.

    Values:
    * `is`: entity state must match `value`.
    * `not`: entity state must _not_ match `value`.
    * `below`: entity state must be below `value` (applicable to numerical values only).
    * `above`: entity state must be above `value` (applicable to numerical values only).
    """


class SchedulerTimeslot(TypedDict):
    """A `SchedulerTimeslot` defines when a `SchedulerSchedule` is triggered, together with the actions that must be executed."""

    start: Required[str]
    """Time in `%H:%M:%S` format on which the schedule should trigger, for example `22:00:00` for 10 PM."""

    stop: NotRequired[str]
    """Time in `%H:%M:%S` format on which the timeslot ends. Only required when a new timeslot is defined."""

    conditions: NotRequired[list[SchedulerCondition]]
    """Conditions that should be validated before the action(s) may be executed."""

    condition_type: NotRequired[Literal["and", "or"]]
    """Logic to apply when validating multiple conditions.

    Values:
    * `and`: All conditions must be met.
    * `or`: One or more of the conditions must be met.
    """

    track_conditions: NotRequired[bool]
    """Watch condition entries for changes, repeat the actions once conditions become valid."""

    actions: Required[list[SchedulerAction]]
    """Actions to execute when the `start` time is reached."""


class SchedulerSchedule(TypedDict):
    """A `SchedulerSchedule` is a schedule that adheres to the `scheduler.add|update` service fields."""

    entity_id: NotRequired[str]
    """The entity id of the schedule. Only required when editing a schedule."""

    name: NotRequired[str]
    """The name of the schedule. Will be used to create its entity_id and is therefore only required when creating a new schedule."""

    weekdays: Required[list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]]
    """The days of the week on which the schedule should be executed."""

    repeat_type: Required[Literal["repeat", "single", "pause"]]
    """Control repeat behaviour after triggering.

    Values:
    * `repeat`: schedule will loop after triggering.
    * `single`: schedule will delete itself after triggering.
    * `pause`: schedule will turn off after triggering, can be reset by turning on.
    """

    timeslots: Required[list[SchedulerTimeslot]]
    """List of time intervals with the actions that should be executed."""

    tags: NotRequired[list[str]]
    """An optional list of tags for the schedule."""


class SchedulerStateAction(TypedDict):
    """An action as defined in the attributes of a scheduler.schedule `State`."""

    service: str
    """The full name of the service to call, for example `climate.set_preset_mode`."""

    data: dict[str, Any]
    """The service data to go with the service call, for example `{'preset_mode': 'comfort'}`."""


class SchedulerStateAttributes(TypedDict):
    """The attributes field in a scheduler `State` instance."""

    weekdays: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]
    """Weekdays at which the scheduler.schedule is active."""

    timeslots: list[str]
    """The timeslot ranges in the scheduler.schedule, in a format like `%H:%M:S - %H:%M:%S`.
    For every timeslot there is a corresponding action.
    """

    entities: list[str]
    """A list of entity ids to apply the scheduler.schedule to."""

    actions: list[SchedulerStateAction]
    """The actions for each timeslot."""

    tags: list[str]
    """An optional list of tags for the scheduler.schedule."""


class SchedulerState(TypedDict):
    """Represents the state attributes of a scheduler.schedule.

    These attributes are not necessarily a 1:1 copy, but only refer to
    those that are relevant for `remeha-modbus`.
    """

    entity_id: str
    """The entity id of the scheduler.schedule."""

    state: Literal[f"{STATE_ON}", f"{STATE_OFF}", f"{STATE_UNKNOWN}", f"{STATE_UNAVAILABLE}"]
    """The state of the scheduler.schedule."""

    attributes: SchedulerStateAttributes
    """The attributes of the scheduler state."""
