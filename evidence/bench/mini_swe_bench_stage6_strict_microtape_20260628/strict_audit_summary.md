# Strict Audit Summary

Stage6 strict MicroTape qualification result: `PASS`.

This run generated two fresh SHA-256 Git MicroTape bundles:

- accepted path: `django__django-12039`
- failed path: `django__django-12050`

Strict gates passed:

- `overall`: `PASS`
- `replay_structural_integrity`: `PASS`
- `bundle_accessibility`: `PASS`
- `basic_ref_reconstruction`: `PASS`
- `git_topology`: `PASS`
- `canonical_payload_hash`: `PASS`
- `registry_head_effect`: `PASS`
- `accepted_head_authority`: `PASS`
- `authorization_head`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
- `economic_timing`: `PASS`
- `market_accounting_correctness`: `PASS`
- `constitutional_protocol_audit`: `PASS`

Aggregate event counts:

- `SystemConstitutionAccepted`: 2
- `GoalStateProposed`: 2
- `AtomAuthorized`: 2
- `WorkerDispatchAuthorized`: 2
- `WorkCapsuleBuilt`: 2
- `EvidenceBound`: 2
- `MarketCreated`: 2
- `PositionMinted`: 2
- `BudgetAllocated`: 2
- `WorkerReceiptImported`: 2
- `MacroObservationImported`: 2
- `CostEvent`: 2
- `PPUTAccounted`: 4
- `OfficialEvaluatorEvidenceImported`: 2
- `CandidateAccepted`: 1
- `FailureNode`: 1
- `MarketSettled`: 2
- `RewardDistributed`: 2
- `PredicateEvaluated`: 2

This directory is a protocol qualification fixture. It is not a benchmark
solve-rate claim and should not be mixed with the older Stage4/Stage5 legacy
bundles when running strict audit.
