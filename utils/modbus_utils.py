import inspect
import math
import struct

from pymodbus.client import ModbusTcpClient

from config.constants import DEFAULT_PORT, MODBUS_TIMEOUT

_modbus_unit_param = None


def modbus_unit_kwargs(slave_id=1):
    """
    PyModbus 3.6.x uses slave=; newer releases use device_id=.
    Resolve once from read_holding_registers signature.
    """
    global _modbus_unit_param
    if _modbus_unit_param is None:
        sig = inspect.signature(ModbusTcpClient.read_holding_registers)
        if "device_id" in sig.parameters:
            _modbus_unit_param = "device_id"
        elif "slave" in sig.parameters:
            _modbus_unit_param = "slave"
        else:
            _modbus_unit_param = "slave"
    return {_modbus_unit_param: slave_id}


# =========================================================
# TCP CLIENT + HOLDING REGISTER I/O
# =========================================================


def create_client(ip, port=DEFAULT_PORT, timeout=MODBUS_TIMEOUT):
    return ModbusTcpClient(host=ip, port=port, timeout=timeout)


def _holding_register_count(dtype):
    if dtype in ("float", "int32"):
        return 2
    return 1


def read_register_data(
    client,
    address,
    dtype,
    slave_id=1,
    modbus_table="holding",
):
    """
    Read decoded register value.
    modbus_table: 'holding', 'input', or 'auto' (holding then input on error).
    """
    tables = (
        ("holding", "input")
        if modbus_table == "auto"
        else ((modbus_table,) if modbus_table in ("holding", "input") else ("holding",))
    )

    count = _holding_register_count(dtype)
    kwargs = modbus_unit_kwargs(slave_id)

    for table in tables:
        read_fn = (
            client.read_input_registers
            if table == "input"
            else client.read_holding_registers
        )
        response = read_fn(address=address, count=count, **kwargs)

        if response.isError():
            continue

        registers = response.registers

        if dtype == "int16":
            if not registers:
                continue
            return struct.unpack(">h", registers[0].to_bytes(2, "big"))[0]

        decoded = decode_registers(registers, dtype)
        if decoded is not None:
            return decoded

    return None


def write_register_data(client, address, dtype, value, slave_id=1):
    if dtype == "int16":
        word = struct.unpack(
            ">H",
            struct.pack(">h", int(value)),
        )[0]
        return client.write_register(address, word, **modbus_unit_kwargs(slave_id))

    if dtype == "float":
        raw = struct.pack(">f", float(value))
        regs = [
            int.from_bytes(raw[0:2], "big"),
            int.from_bytes(raw[2:4], "big"),
        ]
        return client.write_registers(address, regs, **modbus_unit_kwargs(slave_id))

    if dtype == "int32":
        raw = int(value).to_bytes(4, byteorder="big", signed=False)
        regs = [
            int.from_bytes(raw[0:2], "big"),
            int.from_bytes(raw[2:4], "big"),
        ]
        return client.write_registers(address, regs, **modbus_unit_kwargs(slave_id))

    if dtype == "int":
        return client.write_register(
            address, int(value) & 0xFFFF, **modbus_unit_kwargs(slave_id)
        )

    if dtype == "bool":
        return client.write_register(
            address, 1 if value else 0, **modbus_unit_kwargs(slave_id)
        )

    raise ValueError(f"Unsupported write dtype: {dtype}")


# =========================================================
# MODBUS DECODER
# =========================================================

def decode_registers(registers, dtype):

    if not registers:
        return None

    try:

        # =================================================
        # FLOAT (2 Registers)
        # =================================================

        if dtype == "float":

            if len(registers) < 2:
                return None

            raw = (
                registers[0].to_bytes(2, "big") +
                registers[1].to_bytes(2, "big")
            )

            return struct.unpack(">f", raw)[0]

        # =================================================
        # INT16
        # =================================================

        if dtype == "int":

            return registers[0]

        # =================================================
        # INT32
        # =================================================

        if dtype == "int32":

            if len(registers) < 2:
                return None

            raw = (
                registers[0].to_bytes(2, "big") +
                registers[1].to_bytes(2, "big")
            )

            return int.from_bytes(
                raw,
                byteorder="big",
                signed=False,
            )

        # =================================================
        # BOOL
        # =================================================

        if dtype == "bool":

            return registers[0] != 0

        # =================================================
        # STRING
        # =================================================

        chars = []

        for reg in registers:

            chars.append(chr((reg >> 8) & 0xFF))
            chars.append(chr(reg & 0xFF))

        return "".join(chars).replace("\x00", "").strip()

    except Exception as e:

        print("Decode Error:", str(e))

        return None


# =========================================================
# GENERIC MODBUS READ
# Works for:
# - ZC direct registers
# - RC calculated registers
# =========================================================

def read_modbus(
    ip,
    reg_address,
    length,
    dtype,
    slave_id=1,
    port=DEFAULT_PORT,
):

    client = ModbusTcpClient(
        host=ip,
        port=port,
        timeout=3,
    )

    try:

        # =================================================
        # CONNECT
        # =================================================

        if not client.connect():

            print("FAIL: Connection failed")

            return None

        # =================================================
        # CALCULATE REGISTER COUNT
        # =================================================

        register_count = max(
            1,
            math.ceil(length / 2)
        )

        # =================================================
        # READ INPUT REGISTERS
        # =================================================

        response = client.read_input_registers(
            address=reg_address,
            count=register_count,
            **modbus_unit_kwargs(slave_id),
        )

        if response.isError():

            print("FAIL: Modbus read error")

            return None

        # =================================================
        # RAW DATA
        # =================================================

        registers = response.registers

        print("Register :", reg_address)

        print("Raw      :", registers)

        # =================================================
        # DECODE
        # =================================================

        decoded_value = decode_registers(
            registers,
            dtype,
        )

        print("Decoded  :", decoded_value)

        return decoded_value

    except Exception as e:

        print("Modbus Error:", str(e))

        return None

    finally:

        client.close()


# =========================================================
# RC HELPER
# Automatically calculate tracker register
# =========================================================

def read_tracker_register(
    ip,
    tracker_name,
    field_name,
    calculate_register_fn,
    field_specs,
    slave_id=1,
):

    spec = field_specs[field_name]

    reg_address = calculate_register_fn(
        tracker_name,
        field_name,
    )

    return read_modbus(
        ip=ip,
        reg_address=reg_address,
        length=spec["count"] * 2,
        dtype=spec["dtype"],
        slave_id=slave_id,
    )