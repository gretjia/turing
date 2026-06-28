# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
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
- `EvidenceBound`: 2
- `FailureNode`: 1
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
- `WorkerDispatchAuthorized`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:ca2403fb61b85a523836769071d0b3b978b885d838f5129b40ebc4c2677c1117`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:e1b4f9702841d1a3136c969d96c066229711b5c88c7bb1f993cb008b872887c3`
- authorization_head: `mu:b5cf69202d069509683d49da030bda685b8995144d08d27e35eb395f8451a54f`
- accepted_head: `mu:bb014b761dc075f7bb54135e30d26e2946b014956c5d2bd9ffb808360b8dd2b4`
- events: `19`

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
├── 0:SystemConstitutionAccepted:26d3f112dca8 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:412a1b390ec9 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:0c50b7905045 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:b5cf69202d06 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:66ffb53d4df4 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:EvidenceBound:c05bf67dbfa8 EvidenceBound [PRESERVE/PASS]
├── 6:MarketCreated:2cb12ec3d5c1 MarketCreated [PRESERVE/PASS]
├── 7:PositionMinted:291e36c8b7be PositionMinted [PRESERVE/PASS]
├── 8:BudgetAllocated:4aab463f4e58 BudgetAllocated [PRESERVE/PASS]
├── 9:WorkerReceiptImported:e763086edd57 WorkerReceiptImported [PRESERVE/PASS]
├── 10:MacroObservationImported:3622a93b67a1 MacroObservationImported [PRESERVE/PASS]
├── 11:CostEvent:9e6061357292 CostEvent [PRESERVE/PASS]
├── 12:PPUTAccounted:02df7066e59d PPUTAccounted [PRESERVE/PASS] progress=0
├── 13:OfficialEvaluatorEvidenceImported:12a8866a8562 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 14:CandidateAccepted:bb014b761dc0 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 15:MarketSettled:ce288f67e67b MarketSettled [PRESERVE/PASS] result=YES
├── 16:RewardDistributed:cc039b6aaac2 RewardDistributed [PRESERVE/PASS]
├── 17:PPUTAccounted:9443bf4a345a PPUTAccounted [PRESERVE/PASS] progress=1
└── 18:PredicateEvaluated:e1b4f9702841 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:412a1b390ec9` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:66ffb53d4df4` WorkCapsuleBuilt [PRESERVE/PASS]
3. `9:WorkerReceiptImported:e763086edd57` WorkerReceiptImported [PRESERVE/PASS]
4. `10:MacroObservationImported:3622a93b67a1` MacroObservationImported [PRESERVE/PASS]
5. `13:OfficialEvaluatorEvidenceImported:12a8866a8562` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `14:CandidateAccepted:bb014b761dc0` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12050

- bundle hash: `sha256:9547af44a94381360bac7bd6cf953ddc056612d8c73769bcb04cc6afd71e5c02`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:b8640e9a8f88f25580dfcd19c3108d7750e44392712442393be2f919f69ed408`
- authorization_head: `mu:8f5f95cbfae5cc1f9a57e46f970e03bfcdb4f21642ba20d83c728e88a1e729d5`
- accepted_head: `mu:239e2085a1cb5b55b396d626583eaabcbd9461499440c2c4aee0527b7538e158`
- events: `19`

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
├── 0:SystemConstitutionAccepted:239e2085a1cb SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:5d6a87607b06 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:0e1333f48834 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:8f5f95cbfae5 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:4b8f169ea1ba WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:EvidenceBound:182c849ec9a4 EvidenceBound [PRESERVE/PASS]
├── 6:MarketCreated:f28b6c7c7cdd MarketCreated [PRESERVE/PASS]
├── 7:PositionMinted:cea890219947 PositionMinted [PRESERVE/PASS]
├── 8:BudgetAllocated:fb9c23ab85e6 BudgetAllocated [PRESERVE/PASS]
├── 9:WorkerReceiptImported:a79d5fe6be59 WorkerReceiptImported [PRESERVE/PASS]
├── 10:MacroObservationImported:8fea337b343c MacroObservationImported [PRESERVE/PASS]
├── 11:CostEvent:2bfeee4e7081 CostEvent [PRESERVE/PASS]
├── 12:PPUTAccounted:c38970d089f6 PPUTAccounted [PRESERVE/PASS] progress=0
├── 13:OfficialEvaluatorEvidenceImported:c1ed45de3e7e OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 14:FailureNode:5fb1ad0315cd FailureNode [PRESERVE/FAIL] class=OFFICIAL_EVAL_FAIL ✗FAIL
├── 15:MarketSettled:5a987810dd20 MarketSettled [PRESERVE/PASS] result=NO
├── 16:RewardDistributed:e6c26ecaf072 RewardDistributed [PRESERVE/PASS]
├── 17:PPUTAccounted:47d6d029bf5c PPUTAccounted [PRESERVE/PASS] progress=0
└── 18:PredicateEvaluated:b8640e9a8f88 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._
