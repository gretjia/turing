# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 1 | **Events**: 29

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

- `AtomAuthorized`: 1
- `BroadcastRuleActivated`: 1
- `BudgetAllocated`: 2
- `CandidateAccepted`: 1
- `CostEvent`: 2
- `FailureCertificate`: 1
- `FailureNode`: 1
- `GoalStateProposed`: 1
- `MacroObservationImported`: 2
- `MarketCreated`: 1
- `MarketSettled`: 1
- `OfficialEvaluatorEvidenceImported`: 2
- `PPUTAccounted`: 2
- `PositionMinted`: 1
- `PredicateEvaluated`: 1
- `RetryAuthorized`: 1
- `RewardDistributed`: 1
- `SystemConstitutionAccepted`: 1
- `WorkCapsuleBuilt`: 2
- `WorkerDispatchAuthorized`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:df0ccc6df48c3ac87dac7d66f51ce029432828245df0077b8d84b798bd723155`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:ce5127cfa0db05fc596add77735ea411554c349d4c3d786921c22218086e2eab`
- authorization_head: `mu:0a6725e9fadbad11a449190e02a295d66b8fbacf26a00c32b213793427c7ca40`
- accepted_head: `mu:f17c61a1217408519a377288290c32702e56571264ee2da1c7f442d12695e9ae`
- events: `29`

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
├── 0:SystemConstitutionAccepted:5dfaa7c10e9b SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:00af30396d30 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:df89f972dd9f AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:514cf5e4c2dc WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:652503ab6dcf WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:f9031b1cc3fb MarketCreated [PRESERVE/PASS]
├── 6:PositionMinted:45c095fa233d PositionMinted [PRESERVE/PASS]
├── 7:BudgetAllocated:f1bc2aff9db9 BudgetAllocated [PRESERVE/PASS]
├── 8:WorkerReceiptImported:6702b5468fee WorkerReceiptImported [PRESERVE/PASS]
├── 9:MacroObservationImported:c807fc491ebb MacroObservationImported [PRESERVE/PASS]
├── 10:CostEvent:76fde0b78d37 CostEvent [PRESERVE/PASS]
├── 11:OfficialEvaluatorEvidenceImported:a80b2fdf3002 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 12:FailureNode:1a72efcf70b4 FailureNode [PRESERVE/NOT_RUN] class=OFFICIAL_EVAL_FAIL ✗FAIL
├── 13:PPUTAccounted:23d5a3bd1e20 PPUTAccounted [PRESERVE/PASS] progress=0
├── 14:FailureCertificate:af3ef021a8d5 FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 15:BroadcastRuleActivated:05687ad08300 BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 16:RetryAuthorized:3cc056d939a1 RetryAuthorized [ADVANCE/PASS]
├── 17:WorkerDispatchAuthorized:0a6725e9fadb WorkerDispatchAuthorized [ADVANCE/PASS]
├── 18:WorkCapsuleBuilt:95b51c51a080 WorkCapsuleBuilt [PRESERVE/PASS]
├── 19:BudgetAllocated:b9b4de70e8e3 BudgetAllocated [PRESERVE/PASS]
├── 20:WorkerReceiptImported:81dc93ebb5af WorkerReceiptImported [PRESERVE/PASS]
├── 21:MacroObservationImported:9d53b6344bd5 MacroObservationImported [PRESERVE/PASS]
├── 22:CostEvent:bf0f23968657 CostEvent [PRESERVE/PASS]
├── 23:OfficialEvaluatorEvidenceImported:c992e3b6304a OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 24:CandidateAccepted:f17c61a12174 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 25:MarketSettled:cc6425a8527a MarketSettled [PRESERVE/PASS] result=YES
├── 26:RewardDistributed:489ffbe27875 RewardDistributed [PRESERVE/PASS]
├── 27:PPUTAccounted:399e89bd6259 PPUTAccounted [PRESERVE/PASS] progress=1
└── 28:PredicateEvaluated:ce5127cfa0db PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:00af30396d30` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:652503ab6dcf` WorkCapsuleBuilt [PRESERVE/PASS]
3. `8:WorkerReceiptImported:6702b5468fee` WorkerReceiptImported [PRESERVE/PASS]
4. `9:MacroObservationImported:c807fc491ebb` MacroObservationImported [PRESERVE/PASS]
5. `11:OfficialEvaluatorEvidenceImported:a80b2fdf3002` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `18:WorkCapsuleBuilt:95b51c51a080` WorkCapsuleBuilt [PRESERVE/PASS]
7. `20:WorkerReceiptImported:81dc93ebb5af` WorkerReceiptImported [PRESERVE/PASS]
8. `21:MacroObservationImported:9d53b6344bd5` MacroObservationImported [PRESERVE/PASS]
9. `23:OfficialEvaluatorEvidenceImported:c992e3b6304a` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `24:CandidateAccepted:f17c61a12174` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
