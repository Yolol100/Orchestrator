# Public prospecting intake

This repository now contains a bounded, source-driven public company discovery capability plus the existing controlled SMTP/IMAP transport runtime. It is **not** a proprietary B2B contact database and it does not replace the Webactueel Leads owner.

The self-built route intentionally does not use Apollo. It discovers net-new company websites from explicitly approved public source pages, applies basic filters, verifies the official site can be read and deduplicates company domains. Contact lookup stays in Leads and remains bounded per company; direct SMTP still requires fresh Reoon verification before first contact.

## Role boundaries

- **Prospect discovery runtime:** discovers candidate company domains and public company context from approved sources. It never collects contact addresses and never approves outreach.
- **Leads + ChatGPT:** owns ICP/fit, official-site evidence, Opportunity Priority, contact lookup, personalization, compliance, mail copy, provider selection and lifecycle interpretation.
- **Reoon:** verifies a first-contact email for direct SMTP. A `safe` result is technical evidence, not permission to send.
- **GitHub SMTP runtime:** sends only already-approved queue/sequence rows after every send gate is green.
- **Leadscanner:** optional technical website evidence only; never prospecting or transport.
- **Instantly later:** may supplement discovery/enrichment and/or delivery without changing Leads ownership.

## Discovery Sheet contract

### `ProspectSources`

`source_id | source_type | source_url | country | include_terms | exclude_terms | max_candidates | approved | enabled`

Supported source types:

- `seed_site`: treat the source URL itself as one company candidate.
- `directory_page`: inspect one approved public source page and treat external website links as candidate company sites.
- `directory_index`: inspect one approved index page, follow a bounded set of same-source profile links, then extract external candidate company websites from those profiles.

`approved=true` is mandatory. The operator remains responsible for choosing sources that may be accessed for this purpose. The runtime also honors `robots.txt`, uses bounded reads and pacing, and blocks private/link-local/local network targets and unsafe redirects.

### `ProspectCandidates`

`candidate_id | discovered_at | company | website | source_url | source_id | source_type | country | matched_terms | status | reason`

New rows always use `status=discovered`. Discovery never writes `approved`, `safe`, `verzonden`, `positief` or another outreach/sales outcome.

## Dedupe and handoff

Before appending a candidate, discovery deduplicates the normalized company domain against both `Leadlijst` and existing `ProspectCandidates` rows.

The discovery result is candidate evidence only. Leads must still perform the official-site fact/idea check, swap-test, one-company contact lookup, compliance decision, canonical copy generation and Reoon verification before direct SMTP.

## GitHub Actions workflow

`.github/workflows/prospect-discovery.yml` supports:

1. `validate` — contract check of the required Sheet tabs and configured sources.
2. `bootstrap` — explicitly create `ProspectSources` and `ProspectCandidates` tabs/headers when absent.
3. `discover` — crawl only enabled + approved sources, deduplicate, append discovered company candidates and emit `prospect-discovery-report.json`.

Scheduled discovery remains disabled unless repository variable `PROSPECT_DISCOVERY_ENABLED=true`. The discovery job receives only the Google service-account secret. It never receives SMTP/IMAP credentials, Reoon or mailbox-pool secrets.

## Limits and non-goals

A GitHub repository by itself cannot honestly reproduce Instantly's proprietary B2B contact graph, commercial multi-provider enrichment waterfall, cross-customer warmup network, cross-customer deliverability intelligence or real inbox-placement seed network.

The self-built route gives Webactueel an owned, auditable company-discovery layer now. If Instantly is connected later, it can supplement prospect/contact enrichment while Leads and the existing SMTP contracts remain stable.
