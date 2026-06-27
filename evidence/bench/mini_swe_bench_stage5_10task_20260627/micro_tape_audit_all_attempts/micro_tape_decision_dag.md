# Micro Tape Independent Decision DAG Audit

**Verdict**: PARTIAL
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 11 | **Events**: 212

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
- `bundle_accessibility`: `PASS`
- `basic_ref_reconstruction`: `PASS`
- `replay_structural_integrity`: `PASS`
- `constitutional_protocol_audit`: `PARTIAL`
- `overall`: `PARTIAL`

## Aggregate Events

- `BudgetAllocated`: 11
- `CandidateAccepted`: 16
- `CostEvent`: 11
- `EvidenceBound`: 11
- `FailureNode`: 24
- `GoalStateProposed`: 11
- `MacroObservationImported`: 11
- `MarketCreated`: 11
- `MarketSettled`: 11
- `OfficialEvaluatorEvidenceImported`: 18
- `PPUTAccounted`: 11
- `PositionMinted`: 11
- `PredicateEvaluated`: 11
- `RewardDistributed`: 11
- `SystemConstitutionAccepted`: 11
- `WorkCapsuleBuilt`: 11
- `WorkerReceiptImported`: 11

## Runs

### django__django-11964

- bundle hash: `sha256:804c33c9000bd412052aa4e003d6f4fb6740d74cf35a7b62802e6c6798bd94a7`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:cba842066ce0c29649cf95e8aeefc2ecfe61653006cd83d04819196a2acf5945`
- authorization_head: `None`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:a6a9efd4269b GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:e3e0c44fdd87 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:155bfb9b2af5 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:157ec185aca3 MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:9a35e3433595 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:85f28462ebb3 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:2a057797b213 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:c30f7c9fc1de MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:67072ee8b620 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:cca4d24a1c02 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:95d15f0d3923 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:64e3bc579012 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:5561a61185cb CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:1a77f0d82dc2 PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:78bd2577947b PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:a20c03d7a711 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
└── 17:FailureNode:cba842066ce0 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

#### Execution Findings

- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.

### django__django-11790

- bundle hash: `sha256:b1415dab11f9856d8e2ef7ba9c4067a103c3cdf672bafc0eda0d83aee13c9f4c`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:457f67e58114de1e1eed41c7279b358996b2e62535da08ea5acbe08d02d34872`
- authorization_head: `None`
- accepted_head: `mu:457f67e58114de1e1eed41c7279b358996b2e62535da08ea5acbe08d02d34872`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:2728f7f83e59 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:d8b6a2610dbb WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:095e57c38fd9 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:275bcf7fa27f MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:26a98a2d57e0 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:246d23c8f98f BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:12bd9df615bb WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:cfabf497aec0 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:6cc897aa65a8 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:2ff6a4881afb FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:f3933e8920b5 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:1d66381a1c3a RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:ffdd8d4ea6ae CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:e5a3f1c9aa68 PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:b5790b108eed PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:3cfcee4c1011 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:0872475fd7b5 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:778fb92cbcc3 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:457f67e58114 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:2728f7f83e59` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:d8b6a2610dbb` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:12bd9df615bb` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:cfabf497aec0` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:3cfcee4c1011` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:0872475fd7b5` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-11815

- bundle hash: `sha256:f488034f71fdcfbaf7f0225ef651c225f855fe4d6b83a300038c9c6e55a14fb2`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:53dd6e3b01302885a6f3d36879f5e641867f13bd20a58cb61fce1eb528d973c5`
- authorization_head: `None`
- accepted_head: `mu:53dd6e3b01302885a6f3d36879f5e641867f13bd20a58cb61fce1eb528d973c5`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:96283b4c4e54 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:1c48a3344914 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:182e89c55094 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:ec5b05c6853c MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:ea917bc3e12f PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:e368be6b0206 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:dcdb6d5b8ba7 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:b5666e8f4c7a MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:b68a3a89bfec FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:52bce5b5fc55 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:3b05ee0fc578 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:29b62fcb3dc1 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:c4a2dc99bdc6 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:e2c02f0ad156 PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:7f65e1ee8082 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:8979da6dee14 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:0572e7664adf CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:419258a556a4 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:53dd6e3b0130 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:96283b4c4e54` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:1c48a3344914` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:dcdb6d5b8ba7` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:b5666e8f4c7a` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:8979da6dee14` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:0572e7664adf` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-11848

- bundle hash: `sha256:2da0fe316b55ef6c99a9ac9b2e61b26837766e4bdd88507c325d42fc806e3375`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:671e0e609c7e8be3a37ef76720cbdc3b249f1c0d9e538c02c4a107b2a9bf1b40`
- authorization_head: `None`
- accepted_head: `mu:671e0e609c7e8be3a37ef76720cbdc3b249f1c0d9e538c02c4a107b2a9bf1b40`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:6c9873b8d444 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:e48c8e69a901 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:54a82240b3a0 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:0e873b2e2864 MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:a9fadaf73b7d PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:b26c7222a0cb BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:5d0a8971f249 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:b8652355df70 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:d8351ed9ee65 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:1d82a27b86a0 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:bea220e870ef MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:b72455da6550 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:42e8dcd008d8 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:fec38caff5be PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:a6c419809ef9 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:4a5c904e23d6 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:2ef469a37300 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:a8106ef07897 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:671e0e609c7e CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:6c9873b8d444` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:e48c8e69a901` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:5d0a8971f249` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:b8652355df70` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:4a5c904e23d6` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:2ef469a37300` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-11880

- bundle hash: `sha256:a6d1844e079b38fdf153f67c5b299024317d7d5d3ce2691828763b68aa2a60da`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:0d0478b8165f80e41cedb4c43d58761ef0a7ab0d791a517cc932126b3d842fe7`
- authorization_head: `None`
- accepted_head: `mu:0d0478b8165f80e41cedb4c43d58761ef0a7ab0d791a517cc932126b3d842fe7`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:1ee0a0c05a05 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:0c6ee5c4ea17 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:5adfaaa49b6e EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:ef1f44b6d215 MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:7fc4e2d94327 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:a86ad0606b3b BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:81a8634f80e3 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:28ed9ce03091 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:a468b058c947 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:607d3fc522c3 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:8318356e5035 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:70f7ff861663 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:891ea1a9f45d CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:8e473c71387c PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:b4b714dbab91 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:d5e037e30b31 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:bcc46b686c80 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:17398d1f4b0b OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:0d0478b8165f CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:1ee0a0c05a05` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:0c6ee5c4ea17` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:81a8634f80e3` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:28ed9ce03091` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:d5e037e30b31` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:bcc46b686c80` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-11885

- bundle hash: `sha256:6205209c0ed89c660bbfa42fcae88dc6ff1e3eb120eb0a373c4b45bdb6c4d3e2`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:3eb5b63787b0633ef86982c46717a9fb421df5954e458cd30d6d476d3226a4a7`
- authorization_head: `None`
- accepted_head: `mu:3eb5b63787b0633ef86982c46717a9fb421df5954e458cd30d6d476d3226a4a7`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:321414a5156f GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:cf3b24c06198 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:1ea75628e64b EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:8f60a09a5efa MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:ba504496df4b PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:ac6bb868caa2 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:b477a5458fb7 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:3e11c55b16a3 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:3f31e9a98ddf FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:1f274842ad79 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:a36c7b988920 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:74afd3e5a759 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:f9ab259b04c6 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:0fe3b580a0f6 PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:3e8e6e419b63 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:ffbdd3a34a35 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:822619053b6a CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:a9431590b3f5 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:3eb5b63787b0 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:321414a5156f` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:cf3b24c06198` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:b477a5458fb7` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:3e11c55b16a3` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:ffbdd3a34a35` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:822619053b6a` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-11951

- bundle hash: `sha256:4a9f6b5bc30b6d36920c46781ed603ecc8d258767365c39bfc7c4fc3986cc01e`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:18b58be6277b801fc63910c524ce08721af3d30c9ec99019413c88249039f42b`
- authorization_head: `None`
- accepted_head: `mu:18b58be6277b801fc63910c524ce08721af3d30c9ec99019413c88249039f42b`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:faa6914fa863 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:83f6cea0b5ee WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:f141f28537b9 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:c1a1ce45ae1d MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:ea43b6249fe0 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:212dc2c3a7d1 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:89d90d2661e2 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:e86378031c8c MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:65ada2e27d3f FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:c0ffe3b96d3b FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:893b95bb495a MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:7ea66312fa85 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:c6dc23d3ffbc CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:7b2fe2c34f4e PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:dcfe274ae415 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:34a511ee4e87 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:d5a97b4f1e76 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:c40ced7c7142 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:18b58be6277b CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:faa6914fa863` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:83f6cea0b5ee` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:89d90d2661e2` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:e86378031c8c` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:34a511ee4e87` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:d5a97b4f1e76` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

### django__django-11964

- bundle hash: `sha256:4433df9680286f48cd1d56384c4d579ce492b2f9752feb801a096f77dd087853`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:a616e84ae23b4aa06a1d9e801f45389190c489663d5fcff5f182968046291ba5`
- authorization_head: `None`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:a6a9efd4269b GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:e3e0c44fdd87 WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:155bfb9b2af5 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:157ec185aca3 MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:9a35e3433595 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:85f28462ebb3 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:f07b07495208 WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:cc94fda25741 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:79cdf5ad4ee3 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:9e8cd9db2a72 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:198f3c4bf23e MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:c00e3de488ef RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:2fdf0b7661a6 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:ed5e34c09d5e PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:884c1dddf0d2 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:ffa964d74b53 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
└── 17:FailureNode:a616e84ae23b FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

#### Execution Findings

- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.

### django__django-11999

- bundle hash: `sha256:c6f7fa5115749fc1e28c9ba32400baa44eb8d584fcbb69d670383d478a70011b`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:33f5b532bc6a8ce690b0b6459812991946b8ca9f5a62235efad1a71e46c25a0e`
- authorization_head: `None`
- accepted_head: `mu:33f5b532bc6a8ce690b0b6459812991946b8ca9f5a62235efad1a71e46c25a0e`
- events: `20`

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
- `market_accounting_correctness`: `WARN`

#### Decision DAG

```
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:64f92087ebf4 GoalStateProposed [PRESERVE/PASS]
├── 2:WorkCapsuleBuilt:32556f4fa43c WorkCapsuleBuilt [PRESERVE/PASS]
├── 3:EvidenceBound:ba3ded176771 EvidenceBound [PRESERVE/PASS]
├── 4:MarketCreated:fba630e6c076 MarketCreated [PRESERVE/PASS]
├── 5:PositionMinted:efd6ceb22316 PositionMinted [PRESERVE/PASS]
├── 6:BudgetAllocated:e0c48cdf1957 BudgetAllocated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:1326a83ae58b WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:0aa04be864a4 MacroObservationImported [PRESERVE/PASS]
├── 9:FailureNode:93f374fa512b FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureNode:13cdd20cddeb FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 11:MarketSettled:a05a561c3552 MarketSettled [PRESERVE/PASS] result=NO
├── 12:RewardDistributed:c61a0f3d2cd9 RewardDistributed [PRESERVE/PASS]
├── 13:CostEvent:7307a8b81016 CostEvent [PRESERVE/PASS]
├── 14:PPUTAccounted:60147dca529d PPUTAccounted [PRESERVE/PASS] progress=0
├── 15:PredicateEvaluated:dcf23b8ca7e7 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 16:OfficialEvaluatorEvidenceImported:15b83af47e3a OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:0db537d38d44 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:OfficialEvaluatorEvidenceImported:5546dc80de8d OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
└── 19:CandidateAccepted:33f5b532bc6a CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
```

#### Accepted Path

1. `1:GoalStateProposed:64f92087ebf4` GoalStateProposed [PRESERVE/PASS]
2. `2:WorkCapsuleBuilt:32556f4fa43c` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:1326a83ae58b` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:0aa04be864a4` MacroObservationImported [PRESERVE/PASS]
5. `16:OfficialEvaluatorEvidenceImported:15b83af47e3a` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `17:CandidateAccepted:0db537d38d44` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_terminal_evidence`: MarketSettled is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `reward_distributed_before_terminal_market_basis`: RewardDistributed is replayable and preserve-only, but it occurred before terminal official evidence.
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.

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
- **WARN** `pput_final_accounting_missing_after_accept`: Accepted run has no post-accept final PPUTAccounted progress=1 event.
