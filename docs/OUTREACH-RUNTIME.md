# Outreach runtime boundary

Outreach domain execution no longer belongs in this transport-only Orchestrator.

- Process controller: `webactueel-workflow`
- Domain owner: `leads`
- Prospect discovery/qualification/prepare: `Yolol100/Leadscanner`
- SMTP/IMAP/suppression/readback runtime: `Yolol100/outreach-runtime`

The Orchestrator may transport a remote request only when real wait/resume, correlated multi-run state or managed-risk transport is required. It must not contain outreach policy, SMTP/IMAP implementations, prospect discovery or campaign logic.

The old outreach files were removed on the migration branch because `Leadscanner` remains the rollback/live fallback until the new runtime completes its own validate/readiness/live parity gates.
