from config.constants import TARGET_RCS, ZONE_IP
from config.rc_registers import FIELDS_TO_CHECK, FIELD_SPECS, TRACKER_OFFSETS
from utils.api_utils import fetch_rover, find_rc, get_rc_tracker_field
from utils.modbus_utils import create_client, read_register_data
from utils.report_utils import print_unresolved_errors
from utils.tracker_utils import calculate_register
from utils.validation_engine import validate_read_rc_field
from config.case_schema import make_rc_read_case, normalize_case

def _read_case_for_field(field_name):
  spec = FIELD_SPECS[field_name]
  offset = TRACKER_OFFSETS[field_name]
  return make_rc_read_case(
      field_name,
      spec["dtype"],
      offset,
      tolerance=spec.get("tolerance", 0.5),
      modbus_table=spec.get("modbus_table", "input"),
  )


def test_read_rc():

    errors = []
    client = create_client(ZONE_IP)

    try:
        if not client.connect():
            errors.append({
                "step": "Modbus connect",
                "error": f"Could not connect to {ZONE_IP}:502",
            })
        else:
            payload = fetch_rover(ZONE_IP)
            if payload is None:
                errors.append({
                    "step": "fetch_rover",
                    "error": "Rover API returned None",
                })
            else:
                for tracker_id in TARGET_RCS:
                    print("\n" + "=" * 70)
                    print(f"TESTING TRACKER : {tracker_id}")
                    print("=" * 70)

                    rc_data = find_rc(payload, tracker_id)
                    if rc_data is None:
                        errors.append({
                            "step": "find_rc",
                            "tracker": tracker_id,
                            "error": f"Tracker {tracker_id!r} not found",
                        })
                        continue

                    for field_name in FIELDS_TO_CHECK:
                        case = _read_case_for_field(field_name)
                        row = normalize_case(case)
                        api_val = get_rc_tracker_field(rc_data, field_name)
                        reg_address = calculate_register(tracker_id, field_name)

                        modbus_dtype = (
                            "float" if row["dtype"] == "float" else row["dtype"]
                        )
                        modbus_val = read_register_data(
                            client,
                            reg_address,
                            modbus_dtype,
                            modbus_table=row["modbus_table"],
                        )

                        ok, err = validate_read_rc_field(
                            row, modbus_val, api_val
                        )
                        if not ok:
                            errors.append({
                                "step": f"Compare {field_name}",
                                "tracker": tracker_id,
                                "error": err,
                                "modbus": modbus_val,
                                "api": api_val,
                                "register": reg_address,
                            })

    finally:
        client.close()

    print_unresolved_errors("test_read_rc", errors)
    assert not errors, f"FAILED: {errors}"
