# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 2 | **Events**: 44

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

## Aggregate Events

- `AtomAuthorized`: 2
- `BudgetAllocated`: 2
- `CandidateAccepted`: 1
- `CostEvent`: 2
- `FailureNode`: 1
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
- `ToolReceiptAppended`: 10
- `WorkCapsuleBuilt`: 2
- `WorkerDispatchAuthorized`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:3afc40ea18d9ef050641cbffb8bed24f055d4eb2702140d03d5e5aff687f4ef1`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:0e1e2777c8d42fba757391e2e612bdb8f83d3343728388fa055aef1d28cc9b9a`
- authorization_head: `mu:aef2bf049cda3449e7d458000200762e2e95a265782cc7e3d2263c2d41ec8324`
- accepted_head: `mu:7d74eae536ba93a8c5fe14659893198a0ee7b7fbab0be9e31702631476a14732`
- events: `23`

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
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
- `market_accounting_correctness`: `PASS`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:f56417de037f SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:1931559086e2 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:c57e83515a67 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:aef2bf049cda WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:44b07d975fd8 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:678882fde149 MarketCreated [PRESERVE/PASS]
├── 6:PositionMinted:0174cfb96dd8 PositionMinted [PRESERVE/PASS]
├── 7:BudgetAllocated:b5ba8762d932 BudgetAllocated [PRESERVE/PASS]
├── 8:ToolReceiptAppended:f0d41dc46d9d ToolReceiptAppended [PRESERVE/PASS]
├── 9:ToolReceiptAppended:35d0f9e6c877 ToolReceiptAppended [PRESERVE/PASS]
├── 10:ToolReceiptAppended:e8a8487daf05 ToolReceiptAppended [PRESERVE/PASS]
├── 11:ToolReceiptAppended:382caaa7e5b0 ToolReceiptAppended [PRESERVE/PASS]
├── 12:ToolReceiptAppended:15ddae465c3c ToolReceiptAppended [PRESERVE/PASS]
├── 13:ToolReceiptAppended:bb874d7404cb ToolReceiptAppended [PRESERVE/PASS]
├── 14:WorkerReceiptImported:b6fca3707da5 WorkerReceiptImported [PRESERVE/PASS]
├── 15:MacroObservationImported:3630106c8e07 MacroObservationImported [PRESERVE/PASS]
├── 16:CostEvent:38a399a08c6c CostEvent [PRESERVE/PASS]
├── 17:OfficialEvaluatorEvidenceImported:ee8a56935ad8 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 18:CandidateAccepted:7d74eae536ba CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 19:MarketSettled:e29fbd069736 MarketSettled [PRESERVE/PASS] result=YES
├── 20:RewardDistributed:839ad70b1801 RewardDistributed [PRESERVE/PASS]
├── 21:PPUTAccounted:f8138672d69f PPUTAccounted [PRESERVE/PASS] progress=1
└── 22:PredicateEvaluated:0e1e2777c8d4 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:1931559086e2` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:44b07d975fd8` WorkCapsuleBuilt [PRESERVE/PASS]
3. `14:WorkerReceiptImported:b6fca3707da5` WorkerReceiptImported [PRESERVE/PASS]
4. `15:MacroObservationImported:3630106c8e07` MacroObservationImported [PRESERVE/PASS]
5. `17:OfficialEvaluatorEvidenceImported:ee8a56935ad8` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `18:CandidateAccepted:7d74eae536ba` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12050

- bundle hash: `sha256:8c66d2b84e6008590616505dffa4f7698e7b60f484da40c716d8cb2cc0a314a0`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:c455b24efa986c0bc0f61aaf75d3b97b52aab6f27e6738cc390afd66b2809cc7`
- authorization_head: `mu:6efe62b84bcb44a1b34c09052c642abe2b68485d723f0e80cef883a30877effb`
- accepted_head: `mu:f56417de037f597948e68398d84a241c32f2561fafff2ea4e28a9af2938134e1`
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
- `failed_progress_zero`: `PASS`
- `accepted_final_progress_one`: `PASS`
- `cost_conservation_all_branches`: `PASS`
- `vpput_accounting`: `PASS`
- `market_accounting_correctness`: `PASS`

#### Decision DAG

```
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:f56417de037f SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:cc0b2ea7e400 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:5066a93a4513 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:6efe62b84bcb WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:ee33dab496d5 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:1fa1bb5f9b14 MarketCreated [PRESERVE/PASS]
├── 6:PositionMinted:86675d30b2be PositionMinted [PRESERVE/PASS]
├── 7:BudgetAllocated:4b4efd249e8d BudgetAllocated [PRESERVE/PASS]
├── 8:ToolReceiptAppended:7877cf88c76a ToolReceiptAppended [PRESERVE/PASS]
├── 9:ToolReceiptAppended:1fb6650158f2 ToolReceiptAppended [PRESERVE/PASS]
├── 10:ToolReceiptAppended:8fe481b42485 ToolReceiptAppended [PRESERVE/PASS]
├── 11:ToolReceiptAppended:32aca58a6b60 ToolReceiptAppended [PRESERVE/PASS]
├── 12:WorkerReceiptImported:6a784271b7c3 WorkerReceiptImported [PRESERVE/PASS]
├── 13:MacroObservationImported:57d092811f9f MacroObservationImported [PRESERVE/PASS]
├── 14:CostEvent:f7d913baa820 CostEvent [PRESERVE/PASS]
├── 15:OfficialEvaluatorEvidenceImported:beebdcf046c6 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=PATCH_APPLIES_BUT_WRONG EVIDENCE
├── 16:FailureNode:4d9c67993967 FailureNode [PRESERVE/NOT_RUN] class=PATCH_APPLIES_BUT_WRONG ✗FAIL
├── 17:MarketSettled:58baebeb7fb4 MarketSettled [PRESERVE/PASS] result=NO
├── 18:RewardDistributed:6184e5fc8098 RewardDistributed [PRESERVE/PASS]
├── 19:PPUTAccounted:410a199ccb91 PPUTAccounted [PRESERVE/PASS] progress=0
└── 20:PredicateEvaluated:c455b24efa98 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._
