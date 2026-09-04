# Controlled SMTP outreach runtime

This runtime is transport only. It does not decide lead fit, invent contact data, write campaign copy, or authorize outreach. Leads/ChatGPT prepares an explicitly approved queue in the Webactueel Leadlijst spreadsheet. The workflow resolves campaign pacing policy, runs a non-sending sender preflight, verifies pending addresses, sends bounded mail through the configured SMTP account, checks IMAP for replies and bounces, and writes provider readback back to the queue/log tabs. A read-only analytics step then summarizes the transport state in the GitHub run summary.

## Safety model

- Nothing runs unless repository variable `OUTREACH_ENABLED` is exactly `true`.
- Start with `OUTREACH_MODE=validate`, then `verify`, and only use `live` after sender preflight and a reviewed test cohort.
- `scripts/outreach_campaign_policy.py` derives an effective mode and effective send limits before verifier/sender execution. Campaign start/end dates and slow-ramp state can only reduce or block live sending; they never increase the configured hard limits.
- `scripts/outreach_preflight.py` fails closed before verifier/sender execution when configuration, DNS authentication or Sheet contracts are invalid. In effective `live` mode it also authenticates to SMTP and IMAP without sending a message.
- The live preflight requires SPF, DMARC and a configured DKIM selector. `OUTREACH_REQUIRED_SPF_TOKEN` can bind the SPF check to the expected sending provider; for mijn.host the documented token is `include:spf.mijn.host`.
- The preflight validates the three transport tabs (`OutreachQueue`, `Suppression`, `OutreachLog`) using the configured Google service account before any verifier or sender write.
- `OUTREACH_DAILY_LIMIT` defaults to 20 in code and is hard capped at 100.
- `OUTREACH_MAX_SENDS_PER_RUN` defaults to 2 and is hard capped at 10. Optional natural pacing can reduce the effective per-run limit to 1; it never raises it.
- `OUTREACH_MAX_VERIFICATIONS_PER_RUN` defaults to 50 and is hard capped at 500, so verification spend is bounded per run.
- Reoon routing follows its documented API split: fewer than 10 pending addresses use the single Power endpoint; 10 or more use one Bulk Verification task, whose results are polled until completed. Deferred rows are marked `verification_pending` and cannot enter the sender until a later verification run.
- The sender step itself does not receive `REOON_API_KEY`; verification is isolated in the preprocessor. A late/unverified approved row therefore fails closed rather than silently bypassing verifier routing.
- Only rows with `status=approved`, `compliance_status=approved`, a fresh Reoon `safe` result, and `opt_out_mode=reply_optout` may enter direct SMTP sending.
- `provider_required` is intentionally blocked in this direct SMTP runtime. If one-click/header unsubscribe is required, use a provider that implements that mechanism.
- `catch_all`, `unknown`, `role_account`, and `inbox_full` go to manual review. `invalid`, `disabled`, `disposable`, and `spamtrap` are blocked.
- Any real reply stops further sends. Explicit opt-out language and a direct short reply such as `nee` move the address to the suppression list. Delivery-status bounces also suppress the address.
- A row is marked `sending` before the SMTP call. A crash or ambiguous exception therefore fails closed rather than silently retrying and risking a duplicate message.
- Secrets are never stored in repository files, queue rows, logs or artifacts.

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

Recommended initial values for the current Andrew Baeten/mijn.host route:

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
- `OUTREACH_DKIM_SELECTOR=x`
- `OUTREACH_REQUIRED_SPF_TOKEN=include:spf.mijn.host`

Confirm the exact mail host and DKIM selector in DirectAdmin before live mode. Current mijn.host documentation describes `mail.<domain>` as the normal server pattern, IMAP 993 with SSL and SMTP 587 with TLS (465 as the SSL/TLS alternative). Their DirectAdmin DKIM documentation describes the DKIM DNS record as beginning with `x._domainkey.<domain>`; if your account shows a different selector, use that value instead.

## Optional Instantly-like campaign controls

These controls are deliberately opt-in so the existing validated baseline does not silently become more aggressive.

- `OUTREACH_NATURAL_PACING=false`
  - When `true`, the campaign policy reduces the effective maximum to one outbound message per GitHub run. With the current 15-minute schedule this prevents multiple sends from leaving back-to-back in the same run.
- `OUTREACH_CAMPAIGN_START_DATE=`
  - Optional `YYYY-MM-DD`. Before this local date, a requested `live` run is reduced to effective `validate` mode.
- `OUTREACH_CAMPAIGN_END_DATE=`
  - Optional `YYYY-MM-DD`. After this local date, a requested `live` run is reduced to effective `validate` mode.
- `OUTREACH_SLOW_RAMP_ENABLED=false`
  - Enables a deterministic gradual campaign limit. It never exceeds `OUTREACH_DAILY_LIMIT`.
- `OUTREACH_RAMP_START_DATE=`
  - Required when slow ramp is enabled. Use `YYYY-MM-DD`; explicit state prevents a hidden reset.
- `OUTREACH_RAMP_START_LIMIT=2`
- `OUTREACH_RAMP_INCREMENT_PER_DAY=2`
  - With start 2 and increment 2, the effective limit grows 2, 4, 6, 8, ... until the configured daily limit is reached.

The policy output is passed directly into preflight/verifier/sender as the effective mode and limits. A future/ended campaign or a ramp that has not started can only reduce live behavior. The original `OUTREACH_DAILY_LIMIT` and hard runtime caps remain the upper boundary.

See `docs/instantly-parity.md` for the full feature comparison and the remaining gaps such as multi-account rotation, longer sequences, A/Z variants, Unibox-style UI and warmup-network behavior.

## What sender preflight proves

The automated preflight proves only the checks it actually performs:

1. required runtime configuration is structurally valid;
2. SPF exists and, when configured, contains the expected provider token;
3. DMARC exists;
4. the configured DKIM selector resolves to a public key;
5. the Google service account can read the expected queue/suppression/log contracts;
6. in effective `live`, SMTP STARTTLS/SSL authentication works;
7. in effective `live`, IMAP SSL authentication and NOOP work.

It deliberately does **not** claim that a real received message passes SPF/DKIM/DMARC at Gmail/Outlook. That final authentication/alignment and inbox-placement evidence must still come from a real controlled test message and received headers before an execution-10 claim.

## Analytics and diagnostics

`scripts/outreach_analytics.py` runs after the sender with `if: always()` and is marked non-blocking. It reads only `OutreachQueue` and `Suppression` and writes a compact GitHub run summary containing:

- queue/status mix;
- verification mix;
- initial and follow-up SMTP-accepted counts;
- currently ready initial rows and due follow-ups;
- reply, bounce and opt-out counts/rates;
- suppression count;
- effective campaign policy values for the run.

The analytics layer intentionally says `SMTP-accepted`, not `delivered`: a successful SMTP transaction does not prove inbox placement. It also does not invent positive-interest or sales outcomes; those remain owner/controller reconciliation.

## Activation sequence

1. Keep `OUTREACH_ENABLED=false` while configuring secrets, repository variables and sharing the Sheet with the service account.
2. Confirm the actual mijn.host SMTP host and DKIM selector in DirectAdmin/DNS.
3. Leave the optional Instantly-like controls disabled for the first baseline validation, unless you intentionally want natural pacing or a dated/ramped campaign.
4. Set `OUTREACH_ENABLED=true` and `OUTREACH_MODE=validate`. Run manually. Campaign policy and preflight check configuration; no verifier call or mail send occurs.
5. Set `OUTREACH_MODE=verify`. Run manually on a small reviewed queue. Preflight runs first, then Reoon uses the documented single/bulk route; no mail is sent.
6. Review verification statuses, suppression behavior, compliance and message content.
7. If desired, enable `OUTREACH_NATURAL_PACING=true` and configure a slow-ramp start date before switching to live.
8. Set `OUTREACH_MODE=live` with the small default limits. Run manually before relying on the schedule. Preflight now also proves SMTP/IMAP login when campaign policy still permits effective live mode.
9. Send only a controlled test cohort and inspect the received message headers for real SPF/DKIM/DMARC alignment, plus provider readback, reply stop, short-`nee` opt-out, bounce handling and suppression behavior.
10. Scale only after healthy delivery/bounce/complaint/opt-out/reply evidence. Do not use the provider's technical maximum as the operating target and never use extra accounts/domains to bypass provider enforcement.

## Tests and dependency maintenance

CI installs the same outreach requirements before compilation/regression tests. Regression tests cover sender/verifier behavior, preflight DNS/auth/Sheet rules, campaign policy/ramp behavior, analytics calculations and GitHub workflow security invariants. All remote Actions used by repository workflows are required by tests to be pinned to a full 40-character commit SHA, and every workflow must declare explicit permissions without `write-all`.

Dependabot monitors both GitHub Actions and the Python `pip` requirements on a weekly cadence.

## Workflow schedule

The GitHub Actions schedule checks the queue every 15 minutes on weekdays at minute 7/22/37/52 during a broad UTC window. The offset avoids the highest-load start-of-hour pattern called out by GitHub. The Python runtime independently enforces the configured `Europe/Amsterdam` send window, so a delayed or timezone-shifted scheduled run cannot send outside that local window.

With `OUTREACH_NATURAL_PACING=true`, the policy layer reduces the effective per-run limit to one. The schedule then acts as a coarse pacing mechanism without sleeping inside paid runner time.

GitHub scheduled workflows execute only from the default branch. The schedule therefore becomes eligible only after this workflow is merged to the default branch, and the `OUTREACH_ENABLED` gate still prevents execution until explicitly enabled.
