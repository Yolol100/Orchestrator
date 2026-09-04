# Multi-step sequences, A-Z variants and ReplyHub

Reference date: 2026-09-04.

This layer extends the controlled SMTP/IMAP runtime with multi-step sequences, deterministic A-Z variant assignment, a Sheet-based unified reply inbox and derived transport analytics. It does not move lead finding, lead fit, compliance, copy ownership or sales-outcome ownership into the repository.

## Ownership boundary

- Leads/ChatGPT prepares and approves campaign copy, sequence steps, variants, waits and compliance state.
- The repository validates the prepared contract, chooses only among already-approved variants, schedules due work, applies transport limits and records provider readback.
- Reoon remains a bounded technical email-verification preprocessor for first contact.
- Google Sheets holds queue/sequence/readback state.
- SMTP/IMAP transports mail and returns replies/bounces.
- Reporting is descriptive/advisory. It never rewrites copy or silently changes compliance decisions.

## Backward compatibility

`OutreachSequences` is optional per lead. If a lead has no sequence rows, the existing `OutreachQueue` initial-message plus one-follow-up fields continue to work.

If a lead has one or more enabled sequence rows, the sequence contract becomes the transport source for that lead and the legacy follow-up fields are not used for additional sends. This prevents double sending.

## OutreachSequences contract

Columns:

`lead_id | sequence_id | sequence_version | step_number | variant_id | enabled | subject | body | wait_minutes | status | selected | scheduled_at | sent_at | message_id | sender_mailbox_id | sender_email | last_error | source`

Rules:

1. One lead may have one enabled sequence identity/version at a time.
2. Enabled steps must be contiguous from step 1.
3. Maximum configured depth is 50 steps.
4. Each step may use A-Z variants, so at most 26 variant IDs.
5. All variants within a step use the same `wait_minutes`.
6. Step 1 uses `wait_minutes=0`.
7. Step 1 requires a subject. A later step may leave subject blank; the runtime then carries the previous subject forward so normal threading can be preserved.
8. Every enabled variant must have pre-approved body copy.
9. At most one variant in a step may be persisted as `selected=true`.
10. A sent selected row must retain `sent_at` and `message_id`.

## Deterministic A-Z assignment

When multiple approved variants exist for a due step, the runtime selects one deterministically from `lead_id + sequence_id + sequence_version + step_number`. Re-running the same state therefore does not randomly swap a lead to a different copy variant.

The assignment is persisted before SMTP. This makes crash/reconciliation behavior auditable.

Variant selection is per step. A lead can therefore receive variant A in step 1 and variant B in step 2 when both were approved for those steps.

The repository does not generate variants itself.

## Timing and threading

Each follow-up becomes due after the previous successful sequence step plus its configured `wait_minutes`. Optional `OUTREACH_RANDOM_JITTER_MINUTES` adds a stable deterministic extra delay between 0 and the configured maximum. It does not sleep inside a runner; it simply makes the next step eligible later.

Threaded follow-ups use:

- the previous message's `Message-ID` in `In-Reply-To`;
- prior message IDs in `References`;
- the inherited subject when the follow-up subject is blank;
- the same persisted sending mailbox as the initial step.

A disabled/removed/changed or pacing-blocked assigned mailbox is not silently replaced for an existing thread.

## First-contact verification and stop conditions

The first outbound step still requires all existing send gates, including:

- `compliance_status=approved`;
- direct-SMTP-compatible opt-out mode;
- fresh technical verifier `safe` readback;
- no suppression match;
- campaign window/policy green;
- campaign daily/per-run capacity;
- mailbox daily/minimum-wait capacity.

Every later step still consumes campaign and mailbox capacity.

A reply, bounce, opt-out, block, ambiguous send error or suppression state stops later sequence sends. An SMTP result is recorded as transport acceptance only, not inbox placement or a commercial outcome.

## New campaign controls

Optional repository variables:

- `OUTREACH_MAX_NEW_LEADS_PER_DAY=100`
  - Additional cap on step-1 sends. The existing campaign daily limit remains the upper bound, so a value of 100 does not override a 20/day campaign cap.
- `OUTREACH_PRIORITIZE_NEW_LEADS=false`
  - Default `false` prioritizes already-due follow-ups before starting more sequences. Set `true` only when intentionally prioritizing new lead starts.
- `OUTREACH_RANDOM_JITTER_MINUTES=0`
  - Optional deterministic additional delay for sequence steps, bounded by the runtime to 0-120 minutes.
- `OUTREACH_REPLY_LOOKBACK_DAYS=14`
  - Number of IMAP days scanned for reply readback, bounded to 1-90.
- `OUTREACH_CAPTURE_OTHER_MAIL=false`
  - When true, ReplyHub can also record non-lead inbox messages as `other`. Keep false when the sending mailbox contains unrelated private mail.
- `OUTREACH_VARIANT_MIN_SAMPLES=20`
  - Minimum sends before variant comparison is allowed to produce a comparative recommendation.
- `OUTREACH_MAILBOX_BOUNCE_ALERT_RATE=5`
  - Descriptive 30-day bounce-rate alert threshold. It is not an automatic reputation/warmup score.

## ReplyInbox

Columns:

`reply_id | received_at | lead_id | company | email | mailbox_id | mailbox_email | subject | preview | classification | triage_status | owner_label | notes | message_id | in_reply_to | source`

ReplyHub scans every enabled mailbox in live mode. Messages are deduplicated by Message-ID when available, with a stable fallback fingerprint otherwise.

Transport classifications:

- `reply` - message from a known lead address;
- `opt_out` - reply matching the conservative opt-out detector;
- `bounce` - delivery-status evidence for a known recipient;
- `other` - optional non-lead inbox item when `OUTREACH_CAPTURE_OTHER_MAIL=true`.

`reply` and `other` enter `triage_status=new`. Opt-outs and bounces are transport-closed because the runtime also writes the queue/suppression stop state.

`owner_label` and `notes` are operator/controller fields. The runtime does not invent sales sentiment or mark a lead positive/negative/customer from free text.

## VariantAnalytics

Derived columns:

`generated_at | sequence_id | sequence_version | step_number | variant_id | sends | replies_attributed | bounces_attributed | opt_outs_attributed | reply_rate | bounce_rate | opt_out_rate | recommendation | note`

Reply/bounce/opt-out outcomes are attributed to the most recent sent sequence step before the outcome timestamp.

Recommendations are deliberately advisory:

- `insufficient_data`
- `no_comparison`
- `leader`
- `keep`
- `review`

`review` means an owner/controller should inspect the approved variant. It never pauses or rewrites copy automatically.

## MailboxHealth

Derived columns:

`generated_at | mailbox_id | sender_email | sends_30d | replies_30d | bounces_30d | opt_outs_30d | reply_rate | bounce_rate | opt_out_rate | state | note`

This is a 30-day transport dashboard only. It can surface a high observed bounce rate, but it is not a warmup score, sender-reputation score, spam-folder test or inbox-placement measurement.

## Sheet preflight

Before verifier/sender execution, the workflow now validates the exact contracts for:

- `OutreachSequences`
- `ReplyInbox`
- `VariantAnalytics`
- `MailboxHealth`

Malformed sequence definitions fail closed before outbound processing.

## Deliberate exclusions

The following are not implemented as fake local equivalents:

1. warmup network interactions or warmup health scoring;
2. spam-folder rescue/placement observations without external recipient infrastructure;
3. open-tracking pixels, link redirects or custom tracking domains by default;
4. automatic sender-account takeover for an already-started thread;
5. automatic copy generation or automatic variant disabling;
6. lead finding/enrichment inside the transport repository;
7. automatic reply-triggered subsequence sending before explicit owner/controller approval.

Those features either need external infrastructure, have privacy/deliverability trade-offs, or would cross the repository's ownership boundary.

## Current Instantly references used for behavior comparison

- Sequences: https://help.instantly.ai/en/articles/11967303-getting-started-with-sequences-section
- A/Z testing: https://help.instantly.ai/en/articles/6661549-a-z-testing-how-to-create-email-variants
- Campaign options: https://help.instantly.ai/en/articles/6222396-campaign-options
- Unibox reply detection: https://help.instantly.ai/en/articles/6248525-why-replies-aren-t-showing-in-unibox
- Unibox V2: https://help.instantly.ai/en/articles/11647830-introducing-unibox-v2
- Subsequences: https://help.instantly.ai/en/articles/9690757-subsequences
- Warmup: https://help.instantly.ai/en/articles/5975329-how-warm-up-works-and-why-it-s-important
- Custom tracking domains: https://help.instantly.ai/en/articles/6222341-setting-up-a-custom-tracking-domain
