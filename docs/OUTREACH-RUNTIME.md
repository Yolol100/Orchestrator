# Leads runtime boundary

Outreach domain execution does not belong in this transport-only Orchestrator.

- Process controller: `webactueel-workflow`
- Domain owner: `leads`
- Leads execution runtime: `Yolol100/Leadscanner`
- Leadscanner owns prospect discovery, qualification, contact enrichment, zero-touch prepare, sender readiness, SMTP/IMAP delivery, reply/opt-out/bounce readback, suppression and transport logging.
- `Yolol100/outreach-runtime` was retired and deleted on 2026-09-07. It must not be referenced as an active dependency or platform repository.

The Orchestrator may transport a remote request only when real wait/resume, correlated multi-run state or managed-risk transport is required. It must not contain outreach policy, SMTP/IMAP implementations, prospect discovery or campaign logic.

This keeps one Leads runtime while preserving the controller boundary: `webactueel-workflow -> leads -> Leadscanner`.
