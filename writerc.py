import time

from config.constants import (
    READBACK_DELAY,
    TARGET_RCS,
    ZONE_IP,
)

from config.rc_registers import (
    build_write_cases,
)

from utils.api_utils import (
    fetch_rover,
    find_rc,
    get_rc_api_value,
)

from utils.modbus_utils import (
    create_client,
    write_register_data,
    read_register_data,
)

from utils.tracker_utils import (
    get_rc_command_register,
)

from utils.write_utils import (
    verify_rc_write_case,
)


TARGET_RC = TARGET_RCS[0]


def main():

    client = create_client(ZONE_IP)

    if not client.connect():

        print("FAIL: Modbus connection failed")
        return

    cases = build_write_cases()

    passed = 0
    failed = 0

    for case in cases:

        command = case["name"]

        register = get_rc_command_register(
            TARGET_RC,
            command
        )

        print("\n" + "=" * 60)

        print(f"Testing : {command}")

        print(f"Register : {register}")

        response = write_register_data(
            client,
            register,
            case["dtype"],
            case["value"]
        )

        if response.isError():

            print("FAIL: Write failed")

            failed += 1

            continue

        time.sleep(READBACK_DELAY)

        readback = read_register_data(
            client,
            register,
            case["dtype"]
        )

        payload = fetch_rover(ZONE_IP)

        rc_data = find_rc(
            payload,
            TARGET_RC
        )

        api_value = get_rc_api_value(
            rc_data,
            command
        )

        result = verify_rc_write_case(
            command,
            readback,
            case["value"],
            case["tolerance"],
            api_value,
        )

        print("Written  :", case["value"])

        print("Readback :", readback)

        print("API      :", api_value)

        if result:

            print("PASS")

            passed += 1

        else:

            print("FAIL")

            failed += 1

    print("\n===== FINAL SUMMARY =====")

    print("PASS :", passed)

    print("FAIL :", failed)

    client.close()


if __name__ == "__main__":

    main()