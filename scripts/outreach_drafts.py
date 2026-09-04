from __future__ import annotations

import imaplib
import os
import re
import ssl
import time
from hashlib import sha256
from types import SimpleNamespace


def _decode_mailbox_name(value: bytes | str) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    match = re.search(r'(?P<name>"(?:[^"\\]|\\.)*"|[^ ]+)$', text.strip())
    if not match:
        return ""
    name = match.group("name")
    if len(name) >= 2 and name[0] == name[-1] == '"':
        name = name[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
    return name


def find_drafts_folder(imap) -> str:
    status, rows = imap.list()
    if status != "OK":
        raise RuntimeError("IMAP LIST failed while locating Drafts folder")
    candidates: list[tuple[int, str]] = []
    for raw in rows or []:
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        name = _decode_mailbox_name(raw)
        if not name:
            continue
        folded = name.casefold()
        flags = text.casefold()
        if "\\drafts" in flags:
            candidates.append((0, name))
        elif folded in {"drafts", "concepten", "draft"}:
            candidates.append((1, name))
        elif folded.endswith(".drafts") or folded.endswith("/drafts"):
            candidates.append((2, name))
    if not candidates:
        raise RuntimeError("No IMAP Drafts folder found")
    candidates.sort(key=lambda item: (item[0], item[1].casefold()))
    return candidates[0][1]


def append_draft(msg, mailbox, imap_factory=imaplib.IMAP4_SSL) -> str:
    if not mailbox.imap_host or not mailbox.mail_user or not mailbox.mail_password:
        raise RuntimeError(f"IMAP settings are incomplete for mailbox {mailbox.mailbox_id}")
    context = ssl.create_default_context()
    with imap_factory(mailbox.imap_host, mailbox.imap_port, ssl_context=context) as imap:
        imap.login(mailbox.mail_user, mailbox.mail_password)
        folder = find_drafts_folder(imap)
        status, data = imap.append(
            folder,
            r"(\Draft)",
            imaplib.Time2Internaldate(time.time()),
            msg.as_bytes(),
        )
        if status != "OK":
            raise RuntimeError(f"IMAP APPEND failed for Drafts folder {folder}: {data!r}")
        return folder


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _draft_fingerprint(msg) -> str:
    return sha256(msg.as_bytes()).hexdigest()


def process() -> int:
    from outreach_campaign_runtime import _candidate_sort_key, _validate_candidate, build_candidates
    from outreach_mailboxes import choose_initial_mailbox, enabled_mailboxes, load_mailboxes_from_env
    from outreach_sender import (
        LOG_HEADERS,
        LOG_SHEET,
        QUEUE_HEADERS,
        QUEUE_SHEET,
        SUPPRESSION_HEADERS,
        SUPPRESSION_SHEET,
        append_row,
        build_message,
        build_sheets_service,
        ensure_expected_headers,
        get_values,
        iso,
        rows_from_values,
        suppression_match,
        suppression_sets,
        update_row,
        utcnow,
    )
    from outreach_sequences import (
        SEQUENCE_HEADERS,
        SEQUENCE_SHEET,
        build_sequence_message,
        group_sequence_rows,
        validate_sequence_rows,
    )

    spreadsheet_id = os.environ["OUTREACH_SPREADSHEET_ID"]
    max_drafts = _int_env("OUTREACH_MAX_DRAFTS_PER_RUN", 20, 1, 100)
    daily_limit = _int_env("OUTREACH_DAILY_LIMIT", 20, 1, 100)
    jitter_max = _int_env("OUTREACH_RANDOM_JITTER_MINUTES", 0, 0, 120)

    mailboxes = load_mailboxes_from_env(mode="drafts", default_daily_limit=daily_limit)
    active_mailboxes = enabled_mailboxes(mailboxes)
    for mailbox in active_mailboxes:
        if not mailbox.imap_host or not mailbox.mail_user or not mailbox.mail_password:
            raise RuntimeError(f"IMAP credentials are incomplete for mailbox {mailbox.mailbox_id}")

    service = build_sheets_service()
    queue_headers, queue_rows = rows_from_values(get_values(service, spreadsheet_id, QUEUE_SHEET))
    suppression_headers, suppression_rows = rows_from_values(get_values(service, spreadsheet_id, SUPPRESSION_SHEET))
    log_headers, log_rows = rows_from_values(get_values(service, spreadsheet_id, LOG_SHEET))
    sequence_headers, sequence_rows = rows_from_values(get_values(service, spreadsheet_id, SEQUENCE_SHEET))
    ensure_expected_headers(queue_headers, QUEUE_HEADERS, QUEUE_SHEET)
    ensure_expected_headers(suppression_headers, SUPPRESSION_HEADERS, SUPPRESSION_SHEET)
    ensure_expected_headers(log_headers, LOG_HEADERS, LOG_SHEET)
    ensure_expected_headers(sequence_headers, SEQUENCE_HEADERS, SEQUENCE_SHEET)

    sequence_errors = validate_sequence_rows(sequence_rows)
    if sequence_errors:
        raise RuntimeError("sequence contract failed: " + "; ".join(sequence_errors[:20]))

    suppressed_emails, suppressed_domains = suppression_sets(suppression_rows)
    sequence_grouped = group_sequence_rows(sequence_rows)
    candidates = build_candidates(queue_rows, sequence_grouped, now=utcnow(), jitter_max_minutes=jitter_max)
    candidates.sort(key=lambda item: _candidate_sort_key(item, True))

    saved_fingerprints = {
        str(row.get("detail", "")).split("sha256=", 1)[1].split()[0]
        for row in log_rows
        if str(row.get("event", "")).strip().lower() == "draft_saved" and "sha256=" in str(row.get("detail", ""))
    }
    settings = SimpleNamespace(spreadsheet_id=spreadsheet_id)
    drafted = 0
    skipped_existing = 0

    for candidate in candidates:
        if drafted >= max_drafts:
            break
        if not candidate.is_initial:
            continue
        row = candidate.queue_row
        errors = _validate_candidate(candidate)
        if suppression_match(row.get("email", ""), suppressed_emails, suppressed_domains):
            errors.append("recipient is suppressed")
        if errors:
            continue

        mailbox = choose_initial_mailbox(
            active_mailboxes,
            sent_today={},
            last_sent_at={},
            now=utcnow(),
            lead_id=str(row.get("lead_id", "")),
        )
        if mailbox is None:
            raise RuntimeError("No enabled mailbox is available for draft assignment")

        if candidate.kind == "sequence":
            assert candidate.sequence_action is not None
            msg = build_sequence_message(row, candidate.sequence_action, mailbox)
        else:
            msg = build_message(row, mailbox, 1)
        fingerprint = _draft_fingerprint(msg)
        if fingerprint in saved_fingerprints:
            skipped_existing += 1
            continue

        folder = append_draft(msg, mailbox)
        row.update(
            sender_mailbox_id=mailbox.mailbox_id,
            sender_email=mailbox.sender_email,
            stage="1",
            last_error="",
        )
        update_row(service, spreadsheet_id, QUEUE_SHEET, candidate.queue_index + 2, queue_headers, row)
        append_row(
            service,
            spreadsheet_id,
            LOG_SHEET,
            LOG_HEADERS,
            {
                "timestamp": iso(utcnow()),
                "lead_id": row.get("lead_id", ""),
                "email": row.get("email", ""),
                "event": "draft_saved",
                "message_id": str(msg["Message-ID"]),
                "detail": f"folder={folder} sha256={fingerprint}",
                "mailbox_id": mailbox.mailbox_id,
                "sender_email": mailbox.sender_email,
            },
        )
        saved_fingerprints.add(fingerprint)
        drafted += 1

    print(f"drafts_saved={drafted} skipped_existing={skipped_existing} candidates={len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(process())
