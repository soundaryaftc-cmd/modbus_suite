"""
Central validation routing for read/write tests.
All cases are normalized via config.case_schema before use.
"""

from config.case_schema import (
    COMPARE_API,
    COMPARE_MODBUS,
    COMPARE_MQTT,
    case_modbus_table,
    case_mqtt_timeout,
    case_tolerance,
    case_value,
    compare_via,
    normalize_case,
    resolve_api_url,
    should_compare,
)


def validate_modbus_readback(case, readback):
    """Modbus holding-register readback matches written value."""
    from utils.write_utils import verify_rc_write_case

    c = normalize_case(case)
    if verify_rc_write_case(
        c["name"],
        readback,
        case_value(c),
        case_tolerance(c),
        api_value=None,
    ):
        return True, None

    return False, "Modbus readback does not match written value"


def fetch_api_expected_write(case, tracker=None, zone_ip=None):
    """Resolve API expected value for a write case row."""
    from config.constants import ZONE_IP
    from utils.api_utils import (
        fetch_rover,
        find_rc,
        get_api_value,
        get_rc_api_value,
    )

    c = normalize_case(case)
    zone_ip = zone_ip or ZONE_IP

    if tracker and not c.get("key") and not c.get("key_path"):
        payload = fetch_rover(zone_ip)
        rc_data = find_rc(payload, tracker) if payload else None
        if rc_data is None:
            return None
        return get_rc_api_value(rc_data, c["name"])

    api_url = resolve_api_url(c, zone_ip)
    if api_url:
        return get_api_value(
            api_url=api_url,
            key=c.get("key"),
            key_path=c.get("key_path"),
            combine_keys=c.get("combine_keys"),
            count_rule=c.get("count_rule"),
        )

    if tracker:
        payload = fetch_rover(zone_ip)
        rc_data = find_rc(payload, tracker) if payload else None
        if rc_data is None:
            return None
        return get_rc_api_value(rc_data, c["name"])

    return None


def validate_write_post(case, readback, tracker=None, api_value=None, mqtt_payload=None):
    """
    Post-write validation (API or MQTT). Modbus-only cases skip this step.
    Returns (ok: bool, error: str | None).
    """
    c = normalize_case(case)
    via = compare_via(c)

    if via == COMPARE_MODBUS:
        return True, None

    if via == COMPARE_API:
        from utils.write_utils import verify_rc_write_case
        from utils.debug_log import agent_log

        if api_value is None:
            api_value = fetch_api_expected_write(c, tracker=tracker)

        # #region agent log
        agent_log(
            "A",
            "validation_engine.py:validate_write_post",
            "api_compare",
            {
                "command": c.get("name"),
                "api_value": api_value,
                "readback": readback,
                "written": case_value(c),
            },
        )
        # #endregion

        if verify_rc_write_case(
            c["name"],
            readback,
            case_value(c),
            case_tolerance(c),
            api_value=api_value,
        ):
            return True, None

        return False, f"API mismatch (api={api_value!r}, readback={readback!r})"

    if via == COMPARE_MQTT:
        from utils.mqtt_utils import validate_mqtt_for_case

        if mqtt_payload is None:
            return False, "MQTT payload missing"

        ok, err = validate_mqtt_for_case(
            mqtt_payload,
            c,
            tracker or "broadcast",
        )
        if ok:
            return True, None
        return False, err or "MQTT validation failed"

    return False, f"Unknown compare_via: {via!r}"


def resolve_and_validate(
    case,
    modbus_val,
    api_value=None,
    mqtt_value=None,
    mqtt_payload=None,
    tracker=None,
):
    """Single entry for write validation (readback + post-check)."""
    c = normalize_case(case)
    readback_ok, readback_err = validate_modbus_readback(c, modbus_val)
    if not readback_ok:
        return False, readback_err

    return validate_write_post(
        c,
        modbus_val,
        tracker=tracker,
        api_value=api_value,
        mqtt_payload=mqtt_payload,
    )


def run_post_write_validation(case, readback, tracker=None, mqtt_timeout=25):
    """
    Modbus readback + API or MQTT post-check for one write case.
    Returns (ok, error, extra).
    """
    from utils.mqtt_utils import is_mqtt_listener_connected

    c = normalize_case(case)
    ok, err = validate_modbus_readback(c, readback)
    if not ok:
        return False, err, None

    via = compare_via(c)

    if via == COMPARE_MODBUS:
        return True, None, None

    if via == COMPARE_MQTT and not is_mqtt_listener_connected():
        return (
            False,
            "MQTT broker unreachable; cannot verify MQTT write",
            None,
        )

    if via == COMPARE_API:
        api_value = fetch_api_expected_write(c, tracker=tracker)
        ok, err = validate_write_post(
            c,
            readback,
            tracker=tracker,
            api_value=api_value,
        )
        return ok, err, {"api": api_value}

    mqtt_ok, payload, mqtt_err = validate_write_mqtt(
        c,
        tracker=tracker,
        timeout=case_mqtt_timeout(c, default=mqtt_timeout),
    )
    if not mqtt_ok:
        return False, mqtt_err, {"payload": payload}

    return True, None, {"payload": payload}


def validate_write_mqtt(case, tracker=None, timeout=25):
    """Wait for MQTT confirmation of a write. Returns (ok, payload, error)."""
    from utils.mqtt_utils import wait_for_write_mqtt

    c = normalize_case(case)
    return wait_for_write_mqtt(
        c,
        tracker=tracker,
        timeout=case_mqtt_timeout(c, default=timeout),
    )


def validate_read_zc(reg, modbus_val, expected_val):
    """
    Compare ZC Modbus read to API or MQTT expected value.
    Returns (ok, error, source).
    """
    c = normalize_case(reg)

    if not should_compare(c):
        return True, None, "skip"

    via = compare_via(c)
    source = "MQTT" if via == COMPARE_MQTT else "API"

    if expected_val is None:
        return False, f"{source} expected value missing", source

    from utils.validators import compare_zc_register, validator

    if via == COMPARE_MQTT:
        result = validator(
            modbus_val,
            expected_val,
            c["dtype"],
            tolerance=c.get("tolerance"),
        )
    else:
        result = compare_zc_register(c, modbus_val, expected_val)

    mask = c.get("compare_mask")
    if (
        not result
        and mask is not None
        and c["dtype"] == "int"
        and modbus_val is not None
        and expected_val is not None
    ):
        result = (int(modbus_val) & mask) == (int(expected_val) & mask)

    if result:
        return True, None, source

    return False, f"Modbus value does not match {source}", source


def fetch_expected_read_zc(case):
    """Fetch expected value for a ZC read row per compare_via."""
    c = normalize_case(case)
    via = compare_via(c)

    if via == COMPARE_MQTT:
        return fetch_expected_read_zc_mqtt(c)
    return fetch_expected_read_zc_api(c)


def fetch_expected_read_zc_api(case):
    from utils.api_utils import get_api_value

    c = normalize_case(case)
    return get_api_value(
        api_url=c["api_url"],
        key=c.get("key"),
        key_path=c.get("key_path"),
        combine_keys=c.get("combine_keys"),
        count_rule=c.get("count_rule"),
    )


def fetch_expected_read_zc_mqtt(case, count_style=None):
    from utils.mqtt_utils import get_mqtt_value

    c = normalize_case(case)
    style = count_style or c.get("mqtt_count", "expected")
    return get_mqtt_value(mqtt_key=c["mqtt_key"], count_style=style)


def validate_read_rc_field(case, modbus_val, api_val):
    """Compare RC field Modbus read to API value."""
    from utils.validators import compare_values

    c = normalize_case(case)

    if modbus_val is None:
        return False, "read_register_data returned None"

    if compare_values(
        c["dtype"],
        modbus_val,
        api_val,
        case_tolerance(c),
    ):
        return True, None

    return False, "Modbus value does not match API"
