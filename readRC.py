from config.constants import DEFAULT_PORT, ZONE_IP
from config.rc_registers import FIELDS_TO_CHECK, FIELD_SPECS
from utils.api_utils import fetch_rover, get_rc_tracker_field, rover_controller_list
from utils.modbus_utils import create_client, read_register_data
from utils.tracker_utils import calculate_register
from utils.validators import compare_values


def get_trackers_from_api(ip):
    payload = fetch_rover(ip)
    return rover_controller_list(payload) or []


def main():
    zone_ip = ZONE_IP
    trackers = get_trackers_from_api(zone_ip)
    client = create_client(zone_ip, port=DEFAULT_PORT)

    if not client.connect():
        print(f"FAIL: Could not connect to {zone_ip}:{DEFAULT_PORT}")
        return

    total_pass = 0
    total_fail = 0

    try:
        for tracker in trackers:
            tracker_name = tracker.get("deviceID") or tracker.get("device_id")
            if not tracker_name:
                continue

            failed_fields = []

            for field_name in FIELDS_TO_CHECK:
                spec = FIELD_SPECS[field_name]
                dtype = spec["dtype"]
                tolerance = spec.get("tolerance", 0.5)
                api_val = get_rc_tracker_field(tracker, field_name)

                reg_address = calculate_register(tracker_name, field_name)
                modbus_dtype = "float" if dtype == "float" else dtype
                modbus_table = spec.get("modbus_table", "holding")
                modbus_val = read_register_data(
                    client,
                    reg_address,
                    modbus_dtype,
                    modbus_table=modbus_table,
                )

                result = compare_values(
                    dtype,
                    modbus_val,
                    api_val,
                    tolerance,
                )

                if result:
                    total_pass += 1
                else:
                    total_fail += 1
                    failed_fields.append(field_name)

            if failed_fields:
                print(f"{tracker_name}: FAIL -> {failed_fields}")
            else:
                print(f"{tracker_name}: PASS")

    finally:
        client.close()

    print("\n===== SUMMARY =====")
    print("PASS:", total_pass)
    print("FAIL:", total_fail)


if __name__ == "__main__":
    main()
