"""
Standard case dict schema for read/write Modbus tests.

Write case (RC or ZC command)
-----------------------------
  name          str       Command id: MODE, CFLT, HMNM, STOP, ...
  dtype         str       int16 | float | int | str | int32 | bool
  value         number    Value written to Modbus (required for writes)
  tolerance     number    Compare tolerance (default 0)
  compare       bool      False = skip validation (default True)
  compare_via   str       api | mqtt | modbus (modbus = readback only)
  reg_address   int       Absolute holding address (ZC)
  offset        int       Offset from RC tracker base (RC)
  modbus_table  str       holding | input (default holding for writes)

  API (compare_via=api):
  api_url, key, key_path, combine_keys, count_rule

  MQTT (compare_via=mqtt):
  mqtt_key      str       Topic payload key (defaults to upper(name))

Read case (ZC register row or RC field)
---------------------------------------
  Same compare_* / API / MQTT fields as above, plus:
  length        int       Register length in bytes (ZC read)
  modbus_table  str       input | holding (RC reads often input)
  mqtt_count    str       expected | stow_slots (ZC MQTT mode aggregation)
  compare_mask, compare_int_width, compare_mask_ignore, missing_reading_float
"""

from config.constants import ZONE_IP

# compare_via values
COMPARE_API = "api"
COMPARE_MQTT = "mqtt"
COMPARE_MODBUS = "modbus"

_DEFAULTS = {
    "tolerance": 0,
    "compare": True,
    "compare_via": COMPARE_MQTT,
    "modbus_table": "holding",
}


def make_case(name, dtype, **fields):
    """Build a case dict with schema defaults applied."""
    case = {"name": name, "dtype": dtype}
    case.update(_DEFAULTS)
    case.update(fields)
    return normalize_case(case)


def make_rc_write_case(name, dtype, value, offset, **fields):
    """RC per-tracker write command."""
    return make_case(
        name,
        dtype,
        value=value,
        offset=offset,
        **fields,
    )


def make_zc_write_case(name, dtype, value, reg_address, **fields):
    """ZC broadcast write command."""
    return make_case(
        name,
        dtype,
        value=value,
        reg_address=reg_address,
        **fields,
    )


def make_zc_read_case(name, dtype, reg_address, length, **fields):
    """ZC input-register read row."""
    defaults = {
        "compare_via": COMPARE_API,
        "modbus_table": "input",
        "length": length,
        "reg_address": reg_address,
    }
    merged = {**defaults, **fields}
    return make_case(name, dtype, **merged)


def make_rc_read_case(name, dtype, offset, **fields):
    """RC field read (compare via API / rover payload)."""
    defaults = {
        "compare_via": COMPARE_API,
        "modbus_table": "input",
        "offset": offset,
    }
    merged = {**defaults, **fields}
    return make_case(name, dtype, **merged)


def normalize_case(case):
    """Normalize legacy keys and dtypes to the standard schema."""
    c = dict(case)

    # Legacy mqtt flag -> compare_via
    if c.pop("mqtt", None) and c.get("compare_via") in (None, COMPARE_MQTT):
        c["compare_via"] = COMPARE_MQTT

    if c.get("api_url") and c.get("compare_via") is None:
        c["compare_via"] = COMPARE_API

    if c.get("compare_via") is None:
        if c.get("reg_address") is not None and "value" in c:
            c["compare_via"] = COMPARE_MQTT
        elif c.get("api_url") or c.get("key") or c.get("key_path"):
            c["compare_via"] = COMPARE_API
        else:
            c["compare_via"] = _DEFAULTS["compare_via"]

    # MQTT key default
    if c.get("compare_via") == COMPARE_MQTT and not c.get("mqtt_key"):
        c["mqtt_key"] = str(c.get("name", "")).upper()

    # Normalize write dtypes for pymodbus
    if c["dtype"] == "int" and c.get("offset") is not None:
        pass  # read counts stay int
    elif c["dtype"] == "int" and "value" in c:
        c["dtype"] = "int16"

    # API URL template
    if c.get("api_url"):
        c["api_url"] = c["api_url"].replace("ZONE_IP", ZONE_IP)

    return c


def should_compare(case):
    return normalize_case(case).get("compare", True) is not False


def compare_via(case):
    return normalize_case(case).get("compare_via", COMPARE_MQTT)


def is_read_case(case):
    """True when case describes a read (no write value required)."""
    c = normalize_case(case)
    return "value" not in c or c.get("kind") == "read"


def case_value(case, default=1):
    return normalize_case(case).get("value", default)


def case_tolerance(case):
    return normalize_case(case).get("tolerance", 0)


def case_modbus_table(case, default="holding"):
    return normalize_case(case).get("modbus_table", default)


def case_mqtt_timeout(case, default=None):
    """MQTT post-write wait (seconds). HRST uses a longer default after reboot."""
    from config.constants import HRST_MQTT_VERIFY_TIMEOUT, MQTT_VERIFY_TIMEOUT

    c = normalize_case(case)
    if c.get("mqtt_timeout") is not None:
        return c["mqtt_timeout"]
    if default is not None:
        base = default
    else:
        base = MQTT_VERIFY_TIMEOUT
    if c.get("name") == "HRST":
        return max(base, HRST_MQTT_VERIFY_TIMEOUT)
    return base


def resolve_api_url(case, zone_ip=None):
    c = normalize_case(case)
    url = c.get("api_url") or ""
    if url:
        return url.replace("ZONE_IP", zone_ip or ZONE_IP)
    return url
