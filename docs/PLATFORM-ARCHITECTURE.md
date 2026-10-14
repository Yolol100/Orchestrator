# Webactueel platform architecture

## One controller, domain-specific owners

`webactueel-workflow` is the only workflow controller. SEO, Design, Elementor, WordPress Quality Architect, Website QA, Leads and Vacature Search own their domain result; `transcribeer` is the bounded transcription owner mode under `webactueel-workflow`. Apps, tools and repositories only execute or return evidence.

## Nine active capability repositories

1. `Yolol100/Orchestrator` — GitHub transport only.
2. `Yolol100/Designchecker` — shared browser, accessibility, performance and visual evidence for Design and Website QA.
3. `Yolol100/seochecker` — technical SEO evidence.
4. `Yolol100/elementorjson` — controlled Elementor runtime.
5. `Yolol100/programmeren` — generic WordPress/plugin audit harness.
6. `Yolol100/wordpressconnector` — canonical live WordPress read/write/rollback bridge.
7. `Yolol100/transcriberen` — bounded public YouTube channel caption/comment corpus runtime.
8. `Yolol100/Leadscanner` — Leads-owned domain runtime (direct invocation, not an Orchestrator dispatcher adapter).
9. `Yolol100/vacature-engine` — Vacature Search-owned deterministic helper (direct invocation, not an Orchestrator dispatcher adapter).

The machine-readable classification and migration gates live in `config/platform-repositories.json`.

## Consolidation rules

- `Checklist` is rollback-only after migration to `Designchecker`. No archival until the regression observation window, live callsite audit, rollback proof and independent Website QA acceptance are recorded in [Checklist #31](https://github.com/Yolol100/Checklist/issues/31).
- `Elementorconnector` source has been consolidated into `wordpressconnector`; removal needs WordPress Connector **1.9.1+ on each relevant site**, staging Elementor read/write/readback and rollback, Page/Post/Saved Template JSON coverage, bulk ZIP export with `manifest.json`, legacy-caller inactivity and independent Website QA/owner acceptance as tracked in [Elementorconnector #30](https://github.com/Yolol100/Elementorconnector/issues/30).
- Historical sources/candidates in the machine-readable classification are **not** automatically active repositories or permission to archive/delete anything. Check the current live GitHub inventory, dependencies and explicit exit gates.

No source repository is deleted or archived until its stated exit gates are satisfied.

## Product repositories

All other repositories are product or project targets. They are opened only when a task addresses that product. They never become permanent orchestrator nodes solely because they exist.

## Explicit exclusions

`Yolol100/Leadscanner` and `Yolol100/vacature-engine` remain independent, domain-owned runtimes. They are counted in the nine-repository registry but are not registered as Orchestrator dispatcher adapters, and are outside the migration write scope.
