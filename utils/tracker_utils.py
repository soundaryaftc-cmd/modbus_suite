import re

from config.rc_registers import (
    CFLT_OFFSET,
    HMNM_OFFSET,
    HRST_OFFSET,
    MODE_OFFSET,
    PITCH_OFFSET,
    STOP_OFFSET,
    TRACKER_OFFSETS,
)

_RC_COMMAND_OFFSETS = {
    "MODE": MODE_OFFSET,
    "RTC": MODE_OFFSET,
    "Refresh": MODE_OFFSET,
    "STOP": STOP_OFFSET,
    "CFLT": CFLT_OFFSET,
    "PITCH": PITCH_OFFSET,
    "HMNM": HMNM_OFFSET,
    "SC": HMNM_OFFSET,
    "HRST": HRST_OFFSET,
}

MODBUS_MAX_REGISTER = 65535


def get_tracker_number(tracker_name):

    name = str(tracker_name).strip()

    # B331001021, FTCR1163, etc.: row = last 3 digits of numeric suffix.
    match_row = re.match(r"^[A-Za-z]+\d*(\d{3})$", name, re.IGNORECASE)
    if match_row:
        return int(match_row.group(1))

    match = re.search(r"(\d+)$", name)

    if not match:
        raise ValueError(f"Invalid tracker name: {tracker_name}")

    return int(match.group(1))


def get_base_register(tracker_name):

    tracker_no = get_tracker_number(tracker_name)

    if tracker_no < 100:
        return (tracker_no * 100) - 1

    return ((tracker_no - 99) * 100) + 49


def max_rc_register_for_tracker(tracker_name):
    base = get_base_register(tracker_name)
    max_offset = max(
        max(TRACKER_OFFSETS.values(), default=0),
        max(_RC_COMMAND_OFFSETS.values()),
    )
    return base + max_offset


def tracker_modbus_addresses_valid(tracker_name):
    try:
        return max_rc_register_for_tracker(tracker_name) <= MODBUS_MAX_REGISTER
    except ValueError:
        return False


def calculate_register(tracker_name, field_name):

    base_register = get_base_register(tracker_name)

    offset = TRACKER_OFFSETS[field_name]

    return base_register + offset


def get_rc_command_register(tracker_name, command_name):

    offset = _RC_COMMAND_OFFSETS[command_name]

    return get_base_register(tracker_name) + offset
