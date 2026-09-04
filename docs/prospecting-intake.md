# Provider-neutral prospecting intake

The Orchestrator repository is the SMTP/IMAP transport layer. It is not a lead database and does not scrape, enrich, score or personalize prospects. Net-new prospecting belongs to the Webactueel Leads control plane and enters this repository only after the lead has passed the required evidence, dedupe and compliance gates.

## Supported source routes

| Source | Role before transport | Transport effect |
| --- | --- | --- |
| Apollo connector | Net-new people/company search and selective enrichment when the connected capability is available and its credit/confirmation rules are satisfied | None beyond preserving source provenance in the approved queue |
| Public web discovery | Fallback candidate discovery and official-site contact lookup | None beyond preserving source provenance in the approved queue |
| Instantly | Optional later source/provider for search, enrichment and/or campaign delivery | Use the Instantly adapter when Instantly owns delivery; use this repository only when GitHub SMTP is the selected delivery provider |
| Manual/imported list | Candidate input supplied by the operator | Same evidence, dedupe, verification and compliance gates apply |

A provider record can support identity and contact context. It does not prove a website problem, buying intent, legal basis or permission to send commercial email.

## Required control-plane checks before queue creation

Leads/ChatGPT must complete these checks before writing `status=approved`:

1. Dedupe the official company domain against the canonical `Leadlijst`.
2. Confirm the official company name and official website.
3. Link any named recipient and business email to the company/domain with sufficient confidence; never construct or guess an address.
4. Verify the company/site fact used in personalization on the official domain.
5. Choose one specific, evidence-backed improvement idea and pass the swap test.
6. Determine the target-market compliance state: `approved`, `manual_review` or `blocked`.
7. Generate only reviewed copy from the canonical Leads mail source.
8. Check suppression before first contact.

`manual_review` and `blocked` records may never be sent by the runtime.

## Queue provenance

Use the existing `source` field in `OutreachQueue`, `OutreachSequences` and `OutreachLog`. Recommended campaign-scoped values are:

- `apollo`
- `public_web`
- `instantly_import`
- `manual_import`

Provider-specific record IDs, raw enrichment payloads, search queries, personal phone numbers and unnecessary personal data do not belong in the repository. Keep transient enrichment in the source/control-plane run and store only the minimum operational data required by the Sheet contracts.

## Verification boundary

For direct GitHub SMTP first contact, every address still requires fresh Reoon `safe` readback with `is_safe_to_send=true`. Apollo, Instantly, public discovery or an operator-provided address does not bypass this gate.

- `safe` -> technically sendable only when every other gate is green.
- `catch_all`, `unknown`, `role_account`, `inbox_full` -> `manual_review`.
- `invalid`, `disabled`, `disposable`, `spamtrap` -> `blocked`.

Technical verification is not consent or legal permission.

## Handoff to transport

Approved Leads output is written to the canonical Google Sheet:

- `OutreachQueue` for the lead, delivery state and first-contact verification state.
- Optional `OutreachSequences` for previously approved multi-step copy and A-Z variants.
- `Suppression` for addresses/domains that must not be contacted.

The runtime then performs only preflight, Reoon verification, bounded SMTP sending, IMAP reply/bounce/opt-out readback, sequence stopping, logging and derived reporting. It never turns a search result into a sendable lead by itself.

## Later Instantly adoption

Connecting Instantly later does not require replacing the Leads control plane. Instantly may become the prospecting and/or delivery provider, while Leads continues to own dedupe, official-site evidence, Opportunity Priority, personalization, compliance and interpretation of provider readback. This keeps the registry and campaign truth portable across providers.
