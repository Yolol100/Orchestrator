# Instantly-like transport parity map

This repository is not an Instantly clone. It is a controlled SMTP/IMAP transport runtime owned by the Webactueel Leads workflow. The goal is to adopt useful campaign mechanics without moving lead-fit, evidence, copy, compliance or sales-outcome ownership into the repository.

Reference date: 2026-09-04.

## Covered now

| Instantly-style capability | Orchestrator equivalent | Status |
| --- | --- | --- |
| Stop sequence on reply | IMAP/ReplyHub readback moves the lead to `replied` and blocks later sends | implemented |
| Bounce suppression | Delivery-status bounces move the lead to `bounced` and add suppression | implemented |
| Opt-out suppression | Explicit opt-out and direct short `nee` replies move the lead to `opted_out` | implemented |
| Email verification before first contact | Reoon preprocessor with fail-closed freshness gate | implemented |
| Campaign daily limit | `OUTREACH_DAILY_LIMIT` with hard runtime cap | implemented |
| Per-run pacing bound | `OUTREACH_MAX_SENDS_PER_RUN` with hard runtime cap | implemented |
| Send schedule | Local-time weekday send window plus GitHub schedule | implemented |
| Sender/domain health preflight | SPF, DKIM, DMARC, Sheet contract, SMTP and IMAP checks | implemented |
| Multiple sending accounts | `OUTREACH_MAILBOXES_JSON` sender pool | implemented |
| Per-account daily limit | `daily_limit` on each mailbox plus campaign-wide cap | implemented |
| Per-account minimum wait | `min_wait_minutes` on each mailbox | implemented |
| Inbox rotation | Load-aware selection across enabled mailboxes | implemented |
| Sticky sender for follow-ups | `sender_mailbox_id`/`sender_email` persisted on queue/sequence | implemented |
| Multi-mailbox reply/bounce readback | ReplyHub scans every enabled mailbox | implemented |
| Multi-step sequences | `OutreachSequences`, up to 50 ordered approved steps | implemented |
| Independent waits | `wait_minutes` per step | implemented |
| Same-thread follow-ups | `In-Reply-To`, `References`, inherited subject and sticky mailbox | implemented |
| A-Z copy variants | Up to 26 approved variants per step | implemented |
| Deterministic variant assignment | Stable per lead/sequence/version/step assignment, persisted before SMTP | implemented |
| Variant outcome analytics | `VariantAnalytics` with reply/bounce/opt-out last-touch attribution | implemented |
| Max new leads | `OUTREACH_MAX_NEW_LEADS_PER_DAY` | implemented |
| Prioritize new leads | `OUTREACH_PRIORITIZE_NEW_LEADS` | implemented |
| Random additional delay | Deterministic `OUTREACH_RANDOM_JITTER_MINUTES` | implemented |
| Unified reply list | `ReplyInbox` Sheet across all configured sending mailboxes | implemented (operator view) |
| Per-mailbox transport analytics | `MailboxHealth` 30-day transport readback | implemented |

## Campaign-control layer

### Natural pacing

`OUTREACH_NATURAL_PACING=true` forces the effective maximum to one outbound message per GitHub run. With the current 15-minute schedule this prevents multiple messages from leaving back-to-back in one run while preserving existing hard limits.

### Campaign slow ramp

`OUTREACH_SLOW_RAMP_ENABLED=true` enables a deterministic ramp starting at `OUTREACH_RAMP_START_LIMIT` and increasing by `OUTREACH_RAMP_INCREMENT_PER_DAY` each local day until it reaches `OUTREACH_DAILY_LIMIT`. An explicit `OUTREACH_RAMP_START_DATE` is required so the ramp cannot silently reset.

### Campaign start/end dates

`OUTREACH_CAMPAIGN_START_DATE` and `OUTREACH_CAMPAIGN_END_DATE` are optional `YYYY-MM-DD` values. Outside the permitted window, a requested live run is reduced to validation behavior and cannot send.

### Multi-mailbox rotation

Initial messages rotate only across enabled accounts that are below their own daily limit and outside their own minimum-wait interval. Campaign-wide daily/per-run limits remain separate upper bounds, so extra accounts do not multiply or bypass a campaign cap.

Follow-ups remain on the sender stored for the original thread. A disabled, removed, capacity-blocked or identity-changed account is not silently replaced.

### Multi-step sequence contract

`OutreachSequences` lets Leads supply already-approved sequence steps without giving the repository copy ownership. Enabled steps must be contiguous from step 1, and every variant for a step shares the same wait. The transport supports up to 50 steps and A-Z variants per step.

A later step with a blank subject inherits the prior subject. The runtime stores `Message-ID`, uses `In-Reply-To`/`References`, and keeps the same sending mailbox so threaded replies remain auditable.

A reply, bounce, opt-out, block, suppression state or ambiguous send error stops later sequence sends.

### Variants and advisory optimization

Variant choice is deterministic per step and persisted. `VariantAnalytics` reports sends plus reply/bounce/opt-out attribution. It can label a sufficiently sampled underperforming variant `review`, but it never rewrites, disables or invents copy. Leads/controller ownership is preserved.

This is intentionally narrower than Instantly auto-optimization because this runtime does not depend on open/click tracking, and reply evidence is the safer primary outcome signal for the current route.

### ReplyHub

`ReplyInbox` consolidates IMAP readback from enabled sending accounts with deduplication, preview, classification, triage status, mailbox identity and operator notes. Known lead replies immediately stop later sends; opt-outs and bounces also update suppression/readback state.

It is a useful operator queue but not a full Unibox web application: there is no dedicated web UI, AI sentiment engine, bulk-reply composer or CRM-like interface in this repository.

### Reporting

`VariantAnalytics` and `MailboxHealth` are derived reporting tabs. Mailbox health rows report observed 30-day sends/replies/bounces/opt-outs and can flag a high bounce rate. They deliberately do not claim inbox placement, warmup health or sender reputation.

## Important gaps that remain

These are now the largest differences from Instantly's product behavior or features intentionally kept outside this transport repository:

1. **True warmup network and warmup health score.** A repository cannot reproduce Instantly's recipient network interactions, spam-folder placement observations or warmup behavior without external mailbox infrastructure. Self-mail loops would not be equivalent evidence.
2. **Open/link tracking and custom tracking domains.** Not enabled by default because pixels and redirect domains create privacy, infrastructure and deliverability trade-offs. Reply/bounce/opt-out evidence remains the preferred signal for this controlled route.
3. **Full Unibox-style web application.** `ReplyInbox` provides a consolidated operator dataset, but not Instantly's full inbox UI, AI sentiment, bulk actions or rich reply workflow.
4. **Lead finder/enrichment.** Deliberately outside this repository. Leads + ChatGPT owns candidate selection, official-site evidence, dedupe, personalization and compliance.
5. **Automatic disconnected-account takeover.** Deliberately not implemented for an already-started thread because switching sender identity can break threading and weaken evidence. Manual reconciliation remains required.
6. **Automatic reply-triggered subsequences.** A reply already stops the active sequence. Starting a new automated branch based on free-text reply/status requires explicit Leads/controller policy and approval; the transport does not infer this itself.
7. **Automatic copy takeover/optimization.** The reporting layer recommends review only. It does not deactivate approved copy automatically.

## If more parity is needed

The next technically plausible work should be evaluated in this order:

1. build a lightweight operator UI on top of `ReplyInbox` only if the Sheet becomes too cumbersome;
2. add explicit controller-approved reply/subsequence actions if Webactueel defines a safe state machine for them;
3. add a pluggable transport-health signal interface for external inbox-placement/warmup evidence, without inventing a local score;
4. evaluate tracking-domain support only after a separate privacy, legal and deliverability review.

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
- Unibox V2: https://help.instantly.ai/en/articles/11647830-introducing-unibox-v2
- Subsequences: https://help.instantly.ai/en/articles/9690757-subsequences
- Warmup: https://help.instantly.ai/en/articles/5975329-how-warm-up-works-and-why-it-s-important
- Custom tracking domains: https://help.instantly.ai/en/articles/6222341-setting-up-a-custom-tracking-domain
