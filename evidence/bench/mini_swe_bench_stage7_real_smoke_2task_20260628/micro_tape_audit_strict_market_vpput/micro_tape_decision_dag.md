# Micro Tape Independent Decision DAG Audit

**Verdict**: PARTIAL
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 2 | **Events**: 38

## Status Matrix

- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `accepted_head_authority`: `PASS`
- `economic_timing`: `PASS`
- `decision_dag_completeness`: `PASS`
- `market_accounting_correctness`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
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
- `PPUTAccounted`: 4
- `PositionMinted`: 2
- `PredicateEvaluated`: 2
- `RewardDistributed`: 2
- `SystemConstitutionAccepted`: 2
- `WorkCapsuleBuilt`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:ac2a4796c55819c2bd1b333c0a07523e6bb9176d7ff9ffbe2179020d1a7637ca`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:7b09856fcb02fd6fbb3556e3a5d9c245510e1962fccf9acd5a6a70384a728b76`
- authorization_head: `None`
- accepted_head: `mu:7b2cee6f3227174ccf5e45495b49cd3b66afd67245328814efb9bab5d83e56c5`
- events: `19`

#### Checks

- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `accepted_head_authority`: `PASS`
- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `economic_timing`: `PASS`
- `decision_dag_completeness`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
- `market_accounting_correctness`: `PASS`

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
├── 7:WorkerReceiptImported:a175b0e7f3ac WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:d1e09f3dc1eb MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:47811fe04b26 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:a738b3f7b1c4 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:CostEvent:67923f07cdf9 CostEvent [PRESERVE/PASS]
├── 12:PPUTAccounted:f6dfac8ac1e4 PPUTAccounted [PRESERVE/PASS] progress=0
├── 13:PredicateEvaluated:cd957c56b832 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 14:OfficialEvaluatorEvidenceImported:5a074a92b1cf OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 15:CandidateAccepted:7b2cee6f3227 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 16:MarketSettled:2643fc6fc1eb MarketSettled [PRESERVE/PASS] result=YES
├── 17:RewardDistributed:e7c0174c5bae RewardDistributed [PRESERVE/PASS]
└── 18:PPUTAccounted:7b09856fcb02 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:607b217245d6` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:951c810f27be` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:a175b0e7f3ac` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:d1e09f3dc1eb` MacroObservationImported [PRESERVE/PASS]
5. `14:OfficialEvaluatorEvidenceImported:5a074a92b1cf` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `15:CandidateAccepted:7b2cee6f3227` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12050

- bundle hash: `sha256:1c12804ecbf77b906049c595ddc2e79ec1348228b6b3ebf9e87035e348f98647`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:af29bd1d5ec8debbf9aa7c769328d55e794ee9330af11f9c7fb5fda5f4dcbcf5`
- authorization_head: `None`
- accepted_head: `mu:81329296f4188f2f937b62d90593c1a5c4ec3d35e0572981173838b87646e95e`
- events: `19`

#### Checks

- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `LEGACY_MISSING`
- `accepted_head_authority`: `PASS`
- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `economic_timing`: `PASS`
- `decision_dag_completeness`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
- `market_accounting_correctness`: `PASS`

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
├── 7:WorkerReceiptImported:d4a2fa92c192 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:8ca0cf4f53de MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:733193a2e274 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:34a322f7a4e0 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:CostEvent:f99c80cff5e8 CostEvent [PRESERVE/PASS]
├── 12:PPUTAccounted:f203867e380b PPUTAccounted [PRESERVE/PASS] progress=0
├── 13:PredicateEvaluated:dabbaecab7fb PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 14:OfficialEvaluatorEvidenceImported:494e6b7718a9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 15:CandidateAccepted:81329296f418 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 16:MarketSettled:8ec9d137feb9 MarketSettled [PRESERVE/PASS] result=YES
├── 17:RewardDistributed:460ef17d5497 RewardDistributed [PRESERVE/PASS]
└── 18:PPUTAccounted:af29bd1d5ec8 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:14e4b2712370` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:1d3657bb4124` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:d4a2fa92c192` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:8ca0cf4f53de` MacroObservationImported [PRESERVE/PASS]
5. `14:OfficialEvaluatorEvidenceImported:494e6b7718a9` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `15:CandidateAccepted:81329296f418` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
