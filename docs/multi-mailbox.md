# Controlled multi-mailbox rotation

This runtime can rotate approved outbound messages across multiple SMTP/IMAP mailboxes while preserving the existing campaign-level limits, compliance/verifier gates and stop-on-reply behavior.

## Why this exists

Instantly can assign multiple sending accounts to a campaign and rotate sends across them. This implementation mirrors the useful transport mechanics without turning the repository into a lead finder or copy generator.

The rotation layer adds:

- multiple configured sending mailboxes;
- a separate daily cap for each mailbox;
- a minimum wait time per mailbox;
- load-aware initial-message rotation;
- sticky mailbox assignment for follow-ups;
- IMAP reply/bounce monitoring across all enabled mailboxes;
- sender identity stored on the queue for audit/readback;
- per-mailbox analytics.

The campaign-wide `OUTREACH_DAILY_LIMIT`, `OUTREACH_MAX_SENDS_PER_RUN`, campaign date/ramp policy, send window, verification gate, suppression and compliance gate still apply. Extra mailboxes never bypass a campaign-level pause, block or cap.

## Backward compatibility

If `OUTREACH_MAILBOXES_JSON` is absent, the existing single-mailbox variables/secrets continue to work. That mailbox gets ID `primary` by default.

Optional single-mailbox variables:

- `OUTREACH_MAILBOX_ID` - defaults to `primary`;
- `OUTREACH_MAILBOX_DAILY_LIMIT` - defaults to the lower of the effective campaign daily limit and 30;
- `OUTREACH_MAILBOX_MIN_WAIT_MINUTES` - defaults to 1.

## Multi-mailbox secret

For more than one mailbox, add one GitHub Actions secret named `OUTREACH_MAILBOXES_JSON`.

Example shape only; never commit real passwords:

```json
[
  {
    "id": "sales-1",
    "enabled": true,
    "smtp_host": "mail.example.com",
    "smtp_port": 587,
    "imap_host": "mail.example.com",
    "imap_port": 993,
    "mail_user": "sales1@example.com",
    "password": "REDACTED",
    "sender_name": "Andrew Baeten",
    "sender_email": "sales1@example.com",
    "daily_limit": 20,
    "min_wait_minutes": 5,
    "dkim_selector": "x",
    "required_spf_token": "include:spf.example.com"
  },
  {
    "id": "sales-2",
    "enabled": true,
    "smtp_host": "mail.example.com",
    "smtp_port": 587,
    "imap_host": "mail.example.com",
    "imap_port": 993,
    "mail_user": "sales2@example.com",
    "password": "REDACTED",
    "sender_name": "Andrew Baeten",
    "sender_email": "sales2@example.com",
    "daily_limit": 20,
    "min_wait_minutes": 5,
    "dkim_selector": "x",
    "required_spf_token": "include:spf.example.com"
  }
]
```

Mailbox IDs, sender addresses and login users must be unique. Live mode requires a password and DKIM selector for every enabled mailbox. SMTP is restricted to 465/587 and guarded IMAP to 993.

## Rotation behavior

For a new lead, the sender chooses only from enabled mailboxes that:

1. are below their individual daily cap;
2. have satisfied their individual minimum wait time;
3. already passed the run-level sender preflight.

Among available mailboxes, the runtime prefers the lowest utilization and then uses deterministic lead/mailbox hashing to avoid a permanent first-mailbox bias.

The chosen mailbox ID and sender address are stored on the queue before the SMTP call. This is deliberate: if the send result becomes ambiguous, the row remains fail-closed with the exact attempted sender recorded.

## Sticky follow-ups

A follow-up must use the same mailbox as the initial message. This matches the threading behavior expected by normal email clients and the default behavior documented by Instantly.

If the assigned mailbox is disabled, removed, at its daily cap, inside its minimum wait window or its sender address changed, the runtime does not silently switch the follow-up to another mailbox. It waits or fails closed for manual reconciliation. This is more conservative than automatic failover because changing the sender can break the original thread and make transport evidence ambiguous.

Legacy rows that were sent before `sender_mailbox_id` existed can follow up automatically only when exactly one enabled mailbox is configured. With multiple enabled mailboxes, a legacy row without a sender assignment requires manual reconciliation.

## Queue and log fields

`OutreachQueue` adds:

- `sender_mailbox_id`
- `sender_email`

`OutreachLog` adds:

- `mailbox_id`
- `sender_email`

These fields are transport/audit state. They do not change the minimal canonical `Leadlijst`.

## Sender preflight

Every enabled mailbox must pass its own configuration, SPF/DKIM/DMARC and, in live mode, SMTP/IMAP authentication checks. Shared DNS checks are reused when multiple mailboxes use the same authenticated domain configuration.

A broken enabled mailbox fails the run instead of being silently skipped. Disable it explicitly after investigating the sender-health issue; do not use rotation as a way to bypass a throttle, provider warning or reputation problem.

## Analytics

The GitHub step summary now includes the SMTP-accepted send mix per `sender_mailbox_id`. These numbers show which account was used; they are not inbox-placement or deliverability proof.
