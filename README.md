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
Webactueel controller
        ↓ immutable request + approval_policy + dependency receipts
Orchestrator → adapter registry ─┬→ temporary runtime branch / request PR
        ↓                        └→ existing append-only branch where required
transport-plan.json                          ↓
        └──────── specialist artifact/result → readback + domain acceptance ───┘
```

The Orchestrator is a transport/execution layer. It does not make SEO, WordPress, Elementor, design, leads or QA decisions itself.

## What it does

1. Receives one immutable dispatcher request on a temporary `runtime/**` branch.
2. Validates workflow ID, generation, approval policy, dependency receipts and the exact adapter-registry fingerprint.
3. Restricts a short-lived GitHub App token to only the repositories required by that request.
4. Writes only controller-ready request files to registered specialist adapters.
5. Does not start downstream work merely because an upstream node was invoked.
6. Produces `transport-plan.json` with head SHAs, event IDs, request locators and cleanup obligations.
7. Returns control to `webactueel-workflow` for readback, domain acceptance and the next generation.

## Required configuration

The current deployment uses `Yolol100/Orchestrator`. Install the GitHub App only on specialist repositories the controller is allowed to operate.

Repository variable:

- `WEB_ACTUEEL_APP_CLIENT_ID`

Actions secret:

- `WEB_ACTUEEL_APP_PRIVATE_KEY`

The design splits least-privilege tokens by transport type: ordinary request-file adapters receive only `contents: write`; the guarded WordPress request-PR adapter receives `contents: write` plus `pull_requests: write` only on `wordpressconnector`. The normal workflow `GITHUB_TOKEN` remains `contents: read` for this repository.

## Starting a request

Preferred route from the ChatGPT/GitHub connector:

1. Create a temporary branch from `main`, for example `runtime/wf-abcdef123456-g1`.
2. Add exactly one new file under `requests/queue/<request-id>.json`.
3. The push starts `.github/workflows/orchestrate.yml`.
4. Read the resulting `webactueel-transport-<run_id>` artifact.
5. Correlation and domain acceptance happen afterward in the controller/owner.

`workflow_dispatch` is intended only for manual replay of an existing request file on the selected ref. Idempotency prevents duplicate side effects.

## When this dispatcher is not needed

Choose the lightest native route that can provide the required evidence/execution class. An exact connected app or exposed site tool/WebMCP should be preferred over generic browser automation; a native Work/Codex browser should be preferred over a repository adapter when persistent repository evidence is not needed. Repository count by itself is not a reason to activate this dispatcher.

Use this Orchestrator when remote GitHub runs, wait/resume behaviour, dependency waves, persistent transport state, rollback/approval across multiple runs or stricter reproducible evidence are actually required. A scheduled webhook can wake an existing workflow, but it does not replace the dispatcher request, owner decision or acceptance receipt.

## Important boundaries

- `invoked` is never the same as `accepted`.
- A dependency is satisfied only when the request contains a controller-issued `dependency_receipt`.
- `elementorjson` uses only its registered correlated request-file route through `requests/runtime.json`; this is not a free generic dispatch route and acceptance requires exact request/result correlation.
- `wordpressconnector` intentionally uses a request PR on a temporary branch; the Orchestrator does not convert it into a normal push route, and a WordPress runtime node requires `approval_before_write` or stricter.
- `transcriberen` uses its own append-only `runtime-requests` queue; the dispatcher does not create a new runtime branch for it.
- Customer/project truth does not belong on `main`. Temporary runtime branches are removed only after readback and acceptance.
- A green GitHub Action proves transport execution, not domain correctness.

## Local verification

These commands are also the CI source. The Runme Action executes the same named Markdown cells so the README and CI stay aligned.

```bash {"name":"compile-python"}
python3 -m py_compile scripts/*.py tests/*.py
```

```bash {"name":"regression-tests"}
python3 -m unittest discover -s tests -v
```

Use a real staging/read-only smoke test before allowing write or release paths.

## Cleaning temporary runtime branches

After controller closure, run:

```bash
python3 scripts/cleanup_runtime_branches.py transport-plan.json --confirm-workflow-id <WF-ID>
```

Ordinary request branches are removed only when the current SHA still exactly matches the transport receipt. A guarded WordPress request PR can legitimately move after validated result writeback; for that case, provide a separate controller-verified JSON file with `--verified-heads verified-heads.json`, for example:

```json
{"Yolol100/wordpressconnector:runtime/...":"<current-40-hex-sha>"}
```

Without that explicit current SHA, cleanup fails closed. Fixed branches are never deleted.

## Project status and support

The transport layer is actively developed and contract-driven. Extensions require a registered adapter, test evidence and explicit controller acceptance. Report reproducible defects through [GitHub Issues](https://github.com/Yolol100/Orchestrator/issues) without publishing private keys, tokens or request payloads containing customer data.

## About the developer

I am **Andrew Baeten**, a Senior WordPress Developer & Web Designer with 10+ years of experience across 70+ WordPress projects. I build WordPress/WooCommerce solutions as well as QA, SEO and automation tooling around reliable website delivery.

[Portfolio](https://andrewbaeten.nl) · [LinkedIn](https://www.linkedin.com/in/andrew-baeten-305a1478/) · [Email](mailto:info@andrewbaeten.nl)

## License

This repository currently has no open-source license. Reuse, distribution or derivative works are not permitted without explicit permission from the copyright holder.
