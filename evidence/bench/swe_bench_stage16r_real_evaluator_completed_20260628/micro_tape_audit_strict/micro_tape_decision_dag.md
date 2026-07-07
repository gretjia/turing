# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 7 | **Events**: 215

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

- `AtomAuthorized`: 7
- `BudgetAllocated`: 7
- `CandidateAccepted`: 7
- `CostEvent`: 14
- `EvidenceBound`: 7
- `FailureCertificate`: 7
- `FailureNode`: 22
- `GoalStateProposed`: 7
- `MacroObservationImported`: 14
- `MarketCreated`: 7
- `MarketSettled`: 8
- `OfficialEvaluatorEvidenceImported`: 15
- `PPUTAccounted`: 15
- `PositionMinted`: 7
- `PredicateEvaluated`: 7
- `RetryAuthorized`: 7
- `RewardDistributed`: 8
- `SystemConstitutionAccepted`: 7
- `WorkCapsuleBuilt`: 14
- `WorkerDispatchAuthorized`: 14
- `WorkerReceiptImported`: 14

## Runs

### django__django-11790

- bundle hash: `sha256:59424e95caaeb76442c8c07de1d730e2d5744cd050e6c506abdd40a53774bc29`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:dcac7d852eb140ebdf2670becec4337bbf137c7bea425508003da7ff195d165f`
- authorization_head: `mu:682d30517bb6c1f8c41381b4c3af291d8173779cac9f3d6385d75da65976b1a2`
- accepted_head: `mu:bbf0eee588141f79b2b8533b76ba35c251280f340270f46203b414d927ad3547`
- events: `30`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:2728f7f83e59 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:4749e56b72fc AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:f22105d65f11 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:9ecd84aac097 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:8cb235a2689d WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:8bd8b5827444 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:36ee08abdec7 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:ac5ccf1346d5 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:6c67297af433 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:42b5813564b9 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:7ce1d02ae906 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:6ceb78d29878 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:682d30517bb6 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:cc5001a8e949 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:66c9e85c1c32 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:b75d35c587e0 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:cff7173e85d6 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:ac75311779f0 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:277df761e580 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:002d4024b103 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:d19c3b62b784 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:d19dc187a4e8 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:26745097ac93 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:736c63e408a1 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:b197e3d325d2 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:bbf0eee58814 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:446b465e7525 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:61bd2d34b4bd RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:dcac7d852eb1 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:2728f7f83e59` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:f22105d65f11` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:8cb235a2689d` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:8bd8b5827444` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:ac5ccf1346d5` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:6ceb78d29878` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:ac75311779f0` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:277df761e580` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:b197e3d325d2` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:bbf0eee58814` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11815

- bundle hash: `sha256:27fbcdc40022032a683754798565921dd2f9af39794f498dcb585e045d1cd1d8`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:6f826196a484ed4fe738aa7ca80caa79b7c19acd0d91e03002ee67f86673a950`
- authorization_head: `mu:4f5d419bd52e3e0f34f841aae1460de2787ad43adc1be828d10a638f39069088`
- accepted_head: `mu:ae8e6f9aa61106b530526f3809908c5007db63d0eef15b9fc326eed2515873ad`
- events: `30`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:96283b4c4e54 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:76aaeb344a4f AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:aba60707cd40 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:a0972d012d43 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:bdc85897245f WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:4b58dd502e7b MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:c49d7203b4de CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:b5b21d0314b8 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:c5cd85804868 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:9dab60dfb386 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:cba7f3357c96 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:bab886bf001e WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:4f5d419bd52e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:4b7828cb0691 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:c68970d1eaaa MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:382312412b4b PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:3d8855c75869 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:fe4f3b876aa6 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:c4f044f22ec1 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:864cb925af23 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:6da2018cf565 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:25947fd2b62a CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:f4929f8e30e4 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:60efdef70fd6 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:e4736d20b5b2 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:ae8e6f9aa611 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:d27c4779dd1b MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:a02769ae466f RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:6f826196a484 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:96283b4c4e54` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:aba60707cd40` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:bdc85897245f` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:4b58dd502e7b` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:b5b21d0314b8` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:bab886bf001e` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:fe4f3b876aa6` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:c4f044f22ec1` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:e4736d20b5b2` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:ae8e6f9aa611` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11964

- bundle hash: `sha256:a325a28c09edc6797d082ac03aa6f65abc97063536df2927872a6daf6632502b`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:ae0073cc1b310b00774b607bbcebcc5749946f54c4f108e50f84fd315c207fe3`
- authorization_head: `mu:7f62584f4523b26eb17e3e0599da51840c7fbde463d117867e653c9c27eec40d`
- accepted_head: `mu:409440313a742f956befa8f1bdd0c0468fe22f6db411473332664809f05d5711`
- events: `30`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:a6a9efd4269b GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:31d04d7c60de AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:15b24b623ac6 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:d6d0500acb9a WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:c5aa5a7ba1f6 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:75bf4c8d2464 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:1bfdf6ee9943 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:7547dbc8fca7 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:4bea594341c7 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:248b542ab1cf FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:39f9fd731423 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:c967a3a1d841 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:7f62584f4523 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:7d1c78fbff67 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:fe3ae196e715 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:b2d131091bbd PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:61f8ff7197e4 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:4b53f0262c2c WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:93ce45c2b0b4 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:8148fa1e2036 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:b0c6acd4c4f8 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:5625fb70f96a CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:b5eae907c050 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:4fc9d7fb5b53 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:2e2bc5f99a8f OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:409440313a74 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:7daaa35c83f2 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:15149378ec0d RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:ae0073cc1b31 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:a6a9efd4269b` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:15b24b623ac6` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:c5aa5a7ba1f6` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:75bf4c8d2464` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:7547dbc8fca7` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:c967a3a1d841` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:4b53f0262c2c` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:93ce45c2b0b4` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:2e2bc5f99a8f` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:409440313a74` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12209

- bundle hash: `sha256:e69134c054256eab5be8692ecc0e3ea664a2ce27e0373abc26100e0966325930`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:808a7d94cd040e44f63772f12e8e4faae2e7ce1144935b3ce350fbd69ed19e4c`
- authorization_head: `mu:c70b2da3f1a529f6d83e52c7d1c36faef27e356f982c27c8ef70f045adb3b143`
- accepted_head: `mu:7ea6c442771ed05d0144266871ab812c4a422078d66988195c3a20643b1ce2ab`
- events: `35`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:c74f9ebacec7 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:b4ac80ebe7c3 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:2f3268e90931 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:48a1a468d874 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:e3d7462811dc WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:9f6f6d8f6e41 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:d3abe2f6c9fe CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:a0dc013ffd1b OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:cbefa4669c87 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:3fa4bc6e6190 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:f6632f4ebe36 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:1db0b2c1aa90 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:c70b2da3f1a5 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:7bdc09262804 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:5edb55532d50 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:9519535fb800 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:9424e4d6030e BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:2df783594a82 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:0e9523582e42 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:b3277c714c40 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:b71f5d3fc272 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:631780e4f4ad CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:8a7ec1c95dc6 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:5d1f29ba00a8 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:5b4604e76140 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:b6a8ee420558 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:a218893de1f4 MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:814f968fd037 RewardDistributed [PRESERVE/PASS]
├── 29:PPUTAccounted:fcc4ce771096 PPUTAccounted [PRESERVE/PASS] progress=0
├── 30:OfficialEvaluatorEvidenceImported:90c90593cc8e OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 31:CandidateAccepted:7ea6c442771e CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 32:MarketSettled:28c7dc3e7841 MarketSettled [PRESERVE/PASS] result=YES
├── 33:RewardDistributed:361ed79ef187 RewardDistributed [PRESERVE/PASS]
└── 34:PPUTAccounted:808a7d94cd04 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:c74f9ebacec7` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:2f3268e90931` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:e3d7462811dc` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:9f6f6d8f6e41` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:a0dc013ffd1b` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:1db0b2c1aa90` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:2df783594a82` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:0e9523582e42` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:5b4604e76140` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `30:OfficialEvaluatorEvidenceImported:90c90593cc8e` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
11. `31:CandidateAccepted:7ea6c442771e` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12273

- bundle hash: `sha256:39ecee010981d699a2f80bfd6a657bf9d4ddfcd6c4eb3c4684005de5666aeefb`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:8be04948932f87c225338e4c0b22d0e4e68a91f873bb7aa1d50f79895e3e6799`
- authorization_head: `mu:0ed207758b716eda1024d76092a060b171d456643b0a4141d16d6d51b1406187`
- accepted_head: `mu:d2a4fe850b891285536199ae57fe6b6414c8d33056679be5715a1c2673d7516a`
- events: `30`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:3d7e34b05864 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:008682dfbbed AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:94ff28abf1a9 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:16077abd416c WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:d7495bac014f WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:a1c79a01b863 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:ca905da47ab0 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:c89be8ed0288 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:b5aa059b1fa0 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:95fc208bc3b8 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:8a168e68e507 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:d50c92224520 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:0ed207758b71 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:3fa31eeecb9d EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:3bce0472435e MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:7b3156e0f2f8 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:18c123fd744e BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:e62ce4d984bc WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:bce7c78c4106 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:cf6b54d003fc FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:c18c2253d087 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:3dcda0376483 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:a48ca75ff9d1 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:93e6532c83af PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:e3089fab0ea9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:d2a4fe850b89 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:704896c58647 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:00ab19a667b7 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:8be04948932f PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:3d7e34b05864` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:94ff28abf1a9` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:d7495bac014f` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:a1c79a01b863` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:c89be8ed0288` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:d50c92224520` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:e62ce4d984bc` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:bce7c78c4106` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:e3089fab0ea9` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:d2a4fe850b89` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12308

- bundle hash: `sha256:dceee84f68913c8ad1f16269fac032da4074efb2d4faa571d968d54809929523`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:54ee55ed94c39e3ca50e119b76dcdacb5ceeb4e214eb23cc03809ea822f7d8b3`
- authorization_head: `mu:4f47da61388eb268913feba922daa6b57f26141588e388090727d28985c6d7c1`
- accepted_head: `mu:8127b7d4f0f1168a1ac2c51954fc92a4391004c2a8c1045e89701c51a70cc531`
- events: `30`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:319bd61dc4dc GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:cde76054f5f6 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:c5e576ac5f11 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:b5d43370cd48 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:6204fb217f72 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:3a88b62da08b MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:e0cb0dfc3a02 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:5071132afc66 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:babc8a3a838a FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:5b15c29b4e3b FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:246114a9a353 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:407c25284a23 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:4f47da61388e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:8cd217f033b1 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:91345a9a35c7 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:538d5fec5927 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:74426c8fdd48 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:ee8ddebff121 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:555ff01fccb7 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:bf6dea8b1398 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:b60cf7e59872 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:02cd05aff010 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:048e2c198481 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:6e40bbfa30e7 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:066462dcdefb OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:8127b7d4f0f1 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:5ce414b7f1ee MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:1ff70e6833eb RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:54ee55ed94c3 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:319bd61dc4dc` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:c5e576ac5f11` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:6204fb217f72` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:3a88b62da08b` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:5071132afc66` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:407c25284a23` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:ee8ddebff121` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:555ff01fccb7` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:066462dcdefb` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:8127b7d4f0f1` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12325

- bundle hash: `sha256:dc7746e2244c59662bc764f0b4921ab88ae833953b284a81ecda135563350f48`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:86928f89ed4ca1a5e8f359e4765b139ebfa6b75a5d5aa98212987c266dd43c15`
- authorization_head: `mu:6e42e0ba6147a1d19c15dfbd676dec5d0874a649476fd9b3e4c830a7485888e2`
- accepted_head: `mu:c574981812c8ea0dd040a9eff17104f572b68447b0d3dc8ba1922642560b31f0`
- events: `30`

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
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:2a80fef7b0aa GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:f0fc3e3edbca AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:f2fa18c86b26 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:a96529de8445 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:d61cdfed8707 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:3e9d6daaa843 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:a4b48cde19b7 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:d915b5eeaaf0 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:be6eb7f05ffc FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:381c066c15a0 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:fc6e7f7cd7ea RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:2162150e31b8 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:6e42e0ba6147 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:9c1f39252237 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:a7a9dbf3f64b MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:bc3d0b1d07b9 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:afedd53d505c BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:857e30ab52ed WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:4324bc729d9b MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:fc564d5178c2 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:6a5af3d136a8 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:5c01db7e608d CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:5f9f64dfa985 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:1c436d0207fe PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:1ba4adb273f4 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:c574981812c8 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:ba4996b1b0c9 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:0463832aa274 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:86928f89ed4c PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:2a80fef7b0aa` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:f2fa18c86b26` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:d61cdfed8707` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:3e9d6daaa843` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:d915b5eeaaf0` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:2162150e31b8` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:857e30ab52ed` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:4324bc729d9b` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:1ba4adb273f4` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:c574981812c8` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
