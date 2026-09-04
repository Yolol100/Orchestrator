from __future__ import annotations

import os

from outreach_replyhub import REPLY_HEADERS, REPLY_SHEET
from outreach_reporting import (
    MAILBOX_HEALTH_HEADERS,
    MAILBOX_HEALTH_SHEET,
    VARIANT_ANALYTICS_HEADERS,
    VARIANT_ANALYTICS_SHEET,
)
from outreach_sender import (
    build_sheets_service,
    ensure_expected_headers,
    get_values,
    rows_from_values,
)
from outreach_sequences import (
    SEQUENCE_HEADERS,
    SEQUENCE_SHEET,
    validate_sequence_rows,
)


def check_extended_contract(service, spreadsheet_id: str) -> list[str]:
    checks: list[str] = []
    sequence_headers, sequence_rows = rows_from_values(
        get_values(service, spreadsheet_id, SEQUENCE_SHEET)
    )
    ensure_expected_headers(sequence_headers, SEQUENCE_HEADERS, SEQUENCE_SHEET)
    errors = validate_sequence_rows(sequence_rows)
    if errors:
        raise RuntimeError("sequence contract failed: " + "; ".join(errors[:20]))
    checks.append(f"sheet:{SEQUENCE_SHEET}")

    for sheet_name, expected in (
        (REPLY_SHEET, REPLY_HEADERS),
        (VARIANT_ANALYTICS_SHEET, VARIANT_ANALYTICS_HEADERS),
        (MAILBOX_HEALTH_SHEET, MAILBOX_HEALTH_HEADERS),
    ):
        headers, _ = rows_from_values(get_values(service, spreadsheet_id, sheet_name))
        ensure_expected_headers(headers, expected, sheet_name)
        checks.append(f"sheet:{sheet_name}")
    return checks


def main() -> int:
    spreadsheet_id = os.environ["OUTREACH_SPREADSHEET_ID"]
    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip():
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is required for extended preflight")
    service = build_sheets_service()
    checks = check_extended_contract(service, spreadsheet_id)
    print("EXTENDED_OUTREACH_PREFLIGHT=green checks=" + ",".join(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
