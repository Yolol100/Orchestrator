# GitHub Orchestrator — Controlled Multi-Repository Automation

> **Portfolio flagship · Python · GitHub Actions · GitHub App tokens · JSON contracts**

GitHub Orchestrator is a controlled transport layer for coordinating approved automation work across multiple specialist repositories. It focuses on least-privilege access, explicit dependencies, traceable requests and inspectable results instead of treating a triggered workflow as proof that the work was accepted.

**Built by:** [Andrew Baeten](https://github.com/Yolol100) · [Portfolio](https://andrewbaeten.nl)

## What problem it solves

Multi-repository automation can quickly become difficult to audit: one workflow triggers another, permissions become too broad, dependencies are implicit and a green job is mistaken for a correct result. This project keeps transport separate from domain decisions and records the exact repositories, request state, correlation data and cleanup obligations involved in each run.

## Portfolio snapshot

| Area | What it demonstrates |
| --- | --- |
| Orchestration | Bounded multi-repository workflow coordination |
| Security | Short-lived least-privilege GitHub App tokens |
| Reliability | Idempotency, dependency receipts and registry fingerprint validation |
| Traceability | Correlation-stable request/result contracts and `transport-plan.json` evidence |
| Engineering | Python, GitHub Actions, JSON contracts, compile checks and unit tests |
| Safety | Temporary runtime branches, explicit approvals and controlled cleanup |

## Architecture

```text
approved request + dependency receipts
                ↓
        GitHub Orchestrator
                ↓
       registered adapters
        ↙               ↘
temporary request     append-only route
branch / request PR   where required
        ↓               ↓
       specialist artifact/result
                ↓
          readback + acceptance
```

The Orchestrator is a transport/execution layer. It does not make SEO, WordPress, Elementor, design, leads or QA decisions itself.

## What it does

1. Receives one immutable dispatcher request on a temporary `runtime/**` branch.
2. Validates workflow ID, generation, approval policy, dependency receipts and the exact adapter-registry fingerprint.
3. Restricts a short-lived GitHub App token to only the repositories required by that request.
4. Writes only controller-ready request files to registered specialist adapters.
5. Does not start downstream work merely because an upstream node was invoked.
6. Produces `transport-plan.json` with head SHAs, event IDs, request locators and cleanup obligations.
7. Returns control to the owning workflow for readback, domain acceptance and the next generation.

## Required configuration

The current deployment uses `Yolol100/Orchestrator`. Install the GitHub App only on repositories the controller is allowed to operate.

Repository variable:

- `WEB_ACTUEEL_APP_CLIENT_ID`

Actions secret:

- `WEB_ACTUEEL_APP_PRIVATE_KEY`

The design splits least-privilege tokens by transport type. Ordinary request-file adapters receive only `contents: write`; guarded WordPress request-PR transport receives `contents: write` plus `pull_requests: write` only where required. The normal workflow `GITHUB_TOKEN` remains `contents: read` for this repository.

## Starting a request

Preferred route:

1. Create a temporary branch from `main`, for example `runtime/wf-abcdef123456-g1`.
2. Add exactly one request under `requests/queue/<request-id>.json`.
3. The push starts `.github/workflows/orchestrate.yml`.
4. Read the resulting `webactueel-transport-<run_id>` artifact.
5. Correlation and domain acceptance happen outside the transport layer.

`workflow_dispatch` is intended only for manual replay of an existing request file on the selected ref. Idempotency prevents duplicate side effects.

## When this dispatcher is not needed

Use the lightest native route that can provide the required evidence and execution class. A direct connected app or site tool should be preferred over generic browser or repository automation when it can complete the task safely.

Use this Orchestrator when remote GitHub runs, wait/resume behaviour, dependency waves, persistent transport state, rollback/approval across multiple runs or stricter reproducible evidence are actually required.

## Important boundaries

- `invoked` is never the same as `accepted`.
- A dependency is satisfied only when the request contains the required controller-issued `dependency_receipt`.
- Registered adapters keep their own transport contract; the Orchestrator does not silently convert one transport mode into another.
- WordPress runtime writes require the configured approval boundary.
- Customer/project truth does not belong on `main`; temporary runtime state is cleaned up only after readback and acceptance.
- A green GitHub Action proves transport execution, not domain correctness.

## Local verification

These commands are also used as CI sources:

```bash
python3 -m py_compile scripts/*.py tests/*.py
```

```bash
python3 -m unittest discover -s tests -v
```

Use a real staging/read-only smoke test before allowing write or release paths.

## Cleaning temporary runtime branches

After controller closure, run:

```bash
python3 scripts/cleanup_runtime_branches.py transport-plan.json --confirm-workflow-id <WF-ID>
```

Ordinary request branches are removed only when the current SHA still matches the transport receipt. Guarded request-PR routes can require a separately controller-verified current-head JSON file. Without explicit verification, cleanup fails closed. Fixed branches are never deleted.

## Project status and support

The transport layer is actively developed and contract-driven. Extensions require a registered adapter, test evidence and explicit controller acceptance. Report reproducible defects through [GitHub Issues](https://github.com/Yolol100/Orchestrator/issues) without publishing private keys, tokens or request payloads containing customer data.

## About the developer

I am **Andrew Baeten**, a Senior WordPress Developer & Web Designer with 10+ years of experience across 70+ WordPress projects. I build WordPress/WooCommerce solutions as well as QA, SEO and automation tooling around reliable website delivery.

[Portfolio](https://andrewbaeten.nl) · [LinkedIn](https://www.linkedin.com/in/andrew-baeten-305a1478/) · [Email](mailto:info@andrewbaeten.nl)

## License

This repository currently has no open-source license. Reuse, distribution or derivative works are not permitted without explicit permission from the copyright holder.
