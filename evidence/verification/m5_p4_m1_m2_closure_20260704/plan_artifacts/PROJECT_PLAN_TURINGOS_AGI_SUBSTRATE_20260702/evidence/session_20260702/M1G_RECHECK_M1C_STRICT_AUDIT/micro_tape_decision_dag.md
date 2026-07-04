# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 1 | **Events**: 21

## Status Matrix

- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `PASS`
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
- `constitutional_protocol_audit`: `PASS`
- `overall`: `PASS`
- `cost_provenance`: `PASS`
- `sandbox_provenance`: `PASS`

## Aggregate Events

- `AtomAuthorized`: 1
- `BudgetAllocated`: 1
- `CandidateAccepted`: 1
- `CostEvent`: 1
- `EvidenceBound`: 1
- `FailureNode`: 2
- `GoalStateProposed`: 1
- `MacroObservationImported`: 1
- `MarketCreated`: 1
- `MarketSettled`: 1
- `OfficialEvaluatorEvidenceImported`: 1
- `PPUTAccounted`: 2
- `PositionMinted`: 1
- `PredicateEvaluated`: 1
- `RewardDistributed`: 1
- `SystemConstitutionAccepted`: 1
- `WorkCapsuleBuilt`: 1
- `WorkerDispatchAuthorized`: 1
- `WorkerReceiptImported`: 1

## Runs

### django__django-12039

- bundle hash: `sha256:491ce5d7d61c99ea69ef56720988deac59736a59d800b129845c814bad2735da`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:8fb6c3ebdfabcca3a0d3e33ff8fd6afca378b167f51a6b6a439cc9a40240a987`
- authorization_head: `mu:88f79155708e8ad097309b10e9de4f8bcdedca58376990164d4ed7b99edf46e9`
- accepted_head: `mu:a555746fea63ffb0bdb5d0d63f01118864fd3d8c7af3a051a08cce8d8abd2019`
- events: `21`

#### Checks

- `canonical_payload_hash`: `PASS`
- `ref_reconstruction`: `PASS`
- `registry_head_effect`: `PASS`
- `authorization_head`: `PASS`
- `accepted_head_authority`: `PASS`
- `bundle_integrity`: `PASS`
- `git_topology`: `PASS`
- `economic_timing`: `PASS`
- `decision_dag_completeness`: `PASS`
- `terminal_golden_path_anchors_to_accepted_head`: `PASS`
- `cost_provenance`: `PASS`
- `sandbox_provenance`: `PASS`
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
├── 2:AtomAuthorized:5b020faa5ff3 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:e6d987ee7640 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:88f79155708e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:EvidenceBound:280203959318 EvidenceBound [PRESERVE/PASS]
├── 6:MarketCreated:a8c26f148705 MarketCreated [PRESERVE/PASS]
├── 7:PositionMinted:e85e78837517 PositionMinted [PRESERVE/PASS]
├── 8:BudgetAllocated:10647362cb68 BudgetAllocated [PRESERVE/PASS]
├── 9:WorkerReceiptImported:eb23b05839a1 WorkerReceiptImported [PRESERVE/PASS]
├── 10:MacroObservationImported:28f688d76826 MacroObservationImported [PRESERVE/PASS]
├── 11:FailureNode:eca6f7dd1048 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 12:FailureNode:18478e757eca FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 13:CostEvent:070994154147 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:bb539fc2fe3c PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:6334dc3bc9af PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:103d82fed4c9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:a555746fea63 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:b6491ff0f8f3 MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:8e8ffd5d0fbd RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:8fb6c3ebdfab PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:607b217245d6` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:e6d987ee7640` WorkCapsuleBuilt [PRESERVE/PASS]
3. `9:WorkerReceiptImported:eb23b05839a1` WorkerReceiptImported [PRESERVE/PASS]
4. `10:MacroObservationImported:28f688d76826` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:103d82fed4c9` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:a555746fea63` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
