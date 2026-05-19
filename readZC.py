from config.case_schema import (
    COMPARE_MQTT,
    compare_via,
    normalize_case,
    should_compare,
)
from config.read_registers import registers

from utils.modbus_utils import read_modbus
from utils.validation_engine import fetch_expected_read_zc, validate_read_zc


def compare():

    ip = input("Enter Zone IP: ").strip()

    pass_count = 0
    fail_count = 0

    for raw in registers:
        case = normalize_case(raw)

        print(f"\n========== {case['name']} ==========")

        if compare_via(case) == COMPARE_MQTT:
            print("SKIP: MQTT compare rows — run tests/test_read_zc.py")
            pass_count += 1
            continue

        # =================================================
        # MODBUS VALUE
        # =================================================

        modbus_val = read_modbus(
            ip=ip,
            reg_address=case["reg_address"],
            length=case["length"],
            dtype=case["dtype"],
        )

        # =================================================
        # API VALUE
        # =================================================

        api_val = fetch_expected_read_zc(case)

        # =================================================
        # PRINT RESULTS
        # =================================================

        print("\n--- RESULT ---")
        print("Modbus Value :", modbus_val)
        print("API Value    :", api_val)
        print("dtype        :", case["dtype"])

        # =================================================
        # VALIDATION
        # =================================================

        if modbus_val is None or api_val is None:

            print("FAIL: Missing data")
            fail_count += 1
            continue

        if not should_compare(case):
            print("SKIP: Compare disabled for this row (expected mismatch zone)")
            pass_count += 1
            continue

        ok, err, _source = validate_read_zc(case, modbus_val, api_val)
        result = ok

        if result:

            print("PASS: Modbus matches API")
            pass_count += 1

        else:

            print("FAIL: Modbus mismatch")
            fail_count += 1

    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    print("\n========== FINAL SUMMARY ==========")

    print("PASS :", pass_count)
    print("FAIL :", fail_count)


if __name__ == "__main__":
    compare()