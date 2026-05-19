import os

import requests

from config.constants import API_TIMEOUT
from utils.tracker_utils import (
    get_tracker_number,
    tracker_modbus_addresses_valid,
)


# =========================================================
# JSON HELPERS
# =========================================================

def find_key(data, target_key):

    if isinstance(data, dict):

        for key, value in data.items():

            if key == target_key:
                return value

            result = find_key(value, target_key)

            if result is not None:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_key(item, target_key)

            if result is not None:
                return result

    return None


def find_key_path(data, key_path):

    current = data

    for part in key_path.split("."):

        if not isinstance(current, dict):
            return None

        current = current.get(part)

        if current is None:
            return None

    return current


def count_field_value(obj, field, expected_value):

    if isinstance(obj, list):

        return sum(
            count_field_value(item, field, expected_value)
            for item in obj
        )

    if isinstance(obj, dict):

        count = 0

        if obj.get(field) == expected_value:
            count += 1

        for value in obj.values():

            count += count_field_value(
                value,
                field,
                expected_value
            )

        return count

    return 0



def rover_controller_list(data):
    """Rover list from /flask/rover/get/no_time_diff (message = [...], same idea as writerc)."""
    if isinstance(data, dict):
        msg = data.get("message")
        if isinstance(msg, list):
            return msg
    if isinstance(data, list):
        return data
    return None


def fetch_rover(ip):
    url = f"http://{ip}/flask/rover/get/no_time_diff"
    try:
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code != 200:
            print("FAIL: Rover API request failed")
            return None
        return response.json()
    except Exception as e:
        print("API Error:", str(e))
        return None


def find_rc(data, device_id):
    items = rover_controller_list(data)
    if not items:
        return None
    target = str(device_id).strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = item.get("deviceID", item.get("deviceId", ""))
        if str(rid).strip() == target:
            return item
    return None


_RC_API_PATHS = {
    "latitude": "controllerInfo.position.lat",
    "longitude": "controllerInfo.position.lng",
    "altitude": "controllerInfo.position.alt",
    "battery_voltage": "power.batteryVoltage",
    "pv_voltage": "power.pvVoltage",
    "timestamp": "power.timeStamp",
    "tracker_mode": "expectedMode",
    "tracker_status": "online",
}


def get_rc_tracker_field(rc_data, field_name):
    """Resolve rover field from nested API paths used by the rover payload."""
    if not isinstance(rc_data, dict):
        return None

    path = _RC_API_PATHS.get(field_name)
    if path:
        return find_key_path(rc_data, path)

    return rc_data.get(field_name)


def pick_rcs_by_row_branches(payload, require_both=True):
    """One rover with row < 100 and one with row >= 100 (valid Modbus addresses)."""
    items = rover_controller_list(payload) or []
    below_100 = None
    above_100 = None

    for item in items:
        if not isinstance(item, dict):
            continue
        did = item.get("deviceID") or item.get("device_id")
        if not did:
            continue
        did = str(did).strip()
        if not did:
            continue
        try:
            row = get_tracker_number(did)
        except ValueError:
            continue
        if not tracker_modbus_addresses_valid(did):
            continue
        if row < 100 and below_100 is None:
            below_100 = did
        elif row >= 100 and above_100 is None:
            above_100 = did

    targets = [t for t in (below_100, above_100) if t]
    if require_both and (below_100 is None or above_100 is None):
        return None
    return targets or None


def resolve_write_rc_targets(payload):
    """TARGET_RCS env, then TARGET_RC env, then API row-branch pair."""
    explicit_list = os.environ.get("TARGET_RCS", "").strip()
    if explicit_list:
        return [part.strip() for part in explicit_list.split(",") if part.strip()]

    single = os.environ.get("TARGET_RC", "").strip()
    if single:
        return [single]

    return pick_rcs_by_row_branches(payload, require_both=True)


_RC_API_FIELD_KEYS = {
    "MODE": (
        "trackerMode",
        "TrackerMode",
        "MODE",
        "mode",
        "tracker_mode",
    ),
    "CFLT": ("cflt", "CFLT", "collisionFault", "collision_fault"),
    "HMNM": (
        "hmnm",
        "HMNM",
        "manualAngle",
        "manualTarget",
        "targetAngle",
        "target_angle",
    ),
}


def _nested_rc_value(rc_data, *paths):
    """Walk dotted paths; return first value found."""
    for path in paths:
        node = rc_data
        for part in path.split("."):
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if node is not None:
            return node
    return None


def get_rc_api_value(rc_data, command):
    if not isinstance(rc_data, dict):
        return None
    for key in _RC_API_FIELD_KEYS.get(command, (command,)):
        if key in rc_data:
            val = rc_data[key]
            # #region agent log
            if command == "HMNM":
                from utils.debug_log import agent_log

                agent_log(
                    "A",
                    "api_utils.py:get_rc_api_value",
                    "hmnm_top_level",
                    {"key": key, "value": val},
                )
            # #endregion
            return val

    if command == "HMNM":
        nested = _nested_rc_value(
            rc_data,
            "controllerInfo.stow.manualAngle",
            "status.manualAngle",
            "status.targetAngle",
        )
        # #region agent log
        from utils.debug_log import agent_log

        agent_log(
            "B",
            "api_utils.py:get_rc_api_value",
            "hmnm_nested",
            {"value": nested, "top_manualAngle": rc_data.get("manualAngle")},
        )
        # #endregion
        if nested is not None:
            return nested

    return None


def count_rover_rows(data):
    items = rover_controller_list(data)
    if not items:
        return 0
    return sum(
        1
        for item in items
        if isinstance(item, dict) and str(item.get("deviceID", "")).strip()
    )


def value_matches_for_count(actual, expected):
    if actual == expected:
        return True
    if isinstance(expected, bool):
        if isinstance(actual, str):
            s = actual.strip().lower()
            if expected is True:
                return s in ("true", "1", "yes")
            return s in ("false", "0", "no", "")
        if isinstance(actual, (int, float)) and not isinstance(actual, bool):
            return bool(actual) is expected
    return False


def count_rover_controller_field(data, field, expected_value):
    items = rover_controller_list(data)
    if not items:
        return 0
    n = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if not str(item.get("deviceID", "")).strip():
            continue
        if value_matches_for_count(item.get(field), expected_value):
            n += 1
    return n


def get_sensor_scalar(data, name):
    """
    Resolve wind speed/direction from /flask/sensors/values.
    Prefer explicit message.* paths so we do not pick a nested key from another subtree.
    """
    if not isinstance(data, dict):
        return None
    for path in (
        f"message.{name}",
        f"message.wind.{name}",
        f"message.sensor.{name}",
    ):
        v = find_key_path(data, path)
        if v is not None:
            return v
    return find_key(data, name)


def alerts_connectivity_dict_al1(data):
    """
    Dict carrying zone AL1 connectivity flags.
    Supports message as dict, message as list of dicts, or flags at the root.
    """
    keys = (
        "windSensorConnected",
        "floodSensorConnected",
        "snowSensorConnected",
        "zigbee1",
        "zigbee2",
        "wlan",
        "bqConnect",
        "bqUpload",
    )
    if not isinstance(data, dict):
        return None
    msg = data.get("message")
    if isinstance(msg, dict) and any(k in msg for k in keys):
        return msg
    if isinstance(msg, list):
        for item in msg:
            if isinstance(item, dict) and any(k in item for k in keys):
                return item
    if any(k in data for k in keys):
        return data
    return None


def alerts_connectivity_dict_al2(data):
    """Same pattern as AL1 for AL2 / service flags."""
    keys = (
        "dbConnection",
        "batteryHealthy",
        "storageLimitExceeded",
        "highTemperature",
        "serviceDisabled",
        "ntpSync",
        "gpsSync",
    )
    if not isinstance(data, dict):
        return None
    msg = data.get("message")
    if isinstance(msg, dict) and any(k in msg for k in keys):
        return msg
    if isinstance(msg, list):
        for item in msg:
            if isinstance(item, dict) and any(k in item for k in keys):
                return item
    if any(k in data for k in keys):
        return data
    return None


def coerce_int_if_numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def parse_both_version(data):

    h_ver = find_key(data, "hVersion")
    s_ver = find_key(data, "sVersion")

    if h_ver is None or s_ver is None:
        return None

    return f"{h_ver}*{s_ver}"


def parse_alert1_bits(data):

    msg = alerts_connectivity_dict_al1(data)

    if not isinstance(msg, dict):
        return None

    # Dashboard: only flood + snow (sensor connected) drive AL1 for this check; ignore other bits
    bit_rules = {
        10: not msg.get("floodSensorConnected", True),
        8: not msg.get("snowSensorConnected", True),
    }

    if not any(bit_rules.values()):
        return 0

    alert_value = 0

    for bit, is_error in bit_rules.items():

        if is_error:
            alert_value |= (1 << bit)

    return alert_value

def parse_alert2_bits(data):
    """
    Alert2 Bit Mapping
    Decimal Address: 54

    N/A bits are ignored completely.
    """

    msg = alerts_connectivity_dict_al2(data)

    if not isinstance(msg, dict):
        return None
    bit_rules = {
        15: not msg.get("dbConnection", True),
        14: bool(msg.get("storageLimitExceeded", False)),
        13: not msg.get("batteryHealthy", True),
        11: bool(msg.get("storageLimitExceeded", False)),
        10: bool(msg.get("highTemperature", False)),
        9: bool(msg.get("serviceDisabled", False)),
        8: not msg.get("ntpSync", True),
        7: not msg.get("gpsSync", True),
    }

    if not any(bit_rules.values()):
        return 0

    alert_value = 0

    for bit, is_error in bit_rules.items():

        if is_error:
            alert_value |= (1 << bit)

    return alert_value

def count_device_ids(obj):
    """
    Count total number of device IDs in API response.
    """
    if isinstance(obj, list):

        return sum(
            count_device_ids(item)
            for item in obj
        )
    if isinstance(obj, dict):

        count = 0

        # count only deviceID occurrences
        if "deviceID" in obj:
            count += 1

        for value in obj.values():

            count += count_device_ids(value)

        return count

    return 0

def get_api_value(
    api_url,
    key=None,
    key_path=None,
    combine_keys=None,
    count_rule=None
):

    try:

        response = requests.get(api_url, timeout=API_TIMEOUT)

        if response.status_code != 200:
            print("FAIL: API request failed")
            return None

        data = response.json()

        # print("API Data:", data)

        # Nested path
        if key_path:
            return find_key_path(data, key_path)

        # Special parsers
        if key == "bothVersion":
            return parse_both_version(data)

        if key in ("alert1Bits", "alertBits"):
            parsed = parse_alert1_bits(data)
            if parsed is not None:
                return parsed
            for raw_key in ("alert1Bits", "alertBits", "alert1", "zoneAlert1"):
                raw = find_key(data, raw_key)
                coerced = coerce_int_if_numeric(raw)
                if coerced is not None:
                    return coerced
            return None

        if key == "alert2Bits":
            for raw_key in ("alert2Bits", "alert2", "zoneAlert2"):
                raw = find_key(data, raw_key)
                coerced = coerce_int_if_numeric(raw)
                if coerced is not None:
                    return coerced
            return parse_alert2_bits(data)

        if key == "device_count":
            return count_device_ids(data)

        if key in ("speed", "direction"):
            return get_sensor_scalar(data, key)

        # Count logic
        if count_rule:

            mode = count_rule.get("mode")

            if mode == "rover_rows":
                return count_rover_rows(data)

            if mode == "rover_controller_field":
                return count_rover_controller_field(
                    data,
                    count_rule.get("field"),
                    count_rule.get("value"),
                )

            return count_field_value(
                data,
                count_rule.get("field"),
                count_rule.get("value"),
            )

        # Combine values
        if combine_keys:

            total = 0

            for field in combine_keys:

                value = find_key(data, field)

                if value is None:
                    return None

                total += int(value)

            return total

        # Normal key
        return find_key(data, key)

    except Exception as e:

        print("API Error:", str(e))
        return None