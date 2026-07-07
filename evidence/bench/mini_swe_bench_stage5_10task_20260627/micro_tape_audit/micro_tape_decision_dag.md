# Micro Tape Independent Decision DAG Audit

**Verdict**: PARTIAL
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 2 | **Events**: 36

## Status Matrix

- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `accepted_head_authority`: `PASS`
- `economic_timing`: `WARN`
- `decision_dag_completeness`: `PASS`
- `market_accounting_correctness`: `WARN`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `WARN`
- `vpput_accounting`: `WARN`
- `bundle_accessibility`: `PASS`
- `basic_ref_reconstruction`: `PASS`
- `replay_structural_integrity`: `PASS`
- `constitutional_protocol_audit`: `PARTIAL`
- `overall`: `PARTIAL`

## Aggregate Events

- `BudgetAllocated`: 2
- `CandidateAccepted`: 2
- `CostEvent`: 2
- `EvidenceBound`: 2
- `FailureNode`: 4
- `GoalStateProposed`: 2
- `MacroObservationImported`: 2
- `MarketCreated`: 2
- `MarketSettled`: 2
- `OfficialEvaluatorEvidenceImported`: 2
- `PPUTAccounted`: 2
- `PositionMinted`: 2
- `PredicateEvaluated`: 2
- `RewardDistributed`: 2
- `SystemConstitutionAccepted`: 2
- `WorkCapsuleBuilt`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:de061d0204e987f779caebfc98b72941f3b7fe4d7f30a1cbf259426c863a3030`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:7a0726860fb58946a8f3731ae05754d77d6596c5b419f9926fea930d7313c224`
- authorization_head: `None`
- accepted_head: `mu:7a0726860fb58946a8f3731ae05754d77d6596c5b419f9926fea930d7313c224`
- events: `18`

#### Checks

- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `accepted_head_authority`: `PASS`
- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `economic_timing`: `WARN`
- `decision_dag_completeness`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `WARN`
- `vpput_accounting`: `WARN`
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:607b217245d6 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:951c810f27be WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:440b6e53920c EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:8e9be3191458 MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:4222bc192d75 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:bf2501106506 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:faa2351db3d1 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:a98a65bbb71e MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:1511c3fdb99c FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:69436d193105 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:c51f6c473fec MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:95601a49897c RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:22e47a6a7945 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:50e6feb09483 PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:4c1f9d58d9c3 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:8ed75647401e OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 17:CandidateAccepted:7a0726860fb5 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:607b217245d6` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:951c810f27be` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:faa2351db3d1` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:a98a65bbb71e` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:8ed75647401e` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:7a0726860fb5` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_without_terminal_market_settlement`: RewardDistributed must reference a terminal MarketSettled event.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-12050

- bundle hash: `sha256:6812ab9f027123474d50ce1ca964e36ca10f1f82d139919de0075f9d71b62a4e`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:c4509a8280817848b9d51cf2dd676aea2c02725d95de6b0b0b1a6e6069b5a4ad`
- authorization_head: `None`
- accepted_head: `mu:c4509a8280817848b9d51cf2dd676aea2c02725d95de6b0b0b1a6e6069b5a4ad`
- events: `18`

#### Checks

- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `accepted_head_authority`: `PASS`
- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `economic_timing`: `WARN`
- `decision_dag_completeness`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `WARN`
- `vpput_accounting`: `WARN`
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:14e4b2712370 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:1d3657bb4124 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:94287138205c EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:72820a31243f MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:160b9c771b85 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:15af614ceba8 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:899625a3f685 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:56c02057b5e6 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:3c0c7e7797f2 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:f17d9ab68b75 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:0a8e89384fe2 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:d0a52e191764 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:887d3feecbaa CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:4c130fc0ea68 PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:c38df2518506 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:74e426bb8fab OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 17:CandidateAccepted:c4509a828081 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:14e4b2712370` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:1d3657bb4124` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:899625a3f685` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:56c02057b5e6` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:74e426bb8fab` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:c4509a828081` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_without_terminal_market_settlement`: RewardDistributed must reference a terminal MarketSettled event.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.
