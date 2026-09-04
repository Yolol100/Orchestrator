# Webactueel platform architecture

## One controller, six domain owners

`webactueel-workflow` is the only workflow controller. SEO, Design, Elementor, WordPress Quality Architect, Website QA and Leads own their domain result. Apps, tools and repositories only execute or return evidence.

## Seven active core repositories

1. `Yolol100/Orchestrator` — GitHub transport only.
2. `Yolol100/Designchecker` — shared browser, accessibility, performance and visual evidence for Design and Website QA.
3. `Yolol100/seochecker` — technical SEO evidence.
4. `Yolol100/elementorjson` — controlled Elementor runtime.
5. `Yolol100/programmeren` — generic WordPress/plugin audit harness.
6. `Yolol100/wordpressconnector` — canonical live WordPress read/write/rollback bridge.
7. `Yolol100/transcriberen` — caption acquisition runtime.

The machine-readable classification and migration gates live in `config/platform-repositories.json`.

## Consolidation rules

- `Checklist` remains a legacy runtime only until Designchecker has tested formal-evidence parity and the controller route is switched.
- `Elementorconnector` is maintenance-only until its state-token, capability-inventory and staging rollback behavior are proven in `wordpressconnector`.
- `Export-acf-to-csv` receives no new development; `ACF-Text-Manager` is the canonical product repository after unique history is reconciled.
- `elementor-design-kit-generator` is deprecated in favor of `elementorjson`.
- `Woocommerce-return-requests` is an archive candidate because it has no active implementation.

No source repository is deleted or archived until its stated exit gates are satisfied.

## Product repositories

All other repositories are product or project targets. They are opened only when a task addresses that product. They never become permanent orchestrator nodes solely because they exist.

## Explicit exclusions

`Yolol100/Leadscanner` and `Yolol100/vacature-engine` are excluded from this simplification and must not be mutated by this migration.
