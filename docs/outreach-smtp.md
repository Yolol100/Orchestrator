# Controlled SMTP outreach runtime

This runtime is transport only. It does not decide lead fit, invent contact data, write campaign copy, or authorize outreach. Leads/ChatGPT prepares an explicitly approved queue in the Webactueel Leadlijst spreadsheet. The workflow verifies the address, sends bounded mail through the configured SMTP account, checks IMAP for replies and bounces, and writes provider readback back to the queue/log tabs.

## Safety model

- Nothing runs unless repository variable `OUTREACH_ENABLED` is exactly `true`.
- Start with `OUTREACH_MODE=validate`, then `verify`, and only use `live` after sender preflight and a reviewed test cohort.
- `OUTREACH_DAILY_LIMIT` defaults to 20 in code and is hard capped at 100.
- `OUTREACH_MAX_SENDS_PER_RUN` defaults to 2 and is hard capped at 10.
- `OUTREACH_MAX_VERIFICATIONS_PER_RUN` defaults to 50 and is hard capped at 500, so verification spend is bounded per run.
- Reoon routing follows its documented API split: fewer than 10 pending addresses use the single Power endpoint; 10 or more use one Bulk Verification task, whose results are polled until completed. Deferred rows are marked `verification_pending` and cannot enter the sender until a later verification run.
- The sender step itself does not receive `REOON_API_KEY`; verification is isolated in the preprocessor. A late/unverified approved row therefore fails closed rather than silently bypassing the verifier routing.
- Only rows with `status=approved`, `compliance_status=approved`, a fresh Reoon `safe` result, and `opt_out_mode=reply_optout` may enter direct SMTP sending.
- `provider_required` is intentionally blocked in this direct SMTP runtime. If one-click/header unsubscribe is required, use a provider that implements that mechanism.
- `catch_all`, `unknown`, `role_account`, and `inbox_full` go to manual review. `invalid`, `disabled`, `disposable`, and `spamtrap` are blocked.
- Any real reply stops further sends. Strong opt-out language moves the address to the suppression list. Delivery-status bounces also suppress the address.
- A row is marked `sending` before the SMTP call. A crash or ambiguous exception therefore fails closed rather than silently retrying and risking a duplicate message.
- Secrets are never stored in repository files, queue rows, logs, or artifacts.

## Spreadsheet tabs

The existing minimal `Leadlijst` and `Mailtests` tabs remain unchanged. The transport uses three separate tabs:

- `OutreachQueue`: prepared message, compliance/verifier status, delivery state, timestamps, message IDs, and one follow-up.
- `Suppression`: email/domain suppression with reason and evidence.
- `OutreachLog`: append-only operational events.

The queue is not the source of lead-policy truth. Leads remains owner of evidence, fit, personalization and compliance decisions.

## Required GitHub Actions secrets

Create these repository Actions secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: service-account JSON with access to the target Google Sheet. Share the Sheet with that service-account email.
- `REOON_API_KEY`: Reoon Email Verifier API key.
- `OUTREACH_MAIL_PASSWORD`: password for the SMTP/IMAP mailbox.

Never put these values in repository variables or committed files.

## Required repository variables

Recommended initial values:

- `OUTREACH_ENABLED=false`
- `OUTREACH_MODE=validate`
- `OUTREACH_SPREADSHEET_ID=1p4vZnCdcex9zpTAV-ssebXqZcBS2TU6KfXwS-4d2iSI`
- `OUTREACH_TIMEZONE=Europe/Amsterdam`
- `OUTREACH_SEND_WINDOW_START=08:00`
- `OUTREACH_SEND_WINDOW_END=18:00`
- `OUTREACH_DAILY_LIMIT=20`
- `OUTREACH_MAX_SENDS_PER_RUN=2`
- `OUTREACH_MAX_VERIFICATIONS_PER_RUN=50`
- `OUTREACH_VERIFICATION_MAX_AGE_DAYS=30`
- `OUTREACH_SMTP_HOST=mail.andrewbaeten.nl`
- `OUTREACH_SMTP_PORT=587`
- `OUTREACH_IMAP_HOST=mail.andrewbaeten.nl`
- `OUTREACH_IMAP_PORT=993`
- `OUTREACH_MAIL_USER=info@andrewbaeten.nl`
- `OUTREACH_SENDER_NAME=Andrew Baeten`
- `OUTREACH_SENDER_EMAIL=info@andrewbaeten.nl`

Confirm the exact mail host in the mailbox configuration before live mode. The current mijn.host documentation describes `mail.<domain>` as the normal server pattern, IMAP 993 with SSL, and SMTP 587 with TLS (465 as the SSL/TLS alternative).

## Activation sequence

1. Keep `OUTREACH_ENABLED=false` while configuring secrets and sharing the Sheet with the service account.
2. Set `OUTREACH_ENABLED=true` and `OUTREACH_MODE=validate`. Run manually. This checks queue gates but does not call the verifier or send mail.
3. Set `OUTREACH_MODE=verify`. Run manually on a small reviewed queue. This calls Reoon Power verification through the documented single/bulk route but does not send mail.
4. Review verification statuses, suppression behavior, SPF/DKIM/DMARC, mailbox/provider status, compliance and message content.
5. Set `OUTREACH_MODE=live` with the small default limits. Run manually before relying on the schedule.
6. Verify the received message headers, provider readback, reply stop, bounce handling and suppression behavior.
7. Scale only after healthy delivery/bounce/complaint/opt-out/reply evidence. Do not use the provider's technical maximum as the operating target and never use extra accounts/domains to bypass provider enforcement.

## Workflow schedule

The GitHub Actions schedule checks the queue every 15 minutes on weekdays at minute 7/22/37/52 during a broad UTC window. The offset avoids the highest-load start-of-hour pattern called out by GitHub. The Python runtime independently enforces the configured `Europe/Amsterdam` send window, so a delayed or timezone-shifted scheduled run cannot send outside that local window.

GitHub scheduled workflows execute only from the default branch. The schedule therefore becomes eligible only after this workflow is merged to the default branch, and the `OUTREACH_ENABLED` gate still prevents execution until explicitly enabled.
