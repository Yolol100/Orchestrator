from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from outreach_sender import (
    QUEUE_SHEET,
    SUPPRESSION_SHEET,
    build_sheets_service,
    get_values,
    next_action,
    parse_dt,
    rows_from_values,
)


def _percent(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else round((numerator / denominator) * 100, 2)


def build_metrics(rows: Iterable[dict[str, str]], now: datetime, timezone_name: str) -> dict[str, object]:
    rows = list(rows)
    tz = ZoneInfo(timezone_name)
    today = now.astimezone(tz).date()
    status_counts = Counter((row.get("status", "") or "blank").strip().lower() or "blank" for row in rows)

    initial_sent_total = sum(1 for row in rows if parse_dt(row.get("sent_at", "")))
    followup_sent_total = sum(1 for row in rows if parse_dt(row.get("followup_sent_at", "")))
    initial_sent_today = sum(
        1
        for row in rows
        if (dt := parse_dt(row.get("sent_at", ""))) and dt.astimezone(tz).date() == today
    )
    followup_sent_today = sum(
        1
        for row in rows
        if (dt := parse_dt(row.get("followup_sent_at", ""))) and dt.astimezone(tz).date() == today
    )

    replied = status_counts.get("replied", 0)
    bounced = status_counts.get("bounced", 0)
    opted_out = status_counts.get("opted_out", 0)
    contacted = initial_sent_total

    ready_initial = 0
    due_followup = 0
    for row in rows:
        action = next_action(row, now)
        if action == "initial":
            ready_initial += 1
        elif action == "followup":
            due_followup += 1

    verification_counts = Counter(
        (row.get("verification_status", "") or "blank").strip().lower() or "blank" for row in rows
    )

    return {
        "total_rows": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "verification_counts": dict(sorted(verification_counts.items())),
        "initial_sent_total": initial_sent_total,
        "followup_sent_total": followup_sent_total,
        "initial_sent_today": initial_sent_today,
        "followup_sent_today": followup_sent_today,
        "ready_initial": ready_initial,
        "due_followup": due_followup,
        "reply_rate": _percent(replied, contacted),
        "bounce_rate": _percent(bounced, contacted),
        "opt_out_rate": _percent(opted_out, contacted),
        "replied": replied,
        "bounced": bounced,
        "opted_out": opted_out,
    }


def render_markdown(
    metrics: dict[str, object],
    *,
    suppression_count: int,
    policy_reason: str = "",
    effective_mode: str = "",
    effective_daily_limit: str = "",
    effective_max_sends_per_run: str = "",
) -> str:
    status_counts = metrics["status_counts"]
    verification_counts = metrics["verification_counts"]
    status_text = ", ".join(f"{key}={value}" for key, value in status_counts.items()) or "none"
    verification_text = ", ".join(f"{key}={value}" for key, value in verification_counts.items()) or "none"

    lines = [
        "## Controlled outreach analytics",
        "",
        f"- queue rows: **{metrics['total_rows']}**",
        f"- SMTP-accepted initial messages: **{metrics['initial_sent_total']}** total / **{metrics['initial_sent_today']}** today",
        f"- SMTP-accepted follow-ups: **{metrics['followup_sent_total']}** total / **{metrics['followup_sent_today']}** today",
        f"- ready initial rows: **{metrics['ready_initial']}**",
        f"- due follow-ups: **{metrics['due_followup']}**",
        f"- replies: **{metrics['replied']}** ({metrics['reply_rate']}% of contacted leads)",
        f"- bounces: **{metrics['bounced']}** ({metrics['bounce_rate']}% of contacted leads)",
        f"- opt-outs: **{metrics['opted_out']}** ({metrics['opt_out_rate']}% of contacted leads)",
        f"- suppression rows: **{suppression_count}**",
        f"- status mix: `{status_text}`",
        f"- verification mix: `{verification_text}`",
    ]
    if policy_reason:
        lines.extend(
            [
                "",
                "### Campaign policy",
                "",
                f"- reason: `{policy_reason}`",
                f"- effective mode: `{effective_mode or 'unknown'}`",
                f"- effective daily limit: `{effective_daily_limit or 'unknown'}`",
                f"- effective max sends/run: `{effective_max_sends_per_run or 'unknown'}`",
            ]
        )
    lines.extend(
        [
            "",
            "> SMTP acceptance is transport readback, not proof of inbox placement or positive commercial outcome.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    spreadsheet_id = os.environ["OUTREACH_SPREADSHEET_ID"]
    timezone_name = os.getenv("OUTREACH_TIMEZONE", "Europe/Amsterdam").strip() or "Europe/Amsterdam"
    service = build_sheets_service()
    _, rows = rows_from_values(get_values(service, spreadsheet_id, QUEUE_SHEET))
    _, suppression_rows = rows_from_values(get_values(service, spreadsheet_id, SUPPRESSION_SHEET))
    metrics = build_metrics(rows, datetime.now(timezone.utc), timezone_name)
    report = render_markdown(
        metrics,
        suppression_count=len(suppression_rows),
        policy_reason=os.getenv("OUTREACH_POLICY_REASON", ""),
        effective_mode=os.getenv("OUTREACH_EFFECTIVE_MODE", ""),
        effective_daily_limit=os.getenv("OUTREACH_EFFECTIVE_DAILY_LIMIT", ""),
        effective_max_sends_per_run=os.getenv("OUTREACH_EFFECTIVE_MAX_SENDS_PER_RUN", ""),
    )
    print(report)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
