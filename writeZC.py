from pymodbus.client import ModbusTcpClient

from config.constants import DEFAULT_PORT
from config.write_zc_registers import WRITE_CASES

from utils.api_utils import get_api_value
from utils.modbus_utils import modbus_unit_kwargs
from utils.validators import validator
from utils.write_utils import (
    encode_value,
    decode_written_value,
)


# =========================================================
# WRITE REGISTER
# =========================================================

def write_register(
    client,
    reg_address,
    values,
    slave_id=1
):

    try:

        # SINGLE REGISTER
        if len(values) == 1:

            response = client.write_register(
                address=reg_address,
                value=values[0],
                **modbus_unit_kwargs(slave_id),
            )

        # MULTIPLE REGISTERS
        else:

            response = client.write_registers(
                address=reg_address,
                values=values,
                **modbus_unit_kwargs(slave_id),
            )

        return not response.isError()

    except Exception as e:

        print("Write Error:", str(e))
        return False


# =========================================================
# READ BACK
# =========================================================

def read_back(
    client,
    reg_address,
    dtype,
    slave_id=1
):

    count = 1 if dtype == "int16" else 2

    try:

        response = client.read_holding_registers(
            address=reg_address,
            count=count,
            **modbus_unit_kwargs(slave_id),
        )

        if response.isError():

            response = client.read_input_registers(
                address=reg_address,
                count=count,
                **modbus_unit_kwargs(slave_id),
            )

        if response.isError():
            return None

        return decode_written_value(
            response.registers,
            dtype
        )

    except Exception as e:

        print("Readback Error:", str(e))
        return None


# =========================================================
# MAIN
# =========================================================

def main():

    if not WRITE_CASES:
        print(
            "ZC write register map is not configured. "
            "Use writerc.py for rover-controller (RC) writes."
        )
        return

    ip = input("Enter Zone IP: ").strip()

    client = ModbusTcpClient(
        host=ip,
        port=DEFAULT_PORT,
        timeout=5
    )

    if not client.connect():

        print("FAIL: Connection failed")
        return

    pass_count = 0
    fail_count = 0

    for case in WRITE_CASES:

        print(f"\n=== {case['name']} ===")

        desired_val = get_api_value(
            api_url=f"http://{ip}/flask/rover/get/no_time_diff",
            key=case["api_key"]
        )

        print("Desired Value:", desired_val)

        if desired_val is None:

            print("FAIL: API value missing")
            fail_count += 1
            continue

        encoded = encode_value(
            case["dtype"],
            desired_val
        )

        if not encoded:

            print("FAIL: Encoding failed")
            fail_count += 1
            continue

        success = write_register(
            client=client,
            reg_address=case["reg_address"],
            values=encoded
        )

        if not success:

            print("FAIL: Modbus write failed")
            fail_count += 1
            continue

        modbus_val = read_back(
            client=client,
            reg_address=case["reg_address"],
            dtype=case["dtype"]
        )

        print("Modbus Readback:", modbus_val)

        if validator(
            modbus_val,
            desired_val,
            "float" if case["dtype"] == "float" else "int"
        ):

            print("PASS")
            pass_count += 1

        else:

            print("FAIL")
            fail_count += 1

    print("\n=== FINAL SUMMARY ===")
    print("PASS:", pass_count)
    print("FAIL:", fail_count)

    client.close()


if __name__ == "__main__":
    main()