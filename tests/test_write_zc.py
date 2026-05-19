import time

import pytest

from config.constants import READBACK_DELAY, ZONE_IP
from config.write_zc_registers import WRITE_CASES
from config.case_schema import case_modbus_table, case_value, normalize_case
from utils.modbus_utils import create_client, read_register_data, write_register_data
from utils.mqtt_utils import (
    is_mqtt_listener_connected,
    reset_zc_mqtt_state,
    start_mqtt_listener,
    stop_mqtt_listener,
)
from utils.report_utils import print_unresolved_errors
from utils.validation_engine import run_post_write_validation


def test_write_zc_broadcast():

    errors = []
    mqtt_client = None
    client = create_client(ZONE_IP)

    if not WRITE_CASES:
        return

    reset_zc_mqtt_state()
    mqtt_client = start_mqtt_listener(broker_ip=ZONE_IP)

    if not is_mqtt_listener_connected():
        pytest.skip(
            f"MQTT broker unreachable at {ZONE_IP}:1883; "
            "ZC write tests require MQTT confirmation"
        )

    try:
        if not client.connect():
            errors.append({
                "step": "Modbus connect",
                "error": f"Could not connect to {ZONE_IP}:502",
            })
        else:
            for raw in WRITE_CASES:
                case = normalize_case(raw)
                register = case["reg_address"]

                write_resp = write_register_data(
                    client,
                    register,
                    case["dtype"],
                    case_value(case),
                )

                if write_resp.isError():
                    errors.append({
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

                ok, err, extra = run_post_write_validation(
                    case,
                    readback,
                    tracker=None,
                    mqtt_timeout=30,
                )

                if not ok:
                    errors.append({
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

    print_unresolved_errors("test_write_zc", errors)
    assert not errors, f"FAILED: {errors}"
