from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from outreach_sender import (
    QUEUE_HEADERS,
    QUEUE_SHEET,
    SUPPRESSION_HEADERS,
    SUPPRESSION_SHEET,
    build_sheets_service,
    ensure_expected_headers,
    get_values,
    iso,
    log_event,
    normalize_address,
    rows_from_values,
    suppression_match,
    suppression_sets,
    update_row,
    utcnow,
    validate_row,
    verification_decision,
    verification_is_fresh,
    reoon_verify,
)

BULK_CREATE_URL = "https://emailverifier.reoon.com/api/v1/create-bulk-verification-task/"
BULK_RESULT_URL = "https://emailverifier.reoon.com/api/v1/get-result-bulk-verification-task/"
VERIFIABLE_STATUSES = {"approved", "verification_pending"}
TERMINAL_BULK_STATUSES = {"file_not_found", "file_loading_error", "error"}


def max_verifications_from_env() -> int:
    value = int(os.getenv("OUTREACH_MAX_VERIFICATIONS_PER_RUN", "50"))
    if value < 1 or value > 500:
        raise ValueError("OUTREACH_MAX_VERIFICATIONS_PER_RUN must be between 1 and 500")
    return value


def normalize_bulk_results(payload: dict) -> dict[str, dict]:
    raw = payload.get("results", {})
    normalized: dict[str, dict] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict):
                address = normalize_address(value.get("email", "")) or normalize_address(str(key))
                if address:
                    normalized[address] = value
    elif isinstance(raw, list):
        for value in raw:
            if isinstance(value, dict):
                address = normalize_address(value.get("email", ""))
                if address:
                    normalized[address] = value
    return normalized


def reoon_verify_bulk(
    addresses: Iterable[str],
    api_key: str,
    opener: Callable = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    max_polls: int = 60,
    poll_seconds: float = 5.0,
) -> dict[str, dict]:
    emails = list(dict.fromkeys(normalize_address(address) for address in addresses if normalize_address(address)))
    if len(emails) < 10:
        raise ValueError("Reoon bulk endpoint requires at least 10 emails; use single Power verification below 10")
    if len(emails) > 50000:
        raise ValueError("Reoon bulk endpoint accepts at most 50,000 emails")
    if not api_key:
        raise RuntimeError("REOON_API_KEY is required in verify/live mode")

    task_name = "webactueel-" + datetime.utcnow().strftime("%Y%m%d%H%M")
    body = json.dumps({"name": task_name, "emails": emails, "key": api_key}).encode("utf-8")
    request = Request(
        BULK_CREATE_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with opener(request, timeout=90) as response:
        created = json.loads(response.read().decode("utf-8"))
    if not isinstance(created, dict) or created.get("status") != "success" or not created.get("task_id"):
        raise RuntimeError(f"Reoon bulk task creation failed: {created!r}")

    query = urlencode({"key": api_key, "task_id": created["task_id"]})
    result_url = BULK_RESULT_URL + "?" + query
    for _ in range(max_polls):
        with opener(result_url, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("unexpected Reoon bulk result response")
        status = str(payload.get("status", "")).strip().lower()
        if status == "completed":
            return normalize_bulk_results(payload)
        if status in TERMINAL_BULK_STATUSES:
            raise RuntimeError(f"Reoon bulk verification failed: {payload!r}")
        sleeper(poll_seconds)
    raise TimeoutError("Reoon bulk verification did not complete within the polling window")


def candidate_indexes(rows: list[dict[str, str]], now, max_age_days: int) -> list[int]:
    indexes: list[int] = []
    for idx, row in enumerate(rows):
        if row.get("status", "").strip().lower() not in VERIFIABLE_STATUSES:
            continue
        if verification_is_fresh(row, now, max_age_days):
            continue
        indexes.append(idx)
    return indexes


def apply_result(service, settings, headers: list[str], row_number: int, row: dict[str, str], result: dict, detail: str) -> None:
    decision = verification_decision(result)
    row.update(
        verification_status=decision,
        verification_checked_at=iso(utcnow()),
        last_error="" if decision == "safe" else f"verifier status={result.get('status', '')}"[:500],
    )
    row["status"] = "approved" if decision == "safe" else decision
    update_row(service, settings.spreadsheet_id, QUEUE_SHEET, row_number, headers, row)
    log_event(
        service,
        settings,
        row,
        "verified_safe" if decision == "safe" else decision,
        detail=detail if decision == "safe" else row["last_error"],
    )


def process() -> int:
    from outreach_sender import Settings

    settings = Settings.from_env()
    service = build_sheets_service()
    headers, rows = rows_from_values(get_values(service, settings.spreadsheet_id, QUEUE_SHEET))
    ensure_expected_headers(headers, QUEUE_HEADERS, QUEUE_SHEET)
    suppression_headers, suppression_rows = rows_from_values(get_values(service, settings.spreadsheet_id, SUPPRESSION_SHEET))
    ensure_expected_headers(suppression_headers, SUPPRESSION_HEADERS, SUPPRESSION_SHEET)
    suppressed_emails, suppressed_domains = suppression_sets(suppression_rows)
    now = utcnow()

    indexes = candidate_indexes(rows, now, settings.verification_max_age_days)
    if settings.mode == "validate":
        print(f"mode=validate verification_candidates={len(indexes)}; verifier not called")
        return 0

    max_per_run = max_verifications_from_env()
    selected = indexes[:max_per_run]
    deferred = indexes[max_per_run:]

    for idx in deferred:
        row = rows[idx]
        if row.get("status", "").strip().lower() != "verification_pending":
            row.update(status="verification_pending", last_error="verification deferred to a later run")
            update_row(service, settings.spreadsheet_id, QUEUE_SHEET, idx + 2, headers, row)

    eligible: list[int] = []
    for idx in selected:
        row = rows[idx]
        errors = validate_row(row, "initial")
        if suppression_match(row.get("email", ""), suppressed_emails, suppressed_domains):
            errors.append("recipient is suppressed")
        if errors:
            row.update(status="blocked", last_error="; ".join(errors)[:500])
            update_row(service, settings.spreadsheet_id, QUEUE_SHEET, idx + 2, headers, row)
            log_event(service, settings, row, "blocked", detail=row["last_error"])
            continue
        eligible.append(idx)

    if not eligible:
        print(f"mode={settings.mode} verification_candidates=0 deferred={len(deferred)}")
        return 0

    addresses = [rows[idx]["email"] for idx in eligible]
    if len(addresses) >= 10:
        results = reoon_verify_bulk(addresses, settings.reoon_api_key)
        for idx in eligible:
            row = rows[idx]
            address = normalize_address(row["email"])
            result = results.get(address)
            if not result:
                row.update(status="manual_review", verification_status="manual_review", verification_checked_at=iso(utcnow()), last_error="Reoon bulk result missing")
                update_row(service, settings.spreadsheet_id, QUEUE_SHEET, idx + 2, headers, row)
                log_event(service, settings, row, "manual_review", detail=row["last_error"])
                continue
            apply_result(service, settings, headers, idx + 2, row, result, "Reoon bulk Power mode")
        verifier_mode = "bulk"
    else:
        for idx in eligible:
            row = rows[idx]
            result = reoon_verify(row["email"], settings.reoon_api_key)
            apply_result(service, settings, headers, idx + 2, row, result, "Reoon single Power mode")
        verifier_mode = "single"

    print(
        f"mode={settings.mode} verified={len(eligible)} verifier_mode={verifier_mode} "
        f"deferred={len(deferred)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(process())
