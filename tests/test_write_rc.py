import time

from config.constants import READBACK_DELAY, TARGET_RCS, ZONE_IP
from config.rc_write_registers import RC_WRITE_TEST_CASES
from config.case_schema import (
    COMPARE_MQTT,
    case_modbus_table,
    case_value,
    compare_via,
    normalize_case,
)
from utils.modbus_utils import (
    create_client,
    read_register_data,
    write_register_data,
)
from utils.mqtt_utils import (
    drain_tracker_messages,
    is_mqtt_listener_connected,
    reset_zc_mqtt_state,
    start_mqtt_listener,
    stop_mqtt_listener,
)
from utils.report_utils import print_unresolved_errors
from utils.tracker_utils import get_rc_command_register
from utils.validation_engine import run_post_write_validation


def _cases_need_mqtt():
    return any(
        compare_via(normalize_case(c)) == COMPARE_MQTT
        for c in RC_WRITE_TEST_CASES
    )


def test_write_rc_commands():

    errors = []
    mqtt_client = None
    client = create_client(ZONE_IP)

    reset_zc_mqtt_state()
    if _cases_need_mqtt():
        mqtt_client = start_mqtt_listener(broker_ip=ZONE_IP)

    try:
        if not client.connect():
            errors.append({
                "step": "Modbus connect",
                "error": f"Could not connect to {ZONE_IP}:502",
            })
        else:
            for tracker in TARGET_RCS:
                print("\n" + "=" * 80)
                print(f"TRACKER : {tracker}")
                print("=" * 80)

                for raw in RC_WRITE_TEST_CASES:
                    case = normalize_case(raw)

                    if (
                        compare_via(case) == COMPARE_MQTT
                        and not is_mqtt_listener_connected()
                    ):
                        print(
                            f"SKIP {case['name']} ({tracker}): "
                            "MQTT broker unavailable"
                        )
                        continue

                    register = get_rc_command_register(tracker, case["name"])
                    drain_tracker_messages(tracker)

                    write_resp = write_register_data(
                        client,
                        register,
                        case["dtype"],
                        case_value(case),
                    )

                    if write_resp.isError():
                        errors.append({
                            "tracker": tracker,
                            "step": f"Write {case['name']}",
                            "error": "Modbus write failed",
                            "register": register,
                        })
                        continue

                    time.sleep(READBACK_DELAY)

                    readback = read_register_data(
                        client,
                        register,
                        case["dtype"],
                        modbus_table=case_modbus_table(case),
                    )

                    if case["name"] == "HRST":
                        print(
                            f"HRST MQTT wait: "
                            f"{case.get('mqtt_timeout', 60)}s for {tracker}"
                        )

                    ok, err, extra = run_post_write_validation(
                        case,
                        readback,
                        tracker=tracker,
                    )

                    if not ok:
                        errors.append({
                            "tracker": tracker,
                            "step": f"Validate {case['name']}",
                            "error": err,
                            "written": case_value(case),
                            "readback": readback,
                            "compare_via": case.get("compare_via"),
                            **(extra or {}),
                        })

    finally:
        client.close()
        stop_mqtt_listener(mqtt_client)

    print_unresolved_errors("test_write_rc", errors)
    assert not errors, f"FAILED: {errors}"
