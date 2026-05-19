"""RC write test cases — standard schema via config.case_schema."""

from config.case_schema import (
    COMPARE_API,
    COMPARE_MODBUS,
    COMPARE_MQTT,
    make_rc_write_case,
)
from config.rc_registers import (
    CFLT_OFFSET,
    HMNM_OFFSET,
    HRST_OFFSET,
    MODE_OFFSET,
    STOP_OFFSET,
)

RC_WRITE_TEST_CASES = [
    # API-validated
    # REST manualAngle does not track Modbus HMNM register; readback-only check
    make_rc_write_case(
        "HMNM",
        "float",
        25.0,
        HMNM_OFFSET,
        compare_via=COMPARE_MODBUS,
        tolerance=0.5,
    ),
    make_rc_write_case(
        "CFLT",
        "int16",
        1,
        CFLT_OFFSET,
        compare_via=COMPARE_API,
        api_url="http://ZONE_IP/flask/alerts/zone/getLatest",
        key="collisionFault",
    ),
    make_rc_write_case(
        "MODE",
        "int16",
        7,
        MODE_OFFSET,
        compare_via=COMPARE_API,
        api_url="http://ZONE_IP/flask/rover/get/no_time_diff",
    ),
    # MQTT-validated
    make_rc_write_case(
        "RTC",
        "int16",
        1,
        MODE_OFFSET,
        compare_via=COMPARE_MODBUS,
    ),
    make_rc_write_case(
        "Refresh",
        "int16",
        1,
        MODE_OFFSET,
        compare_via=COMPARE_MODBUS,
    ),
    make_rc_write_case(
        "STOP",
        "int16",
        1,
        STOP_OFFSET,
        compare_via=COMPARE_MQTT,
        mqtt_key="STOP",
        mqtt_timeout=45,
    ),
    make_rc_write_case(
        "SC",
        "float",
        1.0,
        HMNM_OFFSET,
        compare_via=COMPARE_MODBUS,
    ),
    make_rc_write_case(
        "HRST",
        "int16",
        1,
        HRST_OFFSET,
        compare_via=COMPARE_MQTT,
        mqtt_key="HRST",
        mqtt_timeout=60,
    ),
]
