# Prompt-strategy receipt

`Yolol100/Orchestrator` is transport-only. It does not select, rank, rewrite or optimize prompt techniques.

`webactueel-workflow` selects the task-adaptive prompt strategy before remote dispatch. Dispatch request schema v1.1 transports only a compact receipt:

- `contract_sha256`: exact shared prompt-strategy contract version;
- `strategy_sha256`: fingerprint of the full selected strategy;
- `techniques`: normalized technique IDs;
- `research_status`: must be `complete` or `not-required`;
- `verification`: bounded checks that must remain attached to the run.

Raw chat history, hidden reasoning, prompt templates and verified research context are intentionally not transported through this repository.

The validator fails closed on a contract hash mismatch, unknown/duplicate technique, pending research, malformed verification or an unsupported dispatch request version.

This keeps selection authority in the controller while allowing GitHub transport and run evidence to prove which strategy contract was active for a dispatch.
