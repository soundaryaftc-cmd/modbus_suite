
LINE = "=" * 80
SUB_LINE = "-" * 80


def format_value(value):
    """
    Formats values for clean test output display.
    """
    if value is None:
        return "-"

    if isinstance(value, float):
        return f"{value:.2f}"

    return str(value)


def print_header(title):
    """
    Prints a test suite header.
    """
    print("\n" + LINE)
    print(f"TEST SUITE : {title}")
    print(LINE)


def print_table_header(headers):
    """
    Prints aligned table headers.

    headers format:
    [
        ("Column1", 20),
        ("Column2", 15)
    ]
    """
    row = ""

    for text, width in headers:
        row += f"{text:<{width}}"

    print("\n" + row)
    print(SUB_LINE)


def print_table_row(values):
    """
    Prints aligned table rows.

    values format:
    [
        (value1, 20),
        (value2, 15)
    ]
    """
    row = ""

    for value, width in values:
        row += f"{format_value(value):<{width}}"

    print(row)


def print_failed_cases(failed_cases):
    """
    Prints detailed failed test cases.
    """
    if not failed_cases:
        return

    print("\n" + LINE)
    print("FAILED CASES")
    print(LINE)

    for index, case in enumerate(failed_cases, start=1):

        print(f"\nFailure #{index}")

        for key, value in case.items():
            print(f"{key:<12}: {format_value(value)}")


def print_unresolved_errors(test_name, failed_cases):
    """
    Prints every unresolved error blocking a test (stdout for logs / pytest -s).
    Call this immediately before failing assertions so operators see what to fix.
    """
    if not failed_cases:
        return

    print("\n" + LINE)
    print(f"UNRESOLVED ERRORS — test: {test_name}")
    print("(These failures prevented resolving this testcase.)")
    print(LINE)

    for index, case in enumerate(failed_cases, start=1):

        print(f"\n  Error #{index}")

        err = case.get("error")
        if err is not None:
            print(f"  {'error':<12}: {err}")

        for key, value in case.items():
            if key == "error":
                continue
            print(f"  {key:<12}: {format_value(value)}")

    print("\n" + LINE)


def print_summary(total, passed, failed, skipped=0):
    """
    Prints final test summary.
    """
    print("\n" + LINE)
    print("FINAL SUMMARY")
    print(LINE)

    print(f"TOTAL   : {total}")
    print(f"PASS    : {passed}")
    print(f"FAIL    : {failed}")

    if skipped:
        print(f"SKIP    : {skipped}")

    print(LINE)