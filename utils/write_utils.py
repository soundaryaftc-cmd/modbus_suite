import struct


# =========================================================
# ENCODER
# =========================================================

def encode_value(dtype, value):

    try:

        # INT16
        if dtype == "int16":

            value = int(value)

            return [value & 0xFFFF]

        # FLOAT
        if dtype == "float":

            raw = struct.pack(">f", float(value))

            return [
                int.from_bytes(raw[0:2], "big"),
                int.from_bytes(raw[2:4], "big"),
            ]

    except Exception as e:

        print("Encode Error:", str(e))

    return None


# =========================================================
# DECODE WRITE VALUES
# =========================================================

def decode_written_value(registers, dtype):

    if not registers:
        return None

    try:

        if dtype == "int16":
            if not registers:
                return None
            return struct.unpack(
                ">h",
                registers[0].to_bytes(2, "big"),
            )[0]

        if dtype == "float":

            raw = (
                registers[0].to_bytes(2, "big") +
                registers[1].to_bytes(2, "big")
            )

            return struct.unpack(">f", raw)[0]

    except Exception as e:

        print("Decode Error:", str(e))

    return None


def encode_int16(value):

    return [int(value) & 0xFFFF]


def encode_float(value):

    raw = struct.pack(">f", float(value))

    high = int.from_bytes(raw[0:2], "big")

    low = int.from_bytes(raw[2:4], "big")

    return [high, low]


def decode_int16(registers):

    if not registers:
        return None

    return struct.unpack(
        ">h",
        registers[0].to_bytes(2, "big"),
    )[0]


def decode_float(registers):

    if len(registers) < 2:
        return None

    raw = (
        registers[0].to_bytes(2, "big") +
        registers[1].to_bytes(2, "big")
    )

    return struct.unpack(">f", raw)[0]


_COMMAND_DTYPES = {
    "MODE": "int16",
    "CFLT": "int16",
    "HMNM": "float",
}


def verify_rc_write_case(command, readback, written, tolerance, api_value=None):
    from config.constants import MODE_MAP
    from utils.validators import compare_float, compare_int

    dtype = _COMMAND_DTYPES.get(command, "int16")

    if dtype == "float":
        if not compare_float(readback, written, tolerance):
            return False
    elif not compare_int(readback, written):
        return False

    if api_value is None:
        return True

    if command == "MODE":
        mode_name = MODE_MAP.get(int(written))
        if mode_name and str(api_value).strip().upper() == mode_name.upper():
            return True
        return compare_int(api_value, written)

    if command == "HMNM":
        return compare_float(api_value, written, tolerance)

    return compare_int(api_value, written)