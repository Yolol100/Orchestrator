# Instantly-like capability map

Reference date: 2026-09-04.

This repository is not presented as an Instantly clone. It now combines bounded public company/domain discovery with the existing controlled SMTP/IMAP runtime. Webactueel Leads remains owner of fit, official-site evidence, Opportunity Priority, bounded contact lookup, personalization, compliance and lifecycle interpretation.

## Covered now

| Instantly-style capability | Webactueel / Orchestrator equivalent | Status |
| --- | --- | --- |
| Net-new company discovery | approved `seed_site`, `directory_page` and `directory_index` sources | implemented, source-driven |
| Prospect filters | include/exclude terms, country and per-source limits | implemented, basic |
| Dedupe | canonical-domain check against `Leadlijst` + `ProspectCandidates` | implemented |
| Contact lookup | bounded per-company lookup stays in Leads; discovery runtime does not bulk-collect addresses | implemented in Leads |
| Email verification | Reoon first-contact freshness gate | implemented |
| Stop on reply | IMAP/ReplyHub blocks later sends | implemented |
| Bounce/opt-out suppression | suppression + stop state | implemented |
| Campaign limits/pacing | daily/per-run limits, windows, ramp and jitter | implemented |
| Sender authentication preflight | SPF, DKIM, DMARC, SMTP and IMAP checks | implemented |
| Multiple sending accounts | mailbox pool with per-mailbox guards and rotation | implemented |
| Sticky follow-up sender | sender persisted per queue/sequence | implemented |
| Multi-step sequences | up to 50 approved steps | implemented |
| Same-thread follow-ups | Message-ID/In-Reply-To/References | implemented |
| A-Z variants | up to 26 approved variants per step | implemented |
| Stable variant assignment | deterministic and persisted | implemented |
| Variant analytics | send/reply/bounce/opt-out reporting | implemented |
| Unified reply dataset | `ReplyInbox` | implemented operator layer |
| Mailbox transport health | 30-day transport metrics | implemented |

## Important Instantly capabilities that remain materially stronger

### Proprietary prospect database and waterfall enrichment

Instantly SuperSearch has a proprietary global B2B contact corpus, advanced filtering and a commercial multi-provider enrichment waterfall. The self-built Webactueel discovery engine is deliberately source-driven. It can find net-new companies from approved public sources, but a GitHub repository alone cannot honestly reproduce Instantly-scale contact coverage or a 5+ commercial-provider waterfall.

### Signals at Instantly scale

Leads can use current public/official company signals. This repository does not claim a continuously refreshed cross-web intent/data graph at Instantly scale.

### True warm-up network

A self-mail loop is not equivalent to Instantly's cross-account warm-up pool. No fake warmup score is implemented.

### Inbox placement network

Sender preflight proves configuration/connectivity, not inbox/spam/promotions placement across seed accounts. Real placement testing remains external.

### Cross-customer deliverability intelligence

Local bounce, suppression and mailbox-health data exist. Instantly has broader network-level deliverability telemetry that this single workspace cannot reproduce.

### Full Unibox/CRM application

`ReplyInbox`, `Leadlijst`, analytics and Sales handoff provide the state/data layer, but not a full rich web application with AI sentiment, bulk actions and CRM UX.

### Automated optimization and reply-triggered branches

A-Z reporting is advisory. Transport does not autonomously rewrite/disable approved copy or launch a new reply-triggered subsequence. Those decisions remain with Leads/controller.

### Open/click tracking

Tracking pixels/redirects remain off by default because of privacy/deliverability trade-offs. Reply, bounce, opt-out and downstream sales outcomes are the preferred optimization signals.

## A-Z versus ATS

There is no separate `ATS` variant in the current Leads model. The implemented transport feature is **A-Z variants**. Leads/`leadpromo.md` remains the copy owner and determines which variants are actually approved.

## Evidence boundary for mailing

Green CI proves code and contract behavior. SMTP acceptance proves only that the sender server accepted a message. It does not prove recipient delivery or primary-inbox placement. End-to-end mailing is only proven after a controlled received-message test with header/authentication inspection plus reply, opt-out, bounce and sequence readback checks.
