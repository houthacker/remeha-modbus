"""Tests for the appliance."""

from custom_components.remeha_modbus.api.appliance import (
    Appliance,
    ApplianceErrorPriority,
    ApplianceStatus,
    CoolingType,
    SeasonalMode,
    SilentMode,
)


def test_error_as_str():
    """Test the variants of error_as_str()."""

    assert (
        Appliance(
            silent_mode=SilentMode.OFF,
            ch_enabled=True,
            cooling_type=CoolingType.ACTIVE_COOLING,
            cooling_forced=False,
            current_error=None,
            error_priority=ApplianceErrorPriority.NO_ERROR,
            status=ApplianceStatus((1, 1)),
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
            summer_winter=22.0,
        ).error_as_str()
        == "OK"
    )

    assert (
        Appliance(
            silent_mode=SilentMode.OFF,
            ch_enabled=True,
            cooling_type=CoolingType.ACTIVE_COOLING,
            cooling_forced=False,
            current_error=int("0207", 16),
            error_priority=ApplianceErrorPriority.WARNING,
            status=ApplianceStatus((1, 1)),
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
            summer_winter=22.0,
        ).error_as_str()
        == "A02.07"
    )

    assert (
        Appliance(
            silent_mode=SilentMode.OFF,
            ch_enabled=True,
            cooling_type=CoolingType.ACTIVE_COOLING,
            cooling_forced=False,
            current_error=int("0207", 16),
            error_priority=ApplianceErrorPriority.BLOCKING,
            status=ApplianceStatus((1, 1)),
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
            summer_winter=22.0,
        ).error_as_str()
        == "H02.07"
    )

    assert (
        Appliance(
            silent_mode=SilentMode.OFF,
            ch_enabled=True,
            cooling_type=CoolingType.ACTIVE_COOLING,
            cooling_forced=False,
            current_error=int("0207", 16),
            error_priority=ApplianceErrorPriority.LOCKING,
            status=ApplianceStatus((1, 1)),
            season_mode=SeasonalMode.SUMMER_NEUTRAL_BAND,
            summer_winter=22.0,
        ).error_as_str()
        == "E02.07"
    )
