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

## Added in the Instantly-lite campaign-control layer

### Natural pacing

`OUTREACH_NATURAL_PACING=true` forces the effective maximum to one outbound message per GitHub run. With the current 15-minute schedule this prevents multiple messages from being sent back-to-back in a single run while preserving the existing hard limits. It is optional and disabled when the variable is absent.

### Campaign slow ramp

`OUTREACH_SLOW_RAMP_ENABLED=true` enables a deterministic ramp that starts at `OUTREACH_RAMP_START_LIMIT` and increases by `OUTREACH_RAMP_INCREMENT_PER_DAY` each local day until it reaches the configured `OUTREACH_DAILY_LIMIT`. An explicit `OUTREACH_RAMP_START_DATE` is required so the ramp cannot silently reset or invent state.

A configuration of start `2` and increment `2` mirrors the shape of Instantly's documented campaign slow-ramp behavior while remaining bounded by this repository's own daily cap.

### Campaign start/end dates

`OUTREACH_CAMPAIGN_START_DATE` and `OUTREACH_CAMPAIGN_END_DATE` are optional `YYYY-MM-DD` values. When a live run is outside that window, the policy layer changes the effective mode to `validate`; preflight and diagnostics can still run, but outbound mail fails closed.

### Run analytics and diagnosis

Every outreach workflow now attempts a read-only analytics summary after processing. It reports queue/status mix, verification mix, SMTP-accepted initial/follow-up counts, replies, bounces, opt-outs, suppression count and currently due work. The report deliberately calls SMTP success `SMTP-accepted`, not `delivered`, because inbox placement is not proven by an SMTP `250` response.

## Important gaps that remain

These are the largest differences from Instantly's current product behavior:

1. **Multi-account inbox rotation and per-account limits.** The current runtime still uses one SMTP/IMAP mailbox. Instantly can assign many accounts to a campaign and rotate sends while enforcing account and campaign limits.
2. **Multi-step sequences.** The current queue supports the initial message plus one approved follow-up. Instantly supports longer sequences with independent waits.
3. **A/Z variants and auto-optimization.** The repository does not choose copy variants. Adding this safely would require Leads to prepare approved variants and the runtime to persist deterministic variant assignment/analytics without generating copy itself.
4. **Unified reply inbox UI.** IMAP reply detection exists, but there is no Unibox-style operator interface or reply triage screen.
5. **Warmup network and warmup health score.** A repository cannot truthfully reproduce Instantly's mailbox warmup network, spam-folder placement observations, or network interactions without external recipient infrastructure. Do not fake this with self-mail loops.
6. **Open/link tracking and custom tracking domains.** These are intentionally not enabled by default because tracking pixels/redirects add privacy, deliverability and infrastructure trade-offs. Reply/bounce/opt-out metrics are more reliable for this controlled route.
7. **Lead finder/enrichment.** This remains outside the repository by design. Leads + ChatGPT owns candidate selection, evidence, dedupe, personalization and compliance.

## Recommended next implementation order

If additional Instantly-like behavior is needed, add it in this order:

1. optional multi-account sender pool with explicit per-account limits, sticky sender assignment for follow-ups, multi-mailbox IMAP readback and no bypass of `throttle/pause/blocked`;
2. provider-neutral campaign/sequence contract that lets Leads submit more than one pre-approved follow-up without giving the repository copy ownership;
3. deterministic A/Z assignment plus reply/bounce/opt-out analytics per approved variant;
4. operator reply queue/readback view;
5. only then consider tracking-domain support, and only after a separate privacy/deliverability review.

## Current Instantly references used for this comparison

- Campaign options: https://help.instantly.ai/en/articles/6222396-campaign-options
- Inbox rotation: https://help.instantly.ai/en/articles/7046484-inbox-rotation-assign-sending-accounts-to-a-campaign
- Account/campaign limits: https://help.instantly.ai/en/articles/6248612-account-and-campaign-limits
- Sequences: https://help.instantly.ai/en/articles/11967303-getting-started-with-sequences-section
- A/Z testing: https://help.instantly.ai/en/articles/6661549-a-z-testing-how-to-create-email-variants
- Campaign slow ramp: https://help.instantly.ai/en/articles/10056946-campaign-slow-ramp-system
- Campaign start/end dates: https://help.instantly.ai/en/articles/6756707-campaign-start-end-date
- Unibox reply detection: https://help.instantly.ai/en/articles/6248525-why-replies-aren-t-showing-in-unibox
- Warmup: https://help.instantly.ai/en/articles/5975329-how-warm-up-works-and-why-it-s-important
