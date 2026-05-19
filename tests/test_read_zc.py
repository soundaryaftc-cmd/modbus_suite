from config.constants import ZONE_IP
from config.read_registers import registers
from config.case_schema import COMPARE_MQTT, compare_via, normalize_case, should_compare
from utils.modbus_utils import read_modbus
from utils.mqtt_utils import (
    rebuild_zc_mode_counts,
    reset_zc_mqtt_state,
    start_mqtt_listener,
    stop_mqtt_listener,
    sync_rover_modes_from_api,
    wait_for_mode_counts_ready,
    zc_mode_counts,
)
from utils.report_utils import print_unresolved_errors
from utils.validation_engine import fetch_expected_read_zc, validate_read_zc


def test_read_zc():

    failed = []
    mqtt_client = None

    reset_zc_mqtt_state()
    mqtt_client = start_mqtt_listener(broker_ip=ZONE_IP)

    sync_rover_modes_from_api(ZONE_IP)
    wait_for_mode_counts_ready(
        zone_ip=ZONE_IP,
        min_rovers=5,
        timeout=15,
    )

    rebuild_zc_mode_counts("expected")
    rebuild_zc_mode_counts("stow_slots")
    print(f"MQTT mode counts (expected): {dict(zc_mode_counts)}")

    try:
        for reg in registers:
            row = normalize_case(reg)
            if not should_compare(row):
                continue

            if compare_via(row) == COMPARE_MQTT and mqtt_client is None:
                print(f"SKIP {row['name']}: MQTT broker unavailable")
                continue

            modbus_val = read_modbus(
                ip=ZONE_IP,
                reg_address=row["reg_address"],
                length=row["length"],
                dtype=row["dtype"],
            )

            expected_val = fetch_expected_read_zc(row)

            ok, err, source = validate_read_zc(row, modbus_val, expected_val)

            if not ok:
                failed.append({
                    "name": row["name"],
                    "error": err,
                    "modbus": modbus_val,
                    "expected": expected_val,
                    "reg_address": row["reg_address"],
                    "dtype": row["dtype"],
                    "compare_via": compare_via(row),
                })

    finally:
        stop_mqtt_listener(mqtt_client)

    print_unresolved_errors("test_read_zc", failed)
    assert failed == [], f"FAILED CASES: {failed}"
