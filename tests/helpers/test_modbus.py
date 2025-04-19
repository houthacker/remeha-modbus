"""Test modbus helper."""

from custom_components.remeha_modbus.api import ClimateZoneHeatingMode
from custom_components.remeha_modbus.const import DeviceInstanceRegisters, ZoneRegisters
from custom_components.remeha_modbus.helpers import modbus


def test_to_registers_happy_path():
    """Test the serialization of the supported data type variations to a list of modbus register values."""

    # INT16, scale 0.1
    assert modbus.to_registers(
        source_variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE, value=20.1
    ) == [201]

    # UINT16, scale 0.01
    assert modbus.to_registers(
        source_variable=ZoneRegisters.DHW_TANK_TEMPERATURE, value=52.3
    ) == [5230]

    # ENUM8
    assert modbus.to_registers(
        source_variable=ZoneRegisters.CURRENT_HEATING_MODE,
        value=ClimateZoneHeatingMode.COOLING.value,
    ) == [ClimateZoneHeatingMode.COOLING.value]

    # STRING(3)
    assert modbus.to_registers(
        source_variable=ZoneRegisters.SHORT_NAME, value="DHW"
    ) == [
        int.from_bytes(b"\x44\x48"),
        int.from_bytes(b"\x57\x00"),
    ]

    # UINT16, tuple.
    assert modbus.to_registers(
        source_variable=DeviceInstanceRegisters.SW_VERSION, value=(2, 1)
    ) == [int.from_bytes(b"\x02\x01")]

    # INT16, None
    assert modbus.to_registers(
        source_variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE, value=None
    ) == [modbus.NULL_VALUES[ZoneRegisters.CURRENT_ROOM_TEMPERATURE.data_type]]


def test_from_registers_happy_path():
    """Test the deserialization of the supported data type variations from a list of modbus register values."""

    # INT16, scale 0.1
    assert (
        modbus.from_registers(
            registers=[201], destination_variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE
        )
        == 20.1
    )

    # UINT16, scale 0.01
    assert (
        modbus.from_registers(
            registers=[5230], destination_variable=ZoneRegisters.DHW_TANK_TEMPERATURE
        )
        == 52.3
    )

    # ENUM8
    assert (
        modbus.from_registers(
            registers=[ClimateZoneHeatingMode.COOLING.value],
            destination_variable=ZoneRegisters.CURRENT_HEATING_MODE,
        )
        == ClimateZoneHeatingMode.COOLING.value
    )

    # STRING(3)
    assert (
        modbus.from_registers(
            registers=[
                int.from_bytes(b"\x44\x48"),
                int.from_bytes(b"\x57\x00"),
                int.from_bytes(b"\x00\x00"),
            ],
            destination_variable=ZoneRegisters.SHORT_NAME,
        )
        == "DHW"
    )

    # UINT16, tuple
    assert modbus.from_registers(
        registers=[int.from_bytes(b"\x02\x01")],
        destination_variable=DeviceInstanceRegisters.SW_VERSION,
    ) == (2, 1)

    # INT16, None
    assert (
        modbus.from_registers(
            registers=[int.from_bytes(b"\x80\x00", signed=True, byteorder="little")],
            destination_variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
        )
        is None
    )
