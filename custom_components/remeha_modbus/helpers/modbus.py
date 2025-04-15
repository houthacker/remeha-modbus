"""Modbus helper functions."""

import logging
import struct
from collections.abc import Callable
from typing import Final

from pymodbus.client.mixin import ModbusClientMixin
from pymodbus.pdu import ModbusPDU

from custom_components.remeha_modbus.const import DataType, ModbusVariableDescription

_LOGGER = logging.getLogger(__name__)

NULL_VALUES: Final[dict[DataType, int]] = {
    DataType.UINT16: int.from_bytes(bytes.fromhex("00ff"), signed=False),
    DataType.UINT32: int.from_bytes(bytes.fromhex("0000ffff"), signed=False),
    DataType.INT16: int.from_bytes(bytes.fromhex("ff80"), signed=True),
    DataType.INT32: int.from_bytes(bytes.fromhex("ffff8000"), signed=True),
}


def _is_gtw08_null_value(variable: ModbusVariableDescription, val: int) -> bool:
    if NULL_VALUES[variable.data_type]:
        return val == NULL_VALUES[variable.data_type]

    return val is None or val == b"nan\x00"


def _to_gtw08_null_value(data_type: DataType) -> int:
    if NULL_VALUES[data_type]:
        return NULL_VALUES[data_type]

    return b"nan\x00"


def _deserialize_bytes(
    variable: ModbusVariableDescription, raw_data: bytes
) -> str | int | float | bytes | None:
    match variable.data_type:
        case DataType.STRING:
            return raw_data.decode()
        case (
            DataType.INT16
            | DataType.INT32
            | DataType.INT64
            | DataType.UINT16
            | DataType.UINT32
            | DataType.UINT64
        ):
            val = int.from_bytes(
                raw_data,
                signed=variable.data_type
                in [DataType.INT16, DataType.INT32, DataType.INT64],
            )

            if _is_gtw08_null_value(variable=variable, val=val):
                _LOGGER.debug(
                    "Register (reg=%d, name=%s) contains NULL value. This might indicate unlinked modbus addresses or an out-of-reach device.",
                    variable.start_address,
                    variable.name,
                )
                return None

            if variable.scale is not None:
                # Conversion to float
                return val * variable.scale

            return val
        case DataType.FLOAT16 | DataType.FLOAT32 | DataType.FLOAT64:
            [x] = struct.unpack("f", raw_data)

            if variable.scale is not None:
                return x * variable.scale

            return x
        case DataType.CUSTOM:
            return raw_data


def _serialize_callable(
    variable: ModbusVariableDescription, value: Callable[[], bytes | None]
) -> list[int]:
    register_count: int = variable.count
    callable_result = value()

    if callable_result is None:
        return _to_gtw08_null_value(variable.data_type)

    if not isinstance(callable_result, bytes):
        raise TypeError(
            f"Callable result type is expected to be `bytes`, but got `{type(callable_result).__name__}`"
        )

    data: list[int] = list(callable_result)

    # len(data) must be even in order to be writable to a register.
    if len(data) % 2 != 0:
        raise ValueError(
            f"Cannot serialize value to variable {variable.name}: we need an even amount of bytes, but it yields {len(data)} bytes."
        )

    # Create tuples of two bytes per element
    data = list(zip(data[0::2], data[1::2], strict=True))
    if len(data) != register_count:
        raise ValueError(
            f"Length of serialized bytes ({len(data)}) exceeds register count of {register_count} required by variable {variable.name}"
        )

    # Convert each tuple of two bytes to an int, since a single register contains 16 bits.
    return [element[0] << 8 | element[1] for element in data]


def _serialize_primitive(  # noqa: C901
    variable: ModbusVariableDescription,
    value: str | float | bool | tuple[int, int] | bytes | None,
) -> list[int]:
    mixin_data_type: ModbusClientMixin.DATATYPE = None
    match variable.data_type:
        case DataType.INT16:
            mixin_data_type = ModbusClientMixin.DATATYPE.INT16
        case DataType.UINT16:
            mixin_data_type = ModbusClientMixin.DATATYPE.UINT16
        case DataType.INT32:
            mixin_data_type = ModbusClientMixin.DATATYPE.INT32
        case DataType.UINT32:
            mixin_data_type = ModbusClientMixin.DATATYPE.UINT32
        case DataType.FLOAT32:
            mixin_data_type = ModbusClientMixin.DATATYPE.FLOAT32
        case DataType.INT64:
            mixin_data_type = ModbusClientMixin.DATATYPE.INT64
        case DataType.UINT64:
            mixin_data_type = ModbusClientMixin.DATATYPE.UINT64
        case DataType.FLOAT64:
            mixin_data_type = ModbusClientMixin.DATATYPE.FLOAT64
        case DataType.STRING:
            mixin_data_type = ModbusClientMixin.DATATYPE.STRING

    if mixin_data_type is None:
        raise ValueError(
            f"No conversion path from {variable.data_type.name} to a modbus data type."
        )

    # de-scale non-null values
    if value is not None and variable.scale is not None:
        value: float = float(value) / variable.scale

        # Convert to int if integer value. Assume
        if value.is_integer():
            value = int(value)

    # None-values might have to be GTW-08 null values.
    if value is None:
        value = _to_gtw08_null_value(variable.data_type)

    return ModbusClientMixin.convert_to_registers(
        value=value, data_type=mixin_data_type
    )


def serialize(
    variable: ModbusVariableDescription,
    value: str
    | float
    | bool
    | tuple[int, int]
    | bytes
    | Callable[[], bytes | None]
    | None,
) -> list[int]:
    """Serialize `value` to a list of modbus register values.

    ### Notes:
        * All numeric values will be serialized to big endian, only the result of the `Callable` will keep its endianness.
        * The type of `value` is assumed to equal or be convertible to `variable.data_type`.
        * If `value == None` or the callable result is `None`, the appropriate GTW-08 `null` value is returned if the GTW-08 parameter list specifies it.
        * If `value` is a tuple, the whole tuple must fit in a single register, contain exactly two elements that are both treated as unsigned bytes.
                Therefore the individual values cannot exceed 2^8.

    Args:
        variable (ModbusVariableDescription): The description of the variable to serialize.
        value (str|float|bool|tuple[int,int]|bytes| (() -> (bytes | None))]): The actual value to serialize or a `Callable` that returns the serialized value as a `bytes` object.

    Returns:
        `list[int]`: The list of modbus register values. `list[0]` corresponds to `variable.start_address`.

    Raises:
        ValueError:
            * If no conversion path exists between `variable.data_type` and `value`
            * If conversion to a numeric type fails.
            * If `value` is a `tuple` which does not contain exactly two elements.

    """

    # Convert the HA data type to a modbus data type.
    if isinstance(value, Callable):
        return _serialize_callable(variable=variable, value=value)

    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError("tuple must contain exactly two elements.")

        value = value[0] << 8 | value[1]

    return _serialize_primitive(variable=variable, value=value)


def deserialize(
    response: ModbusPDU, variable: ModbusVariableDescription
) -> str | int | float | bytes | None:
    """Deserializes `response` into a value of type `data_type`.

    #### Custom deserialization:
        If the response contains a custom struct, set `data_type` to the desired type and provide `struct_format`.
        For example, to read the least significant byte from a register and deserialize it to an `int`,
        set `data_type` to  `DataType.INT16` and set `struct_format` to `=xB`.

    #### Scaling response values
        Response values can be scaled by providing `scale`.
        For example, reading the manual setpoint from register 664 (`parZoneRoomManualSetpoint`) returns
        the setpoint as an integer (the value is multiplied by 10). So a setpoint of `21.5 'C` will be returned as `215`.
        In this case, set `scale` to `0.1` to retrieve the value.

    Args:
        response (ModbusPDU): The modbus response.
        variable (ModbusVariableDescription): Meta information about the variable value to deserialize into.

    Returns:
        The response, deserialized to the requested data type, or `None` if the response
        contains a null value.

    Raises:
        ValueError: If the response cannot be decoded as the requested data type or if `data_type` does not fit in the returned register count.

    """

    def unpack_raw_bytes() -> bytes:
        try:
            return bytes(struct.unpack(variable.struct_format, raw_data))
        except struct.error as err:
            msg: str = f"Error unpacking [{raw_data}] to struct format [{variable.struct_format}]"
            raise ValueError(msg) from err

    def ensure_required_registers() -> list[int]:
        if len(response.registers) < variable.count:
            raise ValueError(
                "Response contains %i registers, but deserializing to %s requires %i.",
                len(response.registers),
                variable.data_type.name,
                variable.count,
            )

        return response.registers[0 : variable.count]

    # Only use the required registers
    registers: list[int] = ensure_required_registers()
    raw_data: bytes = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
    if raw_data == b"nan\x00":
        return None

    # Unpack first, if struct_format is provided.
    if variable.struct_format is not None:
        raw_data = unpack_raw_bytes()

    # Only then deserialize, filter out illegal (null) values and and apply scale
    return _deserialize_bytes(variable=variable, raw_data=raw_data)
