"""ZC broadcast write cases — standard schema via config.case_schema."""

from config.case_schema import COMPARE_MODBUS, COMPARE_MQTT, make_zc_write_case

WRITE_CASES = [
    # ZC collision fault: Modbus readback only (no reliable MQTT shape on broadcast)
    make_zc_write_case(
        "CFLT",
        "int16",
        1,
        reg_address=4,
        compare_via=COMPARE_MODBUS,
    ),
    make_zc_write_case(
        "MODE",
        "int16",
        7,
        reg_address=5,
        compare_via=COMPARE_MQTT,
        mqtt_key="MODE",
    ),
    make_zc_write_case(
        "HMNM",
        "float",
        25.0,
        reg_address=8,
        compare_via=COMPARE_MQTT,
        mqtt_key="HMNM",
        tolerance=0.5,
    ),
]
