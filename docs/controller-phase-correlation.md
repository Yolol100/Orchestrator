# Controller phase and checkpoint correlation

This repository transports controller-approved work. It does not decide task size, phase content, audit criteria, test scenarios, repair loops, or acceptance.

## Ownership boundary

`webactueel-workflow` owns adaptive execution and decides whether a task is `single_pass`, `checkpointed`, or `phased`. It also owns every phase goal, audit/test profile, repair loop, gate decision, and final end-to-end acceptance.

The GitHub Orchestrator only preserves enough immutable correlation to send a controller-approved execution segment to a specialist repository and return evidence to the same controller state.

## Existing correlation fields

Use the existing request contract instead of adding a second phase controller here:

- `workflow_id` identifies the complete controller task.
- `work_item_id` identifies the resumable work item when persistence is required.
- `generation` identifies the current controller execution generation. Increment it when the controller emits a new remote generation after accepted readback or material replan.
- `dependency_receipts[*].checkpoint_id` binds downstream work to an already accepted controller checkpoint.
- `dependency_receipts[*].evidence_ids` records the evidence accepted for that dependency.
- `prompt_strategy.strategy_sha256` binds the dispatched work to the controller-selected strategy.
- `input_fingerprint` binds every node to its exact controller-approved input.
- `idempotency_key`, immutable request content, request `head_sha`, `request_sha256`, workflow run ID and artifacts provide transport/readback correlation.

A controller-local `phase_id` should map to the current `workflow_id + generation + checkpoint_id` state. Do not duplicate the complete phase plan, W-question analysis, audit plan, test plan, acceptance criteria, repair policy, or gate state in this repository.

## Phase handoff sequence

1. The controller performs its W-question/task-semantic analysis and selects the execution shape.
2. The controller defines a phase goal, acceptance criteria, audit/test profile and the smallest remote work segment if GitHub transport is actually required.
3. The controller dispatches that segment using the existing immutable request contract.
4. The Orchestrator validates and transports only controller-ready nodes.
5. The specialist produces correlated runtime evidence.
6. The Orchestrator returns transport evidence; it never marks a phase accepted.
7. `webactueel-workflow` reads the result, runs the phase audit/tests, repairs and retests when required, then decides `CONTINUE`, `REPLAN`, `BLOCK`, or — only after the global final audit — `COMPLETE`.
8. If another remote generation is required, the controller emits a new generation with the accepted checkpoint receipt.

## Fail-closed rules

- Never infer phase success from a green GitHub Action.
- Never let `generation` or `checkpoint_id` act as an acceptance decision by themselves.
- Never add domain audit/test policy to adapter config or transport workflows.
- Never broaden permissions for phase execution; least-privilege adapter permissions remain unchanged.
- Never continue a dependency wave without the controller-issued accepted dependency receipt already required by the schema.
- Never move customer/project truth, full conversation context, or full phase reasoning into transport payloads.

## Verification

`tests/test_phase_correlation_contract.py` locks this boundary: the transport schema must keep the stable generation/checkpoint/evidence fields needed for correlation while remaining free of controller-owned phase acceptance, audit and test policy.
