"""Tests for the appliance."""

from custom_components.remeha_modbus.api import (
    Appliance,
    ApplianceErrorPriority,
    SeasonalMode,
)


def test_error_as_str():
    """Test the variants of error_as_str()."""

    assert (
        Appliance(
            current_error=None,
            error_priority=ApplianceErrorPriority.NO_ERROR,
            status=None,
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
        ).error_as_str()
        == "OK"
    )

    assert (
        Appliance(
            current_error=int("0207", 16),
            error_priority=ApplianceErrorPriority.WARNING,
            status=None,
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
        ).error_as_str()
        == "A02.07"
    )

    assert (
        Appliance(
            current_error=int("0207", 16),
            error_priority=ApplianceErrorPriority.BLOCKING,
            status=None,
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
        ).error_as_str()
        == "H02.07"
    )

    assert (
        Appliance(
            current_error=int("0207", 16),
            error_priority=ApplianceErrorPriority.LOCKING,
            status=None,
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
        ).error_as_str()
        == "E02.07"
    )
