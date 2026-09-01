# Orchestrator repository instructions

## Scope
- This repository is transport infrastructure only. `webactueel-workflow` remains the controller and domain owners remain responsible for content decisions and acceptance.
- Do not add SEO, Design, Elementor, Leads, WordPress or QA policy here.
- Multiple repositories alone do not justify this dispatcher; prefer native Codex multi-repo execution when it can return the same evidence class without remote wait/resume.

## Before changing files
- Read `README.md`, `.github/workflows/ci.yml`, `.github/workflows/orchestrate.yml`, `config/adapter-registry.json`, schemas and the related tests.
- Use a non-runtime feature branch for source changes. Never use `runtime/**` branches for normal development.
- Preserve request immutability, registry fingerprinting, idempotency, dependency receipts, least-privilege tokens and cleanup guards.

## Validation
Run the same commands documented in the README:

```bash
python3 -m py_compile scripts/*.py tests/*.py
python3 -m unittest discover -s tests -v
```

If transport behavior, schemas or adapter config change, update/add the corresponding regression tests before claiming completion.

## Safety boundaries
- Do not place secrets, credentials, client/project truth or full project-source documents in requests, logs or artifacts.
- Do not broaden GitHub App permissions unless the controller contract explicitly requires it and the change is reviewed.
- Do not merge, publish, dispatch production writes or clean runtime branches solely because tests pass.
- A successful GitHub Action proves transport only; controller/owner readback and acceptance are still required.
