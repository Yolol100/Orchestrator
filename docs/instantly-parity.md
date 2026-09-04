# Instantly-like capability map

This repository is not an Instantly clone. It is the controlled SMTP/IMAP transport runtime owned by the Webactueel Leads workflow. Lead finding, evidence, personalization and compliance stay outside the transport repository so the same Leads control plane can use public discovery, Apollo now, or Instantly later without changing transport truth.

Reference date: 2026-09-04.

## Covered in the current Orchestrator runtime

| Instantly-style capability | Orchestrator equivalent | Status |
| --- | --- | --- |
| Stop sequence on reply | IMAP/ReplyHub readback moves the lead to `replied` and blocks later sends | implemented |
| Bounce suppression | Delivery-status bounces move the lead to `bounced` and add suppression | implemented |
| Opt-out suppression | Explicit opt-outs/direct reply opt-outs stop later sends and enter suppression | implemented |
| Email verification before first contact | Reoon preprocessor with fail-closed freshness gate | implemented |
| Daily campaign limit | `OUTREACH_DAILY_LIMIT` with hard runtime cap | implemented |
| Per-run pacing | `OUTREACH_MAX_SENDS_PER_RUN` plus optional natural pacing | implemented |
| Send window/start/end/ramp | local-time window, campaign dates and deterministic slow ramp | implemented |
| Sender authentication preflight | SPF, DKIM, DMARC, SMTP and IMAP checks | implemented |
| Multiple sending accounts | `OUTREACH_MAILBOXES_JSON` sender pool | implemented |
| Per-mailbox daily limit/minimum wait | mailbox-scoped guards plus campaign-wide cap | implemented |
| Inbox rotation | load-aware selection across enabled mailboxes | implemented |
| Sticky sender for follow-ups | sender mailbox/email persisted per queue/sequence | implemented |
| Multi-mailbox reply/bounce readback | ReplyHub scans every enabled mailbox | implemented |
| Multi-step sequences | `OutreachSequences`, up to 50 ordered approved steps | implemented |
| Independent step waits | `wait_minutes` per step | implemented |
| Same-thread follow-ups | `Message-ID`, `In-Reply-To`, `References`, inherited subject | implemented |
| A-Z variants | up to 26 pre-approved variants per step | implemented |
| Stable variant assignment | deterministic per lead/sequence/version/step, persisted before SMTP | implemented |
| Variant outcome reporting | `VariantAnalytics` based on send/reply/bounce/opt-out readback | implemented |
| Max new leads / follow-up priority | campaign controls in runtime | implemented |
| Random additional delay | deterministic bounded jitter | implemented |
| Unified reply dataset | `ReplyInbox` across configured mailboxes | implemented operator layer |
| Mailbox transport health | `MailboxHealth` 30-day send/reply/bounce/opt-out metrics | implemented |

## Prospecting and enrichment: intentionally outside this repository

Instantly now combines outreach with SuperSearch: a large B2B prospect database, advanced filters, verified work-email discovery, waterfall enrichment across multiple data providers and AI/web research. Reproducing that database inside GitHub would be the wrong architecture.

Webactueel uses a provider-neutral intake instead:

1. Leads deduplicates against the canonical Leadlijst.
2. Without Instantly input, Leads may use a genuinely connected native prospecting source such as Apollo for net-new people/company discovery and enrichment, subject to that connector's credit/permission rules.
3. Public web discovery remains the fallback.
4. Official-site evidence is still required for any company/site claim used in personalization.
5. Approved candidates enter `OutreachQueue` / `OutreachSequences`; only then does this repository take over transport.
6. Direct SMTP still requires fresh Reoon `safe` verification even when a prospect provider supplied an address.

This is functional composition, not a hidden lead-finder inside the repo. When Instantly is connected later it can replace or supplement the prospecting/provider layer while the Leads control plane and GitHub transport contracts remain stable.

See `docs/prospecting-intake.md` for the boundary contract.

## Where Instantly remains materially stronger

### 1. True warm-up network

Instantly operates a recipient-account warm-up network with engagement/spam-to-inbox interactions and a warm-up health score. A standalone GitHub repository cannot reproduce that evidence honestly. Self-mail loops are not equivalent.

### 2. Inbox placement testing

Instantly can test inbox/spam/promotions placement across providers, inspect SPF/DKIM/DMARC and blacklist signals, and schedule recurring placement tests. Our preflight validates configuration and transport; it does not prove inbox placement.

### 3. Provider matching / deliverability network intelligence

Instantly can route based on recipient/sender ESP combinations and has broader provider-level deliverability telemetry. Our mailbox pool deliberately does not guess recipient-provider routing.

### 4. Open/click tracking and custom tracking domains

Not enabled in the current runtime. Reply/bounce/opt-out outcomes are intentionally primary because tracking pixels/redirect domains add privacy and deliverability trade-offs. Add only after a separate legal/deliverability review.

### 5. Full Unibox application

`ReplyInbox` consolidates replies and supports controller/operator triage data, but it is not a dedicated web UI with AI sentiment, rich bulk actions and CRM-like interaction.

### 6. Automated copy optimization and reply-triggered branches

The runtime can report variant results but never rewrites or disables approved copy. Replies stop the current sequence. Any new reply-triggered subsequence requires an explicit Leads/controller state machine and approval.

## Campaign-control notes

- `OUTREACH_NATURAL_PACING=true` restricts effective sends to one outbound message per GitHub run.
- Slow ramp and campaign start/end dates only reduce or block sending; they never override hard caps.
- Extra mailboxes cannot multiply campaign-wide limits or bypass provider/reputation controls.
- Enabled sequence steps must be contiguous, pre-approved and aligned to an approved queue row.
- Variant selection is deterministic and persisted. A-Z is transport capability; Leads/`leadpromo.md` remains the copy owner and decides which variants are actually approved for a campaign.
- A reply, bounce, opt-out, suppression state, block or ambiguous send error stops later sequence sends.

## Current evidence boundary

Green repository CI proves compile/regression/contract behavior. SMTP acceptance proves only that the sender server accepted a message. Neither proves recipient delivery or inbox placement. A real received-message test with header/readback inspection is required before claiming live mailing is proven end-to-end.

## Current Instantly references used for this comparison

- SuperSearch and waterfall enrichment
- Campaign Options
- Sequences and A/Z testing
- Unibox V2
- Warm-Up / Email Accounts Dashboard
- Inbox Placement and automated placement tests

Keep this map evidence-bound: if Instantly changes a feature, refresh the comparison before making a parity claim.
