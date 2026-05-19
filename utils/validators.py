# =========================================================
# NORMALIZER
# =========================================================

def normalize_text(value):

    if value is None:
        return ""

    text = str(value).replace("\x00", "").strip()

    # keep printable ASCII only
    text = "".join(
        ch for ch in text
        if 32 <= ord(ch) <= 126
    )

    return text.strip()


# =========================================================
# STRING COMPARATOR
# =========================================================

def compare_str(modbus_val, backend_val):

    modbus_text = normalize_text(modbus_val)

    backend_text = normalize_text(backend_val)

    # =====================================================
    # EXACT MATCH
    # =====================================================

    if modbus_text == backend_text:
        return True

    # =====================================================
    # PACKED VALUE SUPPORT
    # Example:
    # "v1*v2"
    # =====================================================

    packed_parts = [

        part.strip()

        for part in modbus_text.split("*")

        if part.strip()
    ]

    if backend_text in packed_parts:
        return True

    # =====================================================
    # IGNORE TRAILING NOISE
    # Example:
    # "ZONE1 xyz"
    # compare only first token
    # =====================================================

    split_text = modbus_text.split()

    if split_text:

        return split_text[0] == backend_text

    return False


# =========================================================
# INTEGER COMPARATOR
# =========================================================

def compare_int(modbus_val, backend_val):

    try:

        return int(modbus_val) == int(backend_val)

    except Exception:

        return False


# =========================================================
# INT32 COMPARATOR
# =========================================================

def compare_int32(
    modbus_val,
    backend_val,
    tolerance=0,
):

    try:

        if tolerance == 0:

            return int(modbus_val) == int(backend_val)

        return abs(
            int(modbus_val) - int(backend_val)
        ) <= tolerance

    except Exception:

        return False


# =========================================================
# FLOAT COMPARATOR
# =========================================================

def compare_float(
    modbus_val,
    backend_val,
    tolerance=0.01,
):

    try:

        fa = float(modbus_val)
        fb = float(backend_val)

        if abs(fa - fb) <= tolerance:
            return True

        # Modbus vs REST often use different sentinels for missing / invalid sensors
        missing = (-1.0, -99.0)
        if fa in missing and fb in missing:
            return True

        return False

    except Exception:

        return False


# =========================================================
# BOOLEAN COMPARATOR
# =========================================================

def compare_bool(modbus_val, backend_val):

    return bool(modbus_val) == bool(backend_val)


# =========================================================
# COMPARATOR MAP
# =========================================================

COMPARATORS = {

    "str": compare_str,

    "int": compare_int,

    "int32": compare_int32,

    "float": compare_float,

    "bool": compare_bool,
}


# =========================================================
# GENERIC VALIDATOR
# =========================================================

def validator(
    modbus_val,
    backend_val,
    dtype,
    tolerance=None,
):

    comparator = COMPARATORS.get(dtype)

    if comparator is None:

        print(f"Unsupported dtype: {dtype}")

        return False

    # =====================================================
    # FLOAT / INT32 SUPPORT TOLERANCE
    # =====================================================

    if dtype in ("float", "int32"):

        if tolerance is None:

            tolerance = 0.01 if dtype == "float" else 0

        return comparator(
            modbus_val,
            backend_val,
            tolerance,
        )

    # =====================================================
    # NORMAL TYPES
    # =====================================================

    return comparator(
        modbus_val,
        backend_val,
    )


# =========================================================
# ZC REGISTER COMPARISON (readZC / CLI)
# =========================================================

def compare_float_missing_reading(
    modbus_val,
    backend_val,
    tolerance=0.01,
):
    """Treat common missing-sensor sentinels as equal."""
    try:
        fa = float(modbus_val)
        fb = float(backend_val)
    except (TypeError, ValueError):
        return False

    missing = (-1.0, -99.0)
    if fa in missing and fb in missing:
        return True

    return compare_float(modbus_val, backend_val, tolerance)


def compare_zc_register(case, modbus_val, api_val):
    """Compare one ZC register row (mask / tolerance from case dict)."""
    dtype = case.get("dtype", "str")
    tolerance = case.get("tolerance")

    mask = case.get("compare_mask")
    if mask is not None and dtype == "int":
        try:
            width = int(case.get("compare_int_width", 16))
            all_ones = (1 << width) - 1
            mb = int(modbus_val) & all_ones
            ap = int(api_val) & all_ones
            m = int(mask) & all_ones
            if case.get("compare_mask_ignore"):
                inv = all_ones & ~m
                return (mb & inv) == (ap & inv)
            return (mb & m) == (ap & m)
        except (TypeError, ValueError):
            return False

    if dtype == "float" and case.get("missing_reading_float"):
        if tolerance is None:
            return compare_float_missing_reading(modbus_val, api_val)
        return compare_float_missing_reading(
            modbus_val,
            api_val,
            float(tolerance),
        )

    return validator(modbus_val, api_val, dtype, tolerance=tolerance)


def compare_values(dtype, modbus_val, api_val, tolerance=None):
    """Alias used by readRC for field-level checks."""
    return validator(modbus_val, api_val, dtype, tolerance=tolerance)