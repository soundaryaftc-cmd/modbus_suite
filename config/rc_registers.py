TRACKER_OFFSETS = {
    "tracker_id": 0,
    "latitude": 6,
    "longitude": 8,
    "altitude": 10,
    "device_id": 12,
    "angle": 17,
    "timestamp": 19,
    "battery_voltage": 21,
    "pv_voltage": 23,
    "tracker_mode": 25,
    "spa_present": 30,
    "spa_targeted": 32,
    "alerts_1": 34,
    "tracker_status": 35,
    "alerts_2": 39,
    "alerts_3": 40,
    "battery_soc": 41,
}

FIELD_SPECS = {

    "latitude": {
        "dtype": "float",
        "count": 2,
        "tolerance": 0.01,
        "modbus_table": "input",
    },

    "longitude": {
        "dtype": "float",
        "count": 2,
        "tolerance": 0.01,
        "modbus_table": "input",
    },

    "altitude": {
        "dtype": "float",
        "count": 2,
        "tolerance": 0.5,
        "modbus_table": "input",
    },

    "battery_voltage": {
        "dtype": "float",
        "count": 2,
        "tolerance": 0.5,
    },

    "pv_voltage": {
        "dtype": "float",
        "count": 2,
        "tolerance": 0.5,
    },

    "timestamp": {
        "dtype": "int32",
        "count": 2,
        "tolerance": 5,
    },

    "tracker_mode": {
        "dtype": "str",
        "count": 5,
    },

    "tracker_status": {
        "dtype": "bool",
        "count": 1,
    },
}

FIELDS_TO_CHECK = [
    "latitude",
    "longitude",
    "altitude",
]
MODE_OFFSET = 0
STOP_OFFSET = 1
CFLT_OFFSET = 2
PITCH_OFFSET = 3
HMNM_OFFSET = 5
HRST_OFFSET = 7

from config.case_schema import COMPARE_MODBUS, make_rc_write_case

MODE_TEST_VALUES = [1, 2, 3, 4, 5, 6, 7, 8]
CFLT_TEST_VALUES = [1]
HMNM_TEST_ANGLES = [-50.0, -25.0, 0.0, 25.0, 50.0]


def build_write_cases():
    """Full RC write sweep for writerc.py CLI (readback-only validation)."""
    cases = []

    for value in MODE_TEST_VALUES:
        cases.append(
            make_rc_write_case(
                "MODE",
                "int16",
                value,
                MODE_OFFSET,
                compare_via=COMPARE_MODBUS,
                tolerance=0,
            )
        )

    for value in CFLT_TEST_VALUES:
        cases.append(
            make_rc_write_case(
                "CFLT",
                "int16",
                value,
                CFLT_OFFSET,
                compare_via=COMPARE_MODBUS,
                tolerance=0,
            )
        )

    for value in HMNM_TEST_ANGLES:
        cases.append(
            make_rc_write_case(
                "HMNM",
                "float",
                value,
                HMNM_OFFSET,
                compare_via=COMPARE_MODBUS,
                tolerance=0.5,
            )
        )

    return cases