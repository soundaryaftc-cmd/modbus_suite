import json
import time

import paho.mqtt.client as mqtt

# ------------------------------------------------------------------
# GLOBAL MQTT STORAGE
# ------------------------------------------------------------------

mqtt_cache = {}
mqtt_listener_connected = False


def is_mqtt_listener_connected():
    return mqtt_listener_connected


latest_zc_payload = {}

zc_mode_counts = {}

# Latest expectedMode/MODE per rover (from MQTT changeEvent + xbee)
rover_modes = {}

# Per-rover API snapshot for stow-slot mode counting
rover_records = {}


def reset_zc_mqtt_state():
    """Clear ZC mode cache before a test run."""
    global latest_zc_payload
    latest_zc_payload = {}
    zc_mode_counts.clear()
    rover_modes.clear()
    rover_records.clear()

# ------------------------------------------------------------------
# TRACKER ID KEYS
# ------------------------------------------------------------------

_TRACKER_ID_KEYS = (
    "deviceID",
    "deviceId",
    "DID",
    "tracker",
    "tracker_id",
    "trackerId",
)

# ------------------------------------------------------------------
# NORMALIZE TRACKER ID
# ------------------------------------------------------------------


def normalize_tracker_id(tracker):

    return str(tracker).strip()


# ------------------------------------------------------------------
# EXTRACT TRACKER FROM PAYLOAD
# ------------------------------------------------------------------


def extract_tracker_from_payload(payload):

    if not isinstance(payload, dict):
        return None

    for key in _TRACKER_ID_KEYS:

        value = payload.get(key)

        if value is not None and str(value).strip():

            return normalize_tracker_id(value)

    return None


# ------------------------------------------------------------------
# MQTT CALLBACK
# ------------------------------------------------------------------


def _normalize_rover_mode(mode_name):
    if mode_name is None:
        return None
    return str(mode_name).strip().upper()


def _mqtt_key_for_rover_mode(mode_name):
    from config.constants import ROVER_MODE_TO_MQTT_KEY

    normalized = _normalize_rover_mode(mode_name)
    if not normalized:
        return None
    return ROVER_MODE_TO_MQTT_KEY.get(normalized)


def _count_stow_slot_modes():
    """Count locked stow slots (matches ZC Modbus mode rows more closely than expectedMode)."""
    from config.constants import ROVER_MODE_TO_MQTT_KEY

    counts = {key: 0 for key in set(ROVER_MODE_TO_MQTT_KEY.values())}
    for record in rover_records.values():
        st = record.get("current_stow_state")
        if not isinstance(st, list):
            continue
        for slot in st:
            if not isinstance(slot, dict):
                continue
            mode_name = slot.get("mode")
            mqtt_key = _mqtt_key_for_rover_mode(mode_name)
            if mqtt_key:
                counts[mqtt_key] = counts.get(mqtt_key, 0) + 1
    return counts


def rebuild_zc_mode_counts(count_style="expected"):
    """
    Aggregate mode counts for ZC Modbus comparison.
    count_style: 'expected' (expectedMode/MODE) or 'stow_slots' (current_stow_state).
    """
    from config.constants import ROVER_MODE_TO_MQTT_KEY

    zc_mode_counts.clear()

    if count_style == "stow_slots":
        zc_mode_counts.update(_count_stow_slot_modes())
    else:
        for mode_name in rover_modes.values():
            mqtt_key = _mqtt_key_for_rover_mode(mode_name)
            if mqtt_key:
                zc_mode_counts[mqtt_key] = zc_mode_counts.get(mqtt_key, 0) + 1

    for mqtt_key in set(ROVER_MODE_TO_MQTT_KEY.values()):
        zc_mode_counts.setdefault(mqtt_key, 0)


def _merge_zc_modes(payload):
    """Accumulate mode counts from direct keys and nested 'modes' object."""
    if not isinstance(payload, dict):
        return

    modes_obj = payload.get("modes")
    if isinstance(modes_obj, dict):
        for key, value in modes_obj.items():
            if value is not None:
                zc_mode_counts[str(key)] = value

    for key, value in payload.items():
        if key in ("modes",) or value is None:
            continue
        if isinstance(value, (int, float)) and str(key).isupper():
            zc_mode_counts[str(key)] = value


def _update_rover_mode_from_payload(payload):
    """Track per-rover mode from changeEvent or xbee responses."""
    if not isinstance(payload, dict):
        return

    tracker = extract_tracker_from_payload(payload)
    if not tracker:
        return

    mode_name = (
        payload.get("expectedMode")
        or payload.get("MODE")
        or payload.get("mode")
        or payload.get("trackerMode")
    )
    if mode_name is not None:
        rover_modes[tracker] = _normalize_rover_mode(mode_name)
        rebuild_zc_mode_counts("expected")

    if isinstance(payload.get("current_stow_state"), list):
        existing = rover_records.get(tracker, {})
        existing["current_stow_state"] = payload["current_stow_state"]
        rover_records[tracker] = existing


def on_message(client, userdata, msg):

    global latest_zc_payload

    try:

        payload = json.loads(
            msg.payload.decode()
        )

        # ----------------------------------------------------------
        # STORE LATEST ZC PAYLOAD
        # ----------------------------------------------------------

        latest_zc_payload = payload
        _merge_zc_modes(payload)
        _update_rover_mode_from_payload(payload)

        tracker = extract_tracker_from_payload(payload)

        if tracker is not None:

            if tracker not in mqtt_cache:

                mqtt_cache[tracker] = []

            mqtt_cache[tracker].append(payload)

        print("\nMQTT RECEIVED:")
        print(payload)

    except Exception as e:

        print("MQTT Parse Error:", e)


# ------------------------------------------------------------------
# START MQTT LISTENER
# ------------------------------------------------------------------


def start_mqtt_listener(
    broker_ip,
    topic=None,
    topics=None,
):
    """
    Connect to the zone MQTT broker and subscribe. On failure returns None
    (API-seeded mode counts still work for read tests).
    """
    global mqtt_listener_connected

    from config.constants import MQTT_BROKER_PORT, MQTT_TOPICS

    mqtt_listener_connected = False

    if topics is None:
        if topic is not None:
            topics = [topic]
        else:
            topics = list(MQTT_TOPICS)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message

    try:
        client.connect(broker_ip, MQTT_BROKER_PORT, 60)
    except (TimeoutError, OSError) as exc:
        print(
            f"\nMQTT connect failed ({broker_ip}:{MQTT_BROKER_PORT}): {exc}"
        )
        return None

    for sub_topic in topics:
        client.subscribe(sub_topic)

    client.loop_start()
    mqtt_listener_connected = True

    print(f"\nMQTT Listener Started : {', '.join(topics)}")

    return client


def stop_mqtt_listener(client):
    """Stop background loop and disconnect."""
    global mqtt_listener_connected
    if client is None:
        mqtt_listener_connected = False
        return
    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass
    mqtt_listener_connected = False


def sync_rover_modes_from_api(zone_ip):
    """Seed rover_modes from REST so MQTT aggregation has a full snapshot."""
    from utils.api_utils import fetch_rover, rover_controller_list

    payload = fetch_rover(zone_ip)
    items = rover_controller_list(payload) or []
    for item in items:
        if not isinstance(item, dict):
            continue
        did = item.get("deviceID") or item.get("deviceId")
        if not did:
            continue
        did = str(did).strip()
        rover_records[did] = item
        mode_name = item.get("expectedMode") or item.get("MODE") or item.get("mode")
        if mode_name:
            rover_modes[did] = _normalize_rover_mode(mode_name)
    return len(rover_modes)


def wait_for_mode_counts_ready(zone_ip, min_rovers=5, timeout=15):
    """
    Wait for MQTT mode aggregation: seed from API, then apply live MQTT updates.
    """
    sync_rover_modes_from_api(zone_ip)
    start = time.time()
    while time.time() - start < timeout:
        if len(rover_modes) >= min_rovers and zc_mode_counts:
            return True
        time.sleep(0.2)
    return bool(zc_mode_counts)


# ------------------------------------------------------------------
# CLEAR MQTT CACHE
# ------------------------------------------------------------------


def clear_mqtt_cache():

    mqtt_cache.clear()


# ------------------------------------------------------------------
# CLEAR TRACKER MESSAGES
# ------------------------------------------------------------------


def drain_tracker_messages(tracker):

    key = normalize_tracker_id(tracker)

    if key in mqtt_cache:

        mqtt_cache[key].clear()


# ------------------------------------------------------------------
# WAIT FOR TRACKER MQTT MESSAGE
# ------------------------------------------------------------------


def wait_for_tracker_message(
    tracker,
    timeout=10,
):

    key = normalize_tracker_id(tracker)

    start = time.time()

    while time.time() - start < timeout:

        messages = mqtt_cache.get(key)

        if messages:

            return messages.pop(0)

        time.sleep(0.2)

    return None


# ------------------------------------------------------------------
# GET MQTT VALUE FOR ZC MODE READ TESTS
# ------------------------------------------------------------------


def get_mqtt_mode_count(mqtt_key, count_style="expected", timeout=5):
    """Return aggregated MQTT mode count for a ZC Modbus mode register."""
    rebuild_zc_mode_counts(count_style)
    start = time.time()
    while time.time() - start < timeout:
        rebuild_zc_mode_counts(count_style)
        if mqtt_key in zc_mode_counts:
            return zc_mode_counts[mqtt_key]
        time.sleep(0.2)
    return zc_mode_counts.get(mqtt_key, 0)


def get_mqtt_value(
    mqtt_key,
    timeout=5,
    count_style="expected",
):

    global latest_zc_payload

    start = time.time()

    while time.time() - start < timeout:

        rebuild_zc_mode_counts(count_style)

        if mqtt_key in zc_mode_counts:
            return zc_mode_counts[mqtt_key]

        payload = latest_zc_payload

        if isinstance(payload, dict):

            if mqtt_key in payload:

                return payload[mqtt_key]

            modes = payload.get("modes")
            if isinstance(modes, dict) and mqtt_key in modes:

                return modes[mqtt_key]

        time.sleep(0.2)

    return zc_mode_counts.get(mqtt_key)


# ------------------------------------------------------------------
# VALIDATE MQTT FOR WRITE TEST CASES
# ------------------------------------------------------------------


def _stow_state_reflects_command(payload, command, written, tolerance=0):
    """True when changeEvent current_stow_state shows the command (site format)."""
    from config.constants import MODE_MAP
    from utils.validators import compare_float, compare_int

    slots = payload.get("current_stow_state")
    if not isinstance(slots, list):
        return False

    cmd = str(command).upper()
    for slot in slots:
        if not isinstance(slot, dict) or not slot:
            continue
        val = slot.get("value")
        mode = str(slot.get("mode", "")).upper()
        val_s = str(val).strip().upper() if val is not None else ""

        if cmd == "HMNM":
            if val is not None and compare_float(val, written, tolerance):
                return True

        if cmd == "MODE":
            mode_name = MODE_MAP.get(int(written)) if written is not None else None
            if mode_name and mode == mode_name.upper():
                return True

        if cmd == "STOP":
            if val_s in ("STOP", "STP", "HSTP") or mode == "STOP":
                return True
            if written and compare_int(val, written):
                return True

        if cmd == "HRST":
            if val_s in ("HRST", "RST", "RESTART", "1", "1.0"):
                return True
            if written is not None and compare_int(val, written):
                return True
            if written is not None and compare_float(val, written, tolerance):
                return True

    return False


def _change_event_reflects_command(payload, command, written, tolerance=0):
    """Match changeEvent/rover fields used after ZC broadcast writes."""
    from config.constants import MODE_MAP
    from utils.validators import compare_float, compare_int

    cmd = str(command).upper()

    if cmd == "MODE":
        mode_name = MODE_MAP.get(int(written)) if written is not None else None
        if mode_name:
            target = mode_name.upper()
            for key in ("expectedMode", "currentMode"):
                actual = payload.get(key)
                if actual and str(actual).strip().upper() == target:
                    return True
            status = payload.get("status")
            if isinstance(status, dict):
                actual = status.get("currentMode")
                if actual and str(actual).strip().upper() == target:
                    return True
        if _stow_state_reflects_command(payload, "MODE", written, tolerance):
            return True

    if cmd == "HMNM":
        if _stow_state_reflects_command(payload, "HMNM", written, tolerance):
            return True
        rc_meta = payload.get("rc_cmd_meta")
        if isinstance(rc_meta, dict):
            hmnm = rc_meta.get("HMNM")
            if isinstance(hmnm, dict):
                values = hmnm.get("VALUES")
                if values is not None and compare_float(values, written, tolerance):
                    return True

    if cmd == "CFLT":
        rc_meta = payload.get("rc_cmd_meta")
        if isinstance(rc_meta, dict) and "CFLT" in rc_meta:
            return True
        for key in ("cflt", "CFLT", "collisionFault", "collision_fault"):
            if key in payload and compare_int(payload[key], written):
                return True

    return False


def validate_mqtt_for_case(
    payload,
    case,
    tracker,
):
    """
    Confirm MQTT payload is for this tracker
    and reflects the write case.

    Returns:
        (ok: bool, error: str | None)
    """
    from config.case_schema import case_tolerance, case_value, normalize_case
    from config.constants import MODE_MAP

    from utils.validators import (
        compare_float,
        compare_int,
    )

    case = normalize_case(case)

    # --------------------------------------------------------------
    # PAYLOAD VALIDATION
    # --------------------------------------------------------------

    if not isinstance(payload, dict):

        return (
            False,
            "MQTT payload is not a JSON object",
        )

    # --------------------------------------------------------------
    # TRACKER VALIDATION
    # --------------------------------------------------------------

    payload_tracker = extract_tracker_from_payload(
        payload
    )

    expected_tracker = normalize_tracker_id(
        tracker
    )

    if payload_tracker != expected_tracker:

        return (
            False,
            (
                f"tracker mismatch: "
                f"{payload_tracker!r} "
                f"!= "
                f"{expected_tracker!r}"
            ),
        )

    command = case["name"]

    written = case_value(case)

    tolerance = case_tolerance(case)

    # --------------------------------------------------------------
    # OPTIONAL EVENT VALIDATION
    # --------------------------------------------------------------

    expected_event = case.get(
        "expected_event"
    )

    if expected_event:

        actual_event = (
            payload.get("event")
            or payload.get("type")
            or payload.get("status")
        )

        if actual_event != expected_event:

            return (
                False,
                (
                    f"event mismatch: "
                    f"{actual_event!r} "
                    f"!= "
                    f"{expected_event!r}"
                ),
            )

    # --------------------------------------------------------------
    # OPTIONAL KEY VALIDATION
    # --------------------------------------------------------------

    expected_key = case.get(
        "expected_key"
    )

    if expected_key is not None:

        expected_value = case.get(
            "expected_value"
        )

        actual_value = payload.get(
            expected_key
        )

        if actual_value != expected_value:

            return (
                False,
                (
                    f"{expected_key} mismatch: "
                    f"{actual_value!r} "
                    f"!= "
                    f"{expected_value!r}"
                ),
            )

    # --------------------------------------------------------------
    # MODE VALIDATION
    # --------------------------------------------------------------

    if command == "MODE":

        if _change_event_reflects_command(payload, "MODE", written, tolerance):
            # #region agent log
            from utils.debug_log import agent_log

            agent_log(
                "B",
                "mqtt_utils.py:validate_mqtt_for_case",
                "mode_ok_change_event",
                {"expectedMode": payload.get("expectedMode")},
            )
            # #endregion
            return True, None

        for key in (
            "mode",
            "MODE",
            "value",
            "trackerMode",
            "tracker_mode",
        ):

            if key not in payload:
                continue

            actual = payload[key]

            mode_name = MODE_MAP.get(
                int(written)
            )

            if (
                mode_name
                and str(actual).strip().upper()
                == mode_name.upper()
            ):

                return True, None

            if compare_int(
                actual,
                written,
            ):

                return True, None

        values = payload.get("VALUES")
        if isinstance(values, str):
            mode_token = values.lstrip("[").split(",")[0].strip()
            mode_name = MODE_MAP.get(int(written))
            if (
                mode_name
                and mode_token.upper() == mode_name.upper()
            ):
                return True, None

        return (
            False,
            "MODE value not found in MQTT payload",
        )

    # --------------------------------------------------------------
    # HMNM VALIDATION
    # --------------------------------------------------------------

    if command == "HMNM":

        if _change_event_reflects_command(payload, "HMNM", written, tolerance):
            # #region agent log
            from utils.debug_log import agent_log

            agent_log(
                "A",
                "mqtt_utils.py:validate_mqtt_for_case",
                "hmnm_ok_stow",
                {"stow": payload.get("current_stow_state")},
            )
            # #endregion
            return True, None

        for key in (
            "hmnm",
            "HMNM",
            "angle",
            "manualAngle",
            "targetAngle",
            "value",
            "PANGLE",
            "CANGLE",
        ):

            if (
                key in payload
                and compare_float(
                    payload[key],
                    written,
                    tolerance,
                )
            ):

                return True, None

        values = payload.get("VALUES")
        if isinstance(values, str):
            try:
                angle = float(values.split(",")[1])
                if compare_float(angle, written, tolerance):
                    return True, None
            except (IndexError, ValueError, TypeError):
                pass

        return (
            False,
            "HMNM angle not found in MQTT payload",
        )

    # --------------------------------------------------------------
    # CFLT VALIDATION
    # --------------------------------------------------------------

    if command == "CFLT":

        if _change_event_reflects_command(payload, "CFLT", written, tolerance):
            # #region agent log
            from utils.debug_log import agent_log

            agent_log(
                "C",
                "mqtt_utils.py:validate_mqtt_for_case",
                "cflt_ok_change_event",
                {"rc_cmd_meta": list((payload.get("rc_cmd_meta") or {}).keys())},
            )
            # #endregion
            return True, None

        for key in (
            "cflt",
            "CFLT",
            "value",
            "collisionFault",
        ):

            if (
                key in payload
                and compare_int(
                    payload[key],
                    written,
                )
            ):

                return True, None

        return (
            False,
            "CFLT value not found in MQTT payload",
        )

    if command == "STOP":
        if _stow_state_reflects_command(payload, "STOP", written):
            # #region agent log
            from utils.debug_log import agent_log

            agent_log(
                "C",
                "mqtt_utils.py:validate_mqtt_for_case",
                "stop_ok_stow",
                {"stow": payload.get("current_stow_state")},
            )
            # #endregion
            return True, None
        for key in ("stop", "STOP", "status", "value"):
            if key in payload and compare_int(payload[key], written):
                return True, None
        if written and payload.get("CMD") in ("STOP", "STP", "HSTP"):
            return True, None
        # #region agent log
        from utils.debug_log import agent_log

        agent_log(
            "C",
            "mqtt_utils.py:validate_mqtt_for_case",
            "stop_reject",
            {
                "stow": payload.get("current_stow_state"),
                "cmd": payload.get("CMD"),
            },
        )
        # #endregion
        return False, "STOP not reflected in MQTT payload"

    if command == "HRST":
        if _stow_state_reflects_command(payload, "HRST", written, tolerance):
            # #region agent log
            from utils.debug_log import agent_log

            agent_log(
                "D",
                "mqtt_utils.py:validate_mqtt_for_case",
                "hrst_ok_stow",
                {"stow": payload.get("current_stow_state")},
            )
            # #endregion
            return True, None
        for key in ("hrst", "HRST", "restart", "value"):
            if key in payload and compare_int(payload[key], written):
                return True, None
        if written and payload.get("CMD") in ("HRST", "RST", "RESTART"):
            return True, None
        # #region agent log
        from utils.debug_log import agent_log

        agent_log(
            "D",
            "mqtt_utils.py:validate_mqtt_for_case",
            "hrst_reject",
            {
                "stow": payload.get("current_stow_state"),
                "cmd": payload.get("CMD"),
            },
        )
        # #endregion
        return False, "HRST not reflected in MQTT payload"

    return True, None


def wait_for_write_mqtt(
    case,
    tracker=None,
    timeout=20,
):
    """
    After a write, wait for an MQTT payload that validates the command.
    If tracker is None (ZC broadcast), accept the first matching rover message.
    """
    from config.case_schema import normalize_case
    from config.constants import MQTT_BROKER_PORT, ZONE_IP

    case = normalize_case(case)

    if not mqtt_listener_connected:
        return (
            False,
            None,
            f"MQTT broker unreachable at {ZONE_IP}:{MQTT_BROKER_PORT}",
        )

    start = time.time()
    while time.time() - start < timeout:
        if tracker:
            key = normalize_tracker_id(tracker)
            messages = mqtt_cache.get(key, [])
            for payload in reversed(messages):
                ok, err = validate_mqtt_for_case(payload, case, tracker)
                if ok:
                    return True, payload, None
        else:
            for messages in mqtt_cache.values():
                for payload in reversed(messages):
                    did = extract_tracker_from_payload(payload) or "broadcast"
                    ok, err = validate_mqtt_for_case(payload, case, did)
                    if ok:
                        return True, payload, None
        time.sleep(0.2)
    # #region agent log
    from utils.debug_log import agent_log

    agent_log(
        "E",
        "mqtt_utils.py:wait_for_write_mqtt",
        "mqtt_wait_timeout",
        {
            "command": case.get("name"),
            "tracker": tracker,
            "cache_trackers": len(mqtt_cache),
            "cache_messages": sum(len(v) for v in mqtt_cache.values()),
        },
    )
    # #endregion
    return False, None, "MQTT verification timeout"