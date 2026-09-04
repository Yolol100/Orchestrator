# Controlled SMTP outreach runtime

This runtime is transport only. It does not decide lead fit, invent contact data, write campaign copy or authorize outreach. Leads/ChatGPT prepares approved queue and optional sequence rows in the Webactueel Leadlijst spreadsheet. GitHub Actions resolves campaign policy, runs fail-closed preflights, verifies first-contact addresses, processes bounded SMTP/IMAP transport and writes auditable readback.

## Runtime order

`.github/workflows/outreach-smtp.yml` executes:

1. campaign pacing policy;
2. sender/mailbox/DNS preflight;
3. extended Sheet/sequence contract preflight;
4. Reoon verification preprocessor;
5. `scripts/outreach_campaign_runtime.py` for reply sync and bounded sending;
6. non-blocking `scripts/outreach_reporting.py` for derived analytics.

Nothing runs unless `OUTREACH_ENABLED` is exactly `true`.

## Safety model

- Start with `OUTREACH_MODE=validate`, then `verify`, then only a small reviewed `live` pilot.
- `OUTREACH_DAILY_LIMIT` defaults to 20 and is hard capped at 100.
- `OUTREACH_MAX_SENDS_PER_RUN` defaults to 2 and is hard capped at 10.
- Campaign start/end dates, slow ramp and natural pacing can only reduce or block live behavior.
- Every mailbox can have a smaller `daily_limit` and `min_wait_minutes`; mailbox limits never raise campaign limits.
- First contact requires approved compliance, `reply_optout`, fresh Reoon `safe`, no suppression and all policy/mailbox gates green.
- The sender does not receive `REOON_API_KEY`.
- `provider_required` is blocked in direct SMTP; use a provider that implements the required unsubscribe mechanism when applicable.
- `catch_all`, `unknown`, `role_account` and `inbox_full` remain manual review. Invalid/disabled/disposable/spamtrap remain blocked.
- Replies, opt-outs and bounces stop later sends. Opt-outs and bounces enter suppression.
- A row is marked `sending` before SMTP. Ambiguous failures remain fail-closed rather than automatically retrying.
- Follow-up steps stay on the mailbox assigned to the initial message.
- Secrets are never stored in repository files, Sheet rows, logs or artifacts.

## Spreadsheet contracts

`Leadlijst` remains the minimal lead lifecycle/dedupe view and `Mailtests` remains separate. Transport state uses:

### OutreachQueue

Existing queue with sender attribution:

`lead_id | company | website | email | first_name | subject | body | followup_subject | followup_body | followup_delay_days | country | compliance_status | opt_out_mode | status | verification_status | verification_checked_at | stage | next_send_at | sent_at | followup_sent_at | message_id | followup_message_id | reply_at | bounce_at | last_error | source | sender_mailbox_id | sender_email`

Legacy compatibility remains: when a lead has no `OutreachSequences` rows, `subject/body` plus one optional `followup_*` message continue to work.

### OutreachSequences

Optional provider-neutral multi-step contract:

`lead_id | sequence_id | sequence_version | step_number | variant_id | enabled | subject | body | wait_minutes | status | selected | scheduled_at | sent_at | message_id | sender_mailbox_id | sender_email | last_error | source`

When enabled rows exist for a lead, they become that lead's send source and legacy follow-up fields are not used for extra sends. This prevents double sending.

The contract supports up to 50 contiguous steps and A-Z variants per step. All variants in a step share the same wait. Step 1 requires a subject and `wait_minutes=0`; later blank subjects inherit the previous subject. Variant choice is deterministic and persisted before SMTP.

### ReplyInbox

Unified IMAP readback dataset:

`reply_id | received_at | lead_id | company | email | mailbox_id | mailbox_email | subject | preview | classification | triage_status | owner_label | notes | message_id | in_reply_to | source`

Known lead replies, opt-outs and bounces are deduplicated and immediately reconcile the transport stop state. `owner_label` and `notes` are operator/controller fields; the runtime does not invent positive/negative/customer outcomes.

### Suppression

`email | domain | reason | source | created_at | evidence`

### OutreachLog

`timestamp | lead_id | email | event | message_id | detail | mailbox_id | sender_email`

### VariantAnalytics

Derived report:

`generated_at | sequence_id | sequence_version | step_number | variant_id | sends | replies_attributed | bounces_attributed | opt_outs_attributed | reply_rate | bounce_rate | opt_out_rate | recommendation | note`

Recommendations are advisory owner-review signals only. The runtime never rewrites or disables approved copy automatically.

### MailboxHealth

Derived 30-day transport report:

`generated_at | mailbox_id | sender_email | sends_30d | replies_30d | bounces_30d | opt_outs_30d | reply_rate | bounce_rate | opt_out_rate | state | note`

This is not a warmup score, reputation score or inbox-placement measurement.

## Required Actions secrets

Single-mailbox route:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `REOON_API_KEY`
- `OUTREACH_MAIL_PASSWORD`

Multi-mailbox route adds:

- `OUTREACH_MAILBOXES_JSON`

`OUTREACH_MAILBOXES_JSON` is available only to sender preflight and the campaign runtime. It is not passed to verifier or reporting.

See `docs/multi-mailbox.md` for the mailbox JSON shape.

## Core repository variables

Recommended baseline:

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
- `OUTREACH_MAILBOX_ID=primary`
- `OUTREACH_MAILBOX_DAILY_LIMIT=20`
- `OUTREACH_MAILBOX_MIN_WAIT_MINUTES=1`
- `OUTREACH_SMTP_HOST=mail.andrewbaeten.nl`
- `OUTREACH_SMTP_PORT=587`
- `OUTREACH_IMAP_HOST=mail.andrewbaeten.nl`
- `OUTREACH_IMAP_PORT=993`
- `OUTREACH_MAIL_USER=info@andrewbaeten.nl`
- `OUTREACH_SENDER_NAME=Andrew Baeten`
- `OUTREACH_SENDER_EMAIL=info@andrewbaeten.nl`
- `OUTREACH_DKIM_SELECTOR=x`
- `OUTREACH_REQUIRED_SPF_TOKEN=include:spf.mijn.host`

Confirm actual mail host and DKIM selector in DirectAdmin/DNS before live mode.

## Campaign and sequence controls

Existing optional controls:

- `OUTREACH_NATURAL_PACING=false`
- `OUTREACH_CAMPAIGN_START_DATE=`
- `OUTREACH_CAMPAIGN_END_DATE=`
- `OUTREACH_SLOW_RAMP_ENABLED=false`
- `OUTREACH_RAMP_START_DATE=`
- `OUTREACH_RAMP_START_LIMIT=2`
- `OUTREACH_RAMP_INCREMENT_PER_DAY=2`

New optional controls:

- `OUTREACH_MAX_NEW_LEADS_PER_DAY=100`
  - Additional cap on step-1 sends. The campaign-wide daily limit still wins.
- `OUTREACH_PRIORITIZE_NEW_LEADS=false`
  - `false` gives due follow-ups priority before starting more sequences.
- `OUTREACH_RANDOM_JITTER_MINUTES=0`
  - Stable extra step delay, runtime-bounded to 0-120 minutes.
- `OUTREACH_REPLY_LOOKBACK_DAYS=14`
  - IMAP lookback, runtime-bounded to 1-90 days.
- `OUTREACH_CAPTURE_OTHER_MAIL=false`
  - Optional capture of non-lead mailbox messages into `ReplyInbox`; keep false for mixed/private mailboxes.
- `OUTREACH_VARIANT_MIN_SAMPLES=20`
  - Minimum sends before comparative variant recommendations.
- `OUTREACH_MAILBOX_BOUNCE_ALERT_RATE=5`
  - Descriptive 30-day bounce-rate alert threshold.

## Threading

For sequence follow-ups, the runtime stores each successful `Message-ID`, writes the prior message ID into `In-Reply-To`, builds `References`, inherits the prior subject when the new subject is blank and uses the original `sender_mailbox_id`.

If the assigned mailbox is disabled, removed, identity-changed or temporarily out of capacity, the existing thread is deferred/fails closed rather than silently switching sender.

## Preflight guarantees

The combined preflight checks:

1. runtime/mailbox configuration is structurally valid;
2. SPF and expected provider token when configured;
3. DMARC;
4. DKIM selector/public key;
5. core queue/suppression/log Sheet contracts;
6. `OutreachSequences`, `ReplyInbox`, `VariantAnalytics`, `MailboxHealth` contracts;
7. sequence-row consistency;
8. in live mode, SMTP and IMAP authentication for every enabled mailbox.

It does not prove inbox placement or real received-message authentication alignment. Those still require controlled recipient tests and received-header inspection.

## Reporting

`scripts/outreach_reporting.py` is `if: always()` and non-blocking. It reads transport state and refreshes only `VariantAnalytics` and `MailboxHealth`, then writes a compact GitHub summary.

SMTP success is described as SMTP-accepted, never as proven delivered/inbox placed.

## Activation sequence

1. Keep `OUTREACH_ENABLED=false` while configuring Sheet access, secrets, variables and sender DNS.
2. Confirm SMTP/IMAP hosts and DKIM selectors.
3. If using sequences, have Leads/ChatGPT write only reviewed/approved `OutreachSequences` rows. Leaving the tab empty preserves legacy behavior.
4. Run `validate`; both preflights must pass and no mail is sent.
5. Run `verify` on a small reviewed first-contact set; no mail is sent.
6. Review verifier results, sequence rows, variants, waits, suppression and mailbox pool.
7. Switch to `live` with small campaign/per-mailbox limits and run manually.
8. Verify real received headers, reply stop, opt-out, bounce suppression, sequence threading, mailbox rotation and `ReplyInbox` readback.
9. Scale only on healthy evidence; never use extra accounts to bypass provider/reputation enforcement.

## Deliberate non-features

The runtime does not fake warmup networks, spam-folder placement, open/click tracking, custom tracking domains, AI sentiment, lead finding, automatic disconnected-account takeover or automatic reply-triggered subsequences. See `docs/instantly-parity.md` and `docs/sequences-variants-replyhub.md`.

## Tests and schedule

CI compiles Python and runs regression/security tests covering verifier behavior, mailbox rotation, preflight, campaign policy, multi-step timing, variant persistence, threading, daily/per-mailbox accounting, reply/report attribution and secret scoping. Remote Actions remain pinned to full commit SHAs and workflows declare explicit least-privilege permissions.

The scheduled workflow checks the queue every 15 minutes on weekdays at minute 7/22/37/52 during a broad UTC window. Python independently enforces the configured local send window. GitHub scheduled workflows run from the default branch only, and `OUTREACH_ENABLED` remains the explicit execution gate.
