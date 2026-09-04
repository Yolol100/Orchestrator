# Instantly-like transport parity map

This repository is not an Instantly clone. It is a controlled SMTP/IMAP transport runtime owned by the Webactueel Leads workflow. The goal of this map is to adopt useful campaign mechanics without moving lead-fit, evidence, copy, compliance or sales-outcome ownership into the repository.

Reference date: 2026-09-04.

## Already covered

| Instantly-style capability | Orchestrator equivalent | Status |
| --- | --- | --- |
| Stop sequence on reply | IMAP reply readback moves the lead to `replied` and blocks later sends | implemented |
| Bounce suppression | Delivery-status bounces move the lead to `bounced` and add suppression | implemented |
| Opt-out suppression | Explicit opt-out and short direct `nee` replies move the lead to `opted_out` | implemented |
| Email verification before send | Reoon preprocessor with fail-closed freshness gate | implemented |
| Campaign daily limit | `OUTREACH_DAILY_LIMIT` with hard runtime cap | implemented |
| Per-run pacing bound | `OUTREACH_MAX_SENDS_PER_RUN` with hard runtime cap | implemented |
| Send schedule | Local-time weekday send window plus GitHub schedule | implemented |
| Sender/domain health preflight | SPF, DKIM, DMARC, Sheet contract, SMTP and IMAP checks | implemented |
| Follow-up | One pre-written threaded follow-up from the approved queue | implemented |
| Multiple sending accounts | `OUTREACH_MAILBOXES_JSON` sender pool | implemented |
| Per-account daily limit | `daily_limit` on each mailbox plus campaign-wide cap | implemented |
| Per-account minimum wait | `min_wait_minutes` on each mailbox | implemented |
| Inbox rotation | Load-aware selection across enabled mailboxes | implemented |
| Sticky sender for follow-up | `sender_mailbox_id`/`sender_email` persisted on queue | implemented |
| Multi-mailbox reply/bounce readback | IMAP sync over every enabled mailbox | implemented |
| Per-mailbox send analytics | GitHub summary groups SMTP-accepted sends by mailbox ID | implemented |

## Instantly-lite campaign-control layer

### Natural pacing

`OUTREACH_NATURAL_PACING=true` forces the effective maximum to one outbound message per GitHub run. With the current 15-minute schedule this prevents multiple messages from being sent back-to-back in a single run while preserving the existing hard limits. It is optional and disabled when the variable is absent.

### Campaign slow ramp

`OUTREACH_SLOW_RAMP_ENABLED=true` enables a deterministic ramp that starts at `OUTREACH_RAMP_START_LIMIT` and increases by `OUTREACH_RAMP_INCREMENT_PER_DAY` each local day until it reaches the configured `OUTREACH_DAILY_LIMIT`. An explicit `OUTREACH_RAMP_START_DATE` is required so the ramp cannot silently reset or invent state.

A configuration of start `2` and increment `2` mirrors the shape of Instantly's documented campaign slow-ramp behavior while remaining bounded by this repository's own daily cap.

### Campaign start/end dates

`OUTREACH_CAMPAIGN_START_DATE` and `OUTREACH_CAMPAIGN_END_DATE` are optional `YYYY-MM-DD` values. When a live run is outside that window, the policy layer changes the effective mode to `validate`; preflight and diagnostics can still run, but outbound mail fails closed.

### Multi-mailbox rotation

When `OUTREACH_MAILBOXES_JSON` is configured, initial messages rotate across enabled sending accounts that are below their own daily limit and outside their own minimum-wait interval. The campaign-wide limit and per-run limit remain separate upper bounds, so extra accounts do not multiply or bypass the campaign cap.

The chosen account is persisted as `sender_mailbox_id` plus `sender_email`. Follow-ups stay on that same account. If that account is disabled, removed, out of capacity or its sender identity changed, the follow-up is deferred/fails closed instead of silently moving to another sender and breaking the original thread.

### Run analytics and diagnosis

Every outreach workflow attempts a read-only analytics summary after processing. It reports queue/status mix, verification mix, SMTP-accepted initial/follow-up counts, replies, bounces, opt-outs, suppression count, currently due work and the send mix per mailbox ID. The report deliberately calls SMTP success `SMTP-accepted`, not `delivered`, because inbox placement is not proven by an SMTP `250` response.

## Important gaps that remain

These are the largest differences from Instantly's current product behavior:

1. **Multi-step sequences.** The current queue supports the initial message plus one approved follow-up. Instantly supports longer sequences with independent waits.
2. **A/Z variants and auto-optimization.** The repository does not choose copy variants. Adding this safely would require Leads to prepare approved variants and the runtime to persist deterministic variant assignment/analytics without generating copy itself.
3. **Unified reply inbox UI.** IMAP reply detection exists across configured mailboxes, but there is no Unibox-style operator interface or reply triage screen.
4. **Warmup network and warmup health score.** A repository cannot truthfully reproduce Instantly's mailbox warmup network, spam-folder placement observations, or network interactions without external recipient infrastructure. Do not fake this with self-mail loops.
5. **Open/link tracking and custom tracking domains.** These are intentionally not enabled by default because tracking pixels/redirects add privacy, deliverability and infrastructure trade-offs. Reply/bounce/opt-out metrics are more reliable for this controlled route.
6. **Lead finder/enrichment.** This remains outside the repository by design. Leads + ChatGPT owns candidate selection, evidence, dedupe, personalization and compliance.
7. **Automatic disconnected-account takeover.** This implementation intentionally does not move an already-contacted lead to a different sender account automatically because that can break threading and weaken transport evidence. Manual reconciliation is required for that case.

## Recommended next implementation order

If additional Instantly-like behavior is needed, add it in this order:

1. provider-neutral campaign/sequence contract that lets Leads submit more than one pre-approved follow-up without giving the repository copy ownership;
2. deterministic A/Z assignment plus reply/bounce/opt-out analytics per approved variant;
3. operator reply queue/readback view;
4. optional reply-to routing/consolidation only after explicit mailbox ownership and readback rules are defined;
5. only then consider tracking-domain support, and only after a separate privacy/deliverability review.

## Current Instantly references used for this comparison

- Campaign options: https://help.instantly.ai/en/articles/6222396-campaign-options
- Inbox rotation: https://help.instantly.ai/en/articles/7046484-inbox-rotation-assign-sending-accounts-to-a-campaign
- Account/campaign limits: https://help.instantly.ai/en/articles/6248612-account-and-campaign-limits
- Keep sequence in same thread: https://help.instantly.ai/en/articles/7914807-keep-email-sequences-in-the-same-thread
- Sequences: https://help.instantly.ai/en/articles/11967303-getting-started-with-sequences-section
- A/Z testing: https://help.instantly.ai/en/articles/6661549-a-z-testing-how-to-create-email-variants
- Campaign slow ramp: https://help.instantly.ai/en/articles/10056946-campaign-slow-ramp-system
- Campaign start/end dates: https://help.instantly.ai/en/articles/6756707-campaign-start-end-date
- Unibox reply detection: https://help.instantly.ai/en/articles/6248525-why-replies-aren-t-showing-in-unibox
- Warmup: https://help.instantly.ai/en/articles/5975329-how-warm-up-works-and-why-it-s-important
