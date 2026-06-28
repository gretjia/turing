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
- `BudgetAllocated`: 2
- `CandidateAccepted`: 1
- `CostEvent`: 2
- `EvidenceBound`: 1
- `FailureNode`: 1
- `GoalStateProposed`: 1
- `MacroObservationImported`: 2
- `MarketCreated`: 1
- `MarketPriceBroadcast`: 1
- `MarketSettled`: 1
- `OfficialEvaluatorEvidenceImported`: 2
- `PPUTAccounted`: 2
- `PositionMinted`: 2
- `RewardDistributed`: 2
- `SystemConstitutionAccepted`: 1
- `WorkCapsuleBuilt`: 2
- `WorkerDispatchAuthorized`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-11790

- bundle hash: `sha256:bdb1138b4f253b0b723b64aa31ec9b1e0295e6f5ad434c469ed71bc2397c4f01`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:828db8c9f5b37f83d78bfd8aa19c12aaf6323a7a6370cc08bed6ae535e422ead`
- authorization_head: `mu:c10d90adadc2e81dfe8930a868b6536fdf708e0b89343b0a37ed7edc60216f98`
- accepted_head: `mu:e07a2c56b0758fb9df1fb70ef2083dec1cfc9bcc5164cffa7e4e9d9b57f40448`
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
├── 0:SystemConstitutionAccepted:519a0038ac45 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:8f2419235987 GoalStateProposed [PRESERVE/PASS]
├── 2:MarketCreated:03bb52ba1289 MarketCreated [PRESERVE/PASS]
├── 3:EvidenceBound:8fc7e9dae47f EvidenceBound [PRESERVE/PASS]
├── 4:MarketPriceBroadcast:5c4b54212d6f MarketPriceBroadcast [PRESERVE/PASS]
├── 5:AtomAuthorized:c806fc92a3aa AtomAuthorized [ADVANCE/PASS]
├── 6:WorkerDispatchAuthorized:29d9ab431583 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 7:BudgetAllocated:e1cacfe5fb72 BudgetAllocated [PRESERVE/PASS]
├── 8:PositionMinted:b75104fdb70e PositionMinted [PRESERVE/PASS]
├── 9:WorkCapsuleBuilt:0c8d190a1fd4 WorkCapsuleBuilt [PRESERVE/PASS]
├── 10:WorkerDispatchAuthorized:c10d90adadc2 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 11:BudgetAllocated:93f5fa350475 BudgetAllocated [PRESERVE/PASS]
├── 12:PositionMinted:2782b784e1b4 PositionMinted [PRESERVE/PASS]
├── 13:WorkCapsuleBuilt:13e57de60355 WorkCapsuleBuilt [PRESERVE/PASS]
├── 14:WorkerReceiptImported:e04fdf9d98ee WorkerReceiptImported [PRESERVE/PASS]
├── 15:MacroObservationImported:4f88a4c17661 MacroObservationImported [PRESERVE/PASS]
├── 16:CostEvent:1d7d2672cb14 CostEvent [PRESERVE/PASS]
├── 17:OfficialEvaluatorEvidenceImported:13fff6fc0ed9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=SEMANTIC_FAIL EVIDENCE
├── 18:FailureNode:b63139c5062f FailureNode [PRESERVE/NOT_RUN] class=SEMANTIC_FAIL ✗FAIL
├── 19:PPUTAccounted:63009075efcf PPUTAccounted [PRESERVE/PASS] progress=0
├── 20:WorkerReceiptImported:68b863d86207 WorkerReceiptImported [PRESERVE/PASS]
├── 21:MacroObservationImported:14bfe834d6a3 MacroObservationImported [PRESERVE/PASS]
├── 22:CostEvent:f04ec234cdfa CostEvent [PRESERVE/PASS]
├── 23:OfficialEvaluatorEvidenceImported:0b42b9cb6a48 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 24:CandidateAccepted:e07a2c56b075 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 25:MarketSettled:11f21b3a36da MarketSettled [PRESERVE/PASS] result=YES
├── 26:RewardDistributed:1c6bcc57b11f RewardDistributed [PRESERVE/PASS]
├── 27:RewardDistributed:1d7d2aabde7e RewardDistributed [PRESERVE/PASS]
└── 28:PPUTAccounted:828db8c9f5b3 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:8f2419235987` GoalStateProposed [PRESERVE/PASS]
2. `9:WorkCapsuleBuilt:0c8d190a1fd4` WorkCapsuleBuilt [PRESERVE/PASS]
3. `13:WorkCapsuleBuilt:13e57de60355` WorkCapsuleBuilt [PRESERVE/PASS]
4. `14:WorkerReceiptImported:e04fdf9d98ee` WorkerReceiptImported [PRESERVE/PASS]
5. `15:MacroObservationImported:4f88a4c17661` MacroObservationImported [PRESERVE/PASS]
6. `17:OfficialEvaluatorEvidenceImported:13fff6fc0ed9` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `20:WorkerReceiptImported:68b863d86207` WorkerReceiptImported [PRESERVE/PASS]
8. `21:MacroObservationImported:14bfe834d6a3` MacroObservationImported [PRESERVE/PASS]
9. `23:OfficialEvaluatorEvidenceImported:0b42b9cb6a48` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `24:CandidateAccepted:e07a2c56b075` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
