# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 20 | **Events**: 600

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

- `AtomAuthorized`: 20
- `BudgetAllocated`: 20
- `CandidateAccepted`: 13
- `CostEvent`: 40
- `EvidenceBound`: 20
- `FailureCertificate`: 20
- `FailureNode`: 67
- `GoalStateProposed`: 20
- `MacroObservationImported`: 40
- `MarketCreated`: 20
- `MarketSettled`: 20
- `OfficialEvaluatorEvidenceImported`: 40
- `PPUTAccounted`: 40
- `PositionMinted`: 20
- `PredicateEvaluated`: 20
- `RetryAuthorized`: 20
- `RewardDistributed`: 20
- `SystemConstitutionAccepted`: 20
- `WorkCapsuleBuilt`: 40
- `WorkerDispatchAuthorized`: 40
- `WorkerReceiptImported`: 40

## Runs

### django__django-11790

- bundle hash: `sha256:ed0e3eafcc8224ddf8416efa141b25d9cf10cacadca90d1d546ce377e222e70c`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:2f9e2832a2490d5f09455b848423c0600fda1e0959df63d93c60f95c6fad74eb`
- authorization_head: `mu:e95b18efaa3cb906456aad3afffaa722e28b53d4a0684b1cc47d0a95861bfe73`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:2728f7f83e59 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:cdc2daa2b608 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:0c1e46346b6a WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:29e6b5f984b3 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:2dc99655998a WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:c5ec15ada599 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:1ba5a6d79c95 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:7a6aa65e12fa OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:c047eab1296f FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:f945d97a6b90 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:19d6d8dc8909 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:56d5e470458d WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:e95b18efaa3c WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:36b2e4d71319 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:ba32f589dba1 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:3ff9dedea07f PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:d9e2af12c174 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:0995949c105d WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:b056cbee739a MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:eacc170e77b6 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:fcc7abb420dd FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:52c0ec51b039 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:d3d9708bec58 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:7bffe7776db4 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:9d05f7691eac OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:c331577034ea FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:ed358ec9802b MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:1ff6d68f1114 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:2f9e2832a249 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-11815

- bundle hash: `sha256:003b61a4e135bcdcba0173e9925fbb6fd7c55da62a427a835371a871923e0dcb`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:a71f848b48900205c89a9baba9b6852c9a92f96f875213c6ed0c7abf9532ff89`
- authorization_head: `mu:b7861838649648a110a713859fe5030bbb453e6659991e41f6cc59282db3e17e`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:96283b4c4e54 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:c8aff8a59265 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:7b14a8f79201 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:df26d161b78e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:a2805cd5ca89 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:d0a21b3203f5 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:9cda40436a36 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:cbe8e9910206 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:10896395c420 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:f6ba41d0b45c FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:751c84ee5781 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:cab348f1db2c WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:b78618386496 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:61158a955758 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:da9624ecbcb3 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:af7d37c1177e PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:dba83566d2a5 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:985ea2725a5d WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:4f9e3e520283 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:4ad40983a059 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:e96d8854b3dd FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:71bcbdd57a74 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:67d9e464a49f PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:6f1ef8d613fc PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:66e9ed4ae810 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:94a743bd033e FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:c2deb2d68abb MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:24a4287a190f RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:a71f848b4890 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-11848

- bundle hash: `sha256:dc9d2ea3ff5386e7d693753609f2d25501ca253d26e78e2450470067a3f94833`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:349bc7177791ab561eb7245c2e62cbde5080fe007ac093536ef0bfad19af6295`
- authorization_head: `mu:9e178f3ad83e1a7f99e962ebb988a98297cd1fad332e0684fe191fa18c67f565`
- accepted_head: `mu:abe46a9222b777eeaafc8006fee4a5bfd68c9e78d0a2902eab1809fd094e16b4`
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
├── 1:GoalStateProposed:6c9873b8d444 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:513d66193043 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:8334409ce7cd WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:bd5e532ee2a1 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:1a51620f95e3 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:e8dca1e690b5 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:787eafc690ab CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:8cc18bb39fdd OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:95391f6afcf0 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:1fce9d88b817 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:adb7383b4b1d RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:8de0f1773253 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:9e178f3ad83e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:19f33406a47d EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:d117ab81c737 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:05d608b04e49 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:40e922cf3406 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:6b2bd72c232d WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:383eeda5c852 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:f76bb1559efb FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:6f14e3b1f858 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:88058fee1b3a CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:3eac5863fda3 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:1405b12d4da7 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:7b57f886a980 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:abe46a9222b7 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:62c53d302e08 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:3d43313b91d7 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:349bc7177791 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:6c9873b8d444` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:8334409ce7cd` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:1a51620f95e3` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:e8dca1e690b5` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:8cc18bb39fdd` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:8de0f1773253` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:6b2bd72c232d` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:383eeda5c852` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:7b57f886a980` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:abe46a9222b7` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11880

- bundle hash: `sha256:9e0d900db8adccd78cc0510f4d88c688ba28d01e5a87ea317509d0862b6e94cd`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:0d5930303a50ec6b5d9feeb60c1e971ce229e5e436a9c76b2700150e4fdc4d72`
- authorization_head: `mu:5656815f09d91044d8101c233bd5f1497a7818f16fa816f53fa54dda31c8b092`
- accepted_head: `mu:d55d867eed2e49aa857b17e28ed317f8caa143be6cd173e97c1f09ed712c27e5`
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
├── 1:GoalStateProposed:1ee0a0c05a05 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:ea80977b7be4 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:76296f72ab73 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:dc8f8946a011 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:fa95e18dd591 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:ad2ee1a1c107 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:9a63c5ccc4c2 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:9a0e97a31cb9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:3f519ee6d446 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:4b0c5d0e64f8 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:8729eb5c79b6 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:a2de2f073491 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:5656815f09d9 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:4125c8b4b384 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:022f4dc8340e MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:1b6339bb67c9 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:40d1a05041b8 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:b6f9f0305e65 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:41628aa2d110 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:61a7a57e14fb FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:b189880c471d FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:d6bec54e9d16 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:d7fc3b8a3825 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:6d517aa564bb PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:e70ec278d2dd OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:d55d867eed2e CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:cd86becf300b MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:1a248de9f690 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:0d5930303a50 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:1ee0a0c05a05` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:76296f72ab73` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:fa95e18dd591` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:ad2ee1a1c107` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:9a0e97a31cb9` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:a2de2f073491` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:b6f9f0305e65` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:41628aa2d110` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:e70ec278d2dd` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:d55d867eed2e` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11885

- bundle hash: `sha256:cc4d9833dfdb02d58074fb8eab3e5aa81bbb42e85ae444958bee6d00296fd2fe`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:c8eded78596dbe48ff86cd88b486d63bf190afcc1053f61032e6800533bd3c33`
- authorization_head: `mu:f60ed2ff6ff7bf8bacd8e334885661e3f95d4267acef5aac9a934af50073e83b`
- accepted_head: `mu:8890f7021de81a2b8799027d5f4e7bc14fb8eea0ab585776f349736d2166eff1`
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
├── 1:GoalStateProposed:321414a5156f GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:facf3d2aabbc AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:84c7d8ae619b WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:c183ba3197c1 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:6b199f162cb5 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:e6f3ba48d2dd MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:abd56b0b78db CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:485880cf31ee OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:b7fc349de80d FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:c7851107b3c8 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:a697e47f0178 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:39a26a3e3d11 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:f60ed2ff6ff7 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:bb2ad4856fcd EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:43612a4cad1e MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:2e6a2e44c2ee PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:89004f619054 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:369e9a17b32c WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:e0e1a9e8f8a4 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:db5f12c791bc FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:53d2df713b4d FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:167cc10684be CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:ad21a188a9cb PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:729ce7791b13 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:de7184f26165 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:8890f7021de8 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:41553d76cc16 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:82f17f39fb57 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:c8eded78596d PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:321414a5156f` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:84c7d8ae619b` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:6b199f162cb5` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:e6f3ba48d2dd` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:485880cf31ee` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:39a26a3e3d11` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:369e9a17b32c` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:e0e1a9e8f8a4` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:de7184f26165` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:8890f7021de8` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11951

- bundle hash: `sha256:5759d06287a37614238776feed880d487d59c1f063a69a72312df02bc021dd11`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:a1b3f62cca1dc87b4f8ec8be630bcac6fbfbd91f5e62b41b2eb9d0f0f4ffdc06`
- authorization_head: `mu:7412369cf920bde1ef24d6564cdd997bfd3a0aa30378e1426a38c8bd0e10d53b`
- accepted_head: `mu:3a02bce693e3d95ae81e19b05b79a2836699ad8dfa4ac5fd1a8f4e45da61ad73`
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
├── 1:GoalStateProposed:faa6914fa863 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:8942b3aa609a AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:66c6912a359c WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:427f78a90046 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:4fd250240ae9 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:d42dd56907bb MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:405594846cb6 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:ad3a93575745 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:b4cdf13ad2c2 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:7a89bc50158c FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:319a729c0d5c RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:217cb5bc9ad9 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:7412369cf920 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:1e530466c3fb EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:594e3dab266b MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:87b9fced1560 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:0f50a375f7a0 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:925b4d4b2223 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:085eca4d1931 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:1ddac1bf2bf5 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:3bed154ab548 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:ce81371ce256 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:0375478c2596 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:d2441a2e2032 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:34c27e5ba1f0 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:3a02bce693e3 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:67bc87b36254 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:2bfa7561c833 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:a1b3f62cca1d PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:faa6914fa863` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:66c6912a359c` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:4fd250240ae9` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:d42dd56907bb` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:ad3a93575745` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:217cb5bc9ad9` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:925b4d4b2223` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:085eca4d1931` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:34c27e5ba1f0` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:3a02bce693e3` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11964

- bundle hash: `sha256:05a538e22401c03b7be88d56df889057e762c4360122dbe72ef0955dd2f1e07e`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:e99db1cd05f6fbc006b155ce240d85974c8df7a40faadf53962eecd645bad4f1`
- authorization_head: `mu:6bf86ba05ef4b8871c64e2986cc7eb073d25e786ea61e46196ff2333a34c05f3`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:a6a9efd4269b GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:b5b4fde439d8 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:ff7034137482 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:cfb3ea5ad457 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:7f9302261f12 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:c62bf3a5c1a7 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:1bb898b02d03 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:35e6f47af02a OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:12ce69a1d245 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:2c1dcdf24242 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:e5c84bf8522c RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:e295c46dd01a WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:6bf86ba05ef4 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:3513d9ba9aa3 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:8dae9b57e59d MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:297734f21fc7 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:3c2546dace80 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:902727e2f0fc WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:b1b3d8622ab8 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:ff0dc2ef58af FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:53ff61b49405 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:ac89466ef466 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:f5cc3ad93206 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:e893120f24ed PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:28649ce0004e OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 26:FailureNode:a30c50d131d1 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:70f51558bb2b MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:b3e352dc0950 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:e99db1cd05f6 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-11999

- bundle hash: `sha256:673f3cd7b3d79f27118d6e82cf770ba5922c886d6b9db0ac8e94551d36227a82`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:46754a2ef504bc2ee63e9fbc47731558c05c1f8f911eb0ec933e97f4dd411c5d`
- authorization_head: `mu:5964de6c93f18a71f7d64f087e847c7699a59f9fa8a58b1ddea988b2ada8750c`
- accepted_head: `mu:14cae4c96140cd705c1999da3ac01e236d3b05d2c0e4e41cb944a4eac190ba60`
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
├── 1:GoalStateProposed:64f92087ebf4 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:37c0af7af1bb AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:e2d676701e34 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:e502257a64c6 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:f4ddc265806d WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:6448b90c243a MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:d5b8ef0a8614 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:43fef7c39a0b OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:19a84cf5ffa3 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:0f83c6b55da0 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:6de3aeb716e9 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:fed1359ad731 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:5964de6c93f1 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:c69cebd86cba EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:6eedd086887a MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:8b8b8742c60b PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:c30fcb60937a BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:391e40c7b580 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:8a51a2becce3 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:230cc531206c FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:5151e6181849 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:ffe0b5fdd87b CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:d09d02860709 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:168008d0fccf PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:855220b0b424 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:14cae4c96140 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:3582deac5333 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:1383770a4872 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:46754a2ef504 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:64f92087ebf4` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:e2d676701e34` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:f4ddc265806d` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:6448b90c243a` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:43fef7c39a0b` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:fed1359ad731` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:391e40c7b580` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:8a51a2becce3` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:855220b0b424` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:14cae4c96140` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12039

- bundle hash: `sha256:279d86592806981b6100695f2f08f4c910d8e0758401e1838df732ffaa382708`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:82de23e86e829e37271449f052579f8dbb7f2f2bcd5bc330bf311d24715edb7b`
- authorization_head: `mu:48db4441b59d21debb89f9d2d49b7313bd00a911483f5594b51abe7be91e331b`
- accepted_head: `mu:80cba4b9f877bfeec46d368d08920a8b31ef890043f46296e856bbe64a91a74d`
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
├── 1:GoalStateProposed:607b217245d6 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:facaea76a52e AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:7cf5bda4bffd WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:6a3d1295822d WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:8b228bbcc9ac WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:807726a054a6 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:81f5dbbd338e CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:ced94400967a OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:7abfe5837b32 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:d05df7418204 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:2a1ee54824fb RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:34b29f6ca961 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:48db4441b59d WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:847f66a1daec EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:132b33d3ab25 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:baf6e1a7ced9 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:3a7cca12e838 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:915c691b6bba WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:1da7134eca8c MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:d9b40ac73e8e FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:dfad91ad5689 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:c0c331471647 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:46c5dc755944 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:bcd33398848b PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:c3d0190c55ad OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:80cba4b9f877 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:1b401bb8caed MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:2171dd9a2ee6 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:82de23e86e82 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:607b217245d6` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:7cf5bda4bffd` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:8b228bbcc9ac` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:807726a054a6` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:ced94400967a` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:34b29f6ca961` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:915c691b6bba` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:1da7134eca8c` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:c3d0190c55ad` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:80cba4b9f877` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12050

- bundle hash: `sha256:e91ba77544481d6bb349540ce09c73741db13e6071491eefb45414a45255c48c`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:1411484a8649a181b89d9d2b1b9dd0f5a2b6cf225f3401ed2cb37d65c3ad5dfa`
- authorization_head: `mu:1f29e68eb985af86dfe86f7fb30a47ab6dcf401a60ac709040f09a462890d097`
- accepted_head: `mu:af0e4c13b860468df5dd2eda79066e1909e0f788646b2f22a209d475386596c2`
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
├── 1:GoalStateProposed:14e4b2712370 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:036660533685 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:847a95df5a50 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:11dc7fb63802 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:b226833e54ef WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:8bc54213843e MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:729d20a9f84b CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:fb5f118e4012 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:eb20cc034d4f FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:08ff8d178326 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:255fe667fa3d RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:7e4c80738d61 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:1f29e68eb985 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:d24ed7fc3979 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:d8dd5bc76b1e MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:cad8bf677862 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:edf7ead04739 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:ca6b411c9537 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:0ef43c2048e9 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:517d395a538d FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:5c992d1b0df3 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:83da4a09b297 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:a8f0c53e8a5b PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:c54d379c39b6 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:e2848383adf7 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:af0e4c13b860 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:7d1d455da452 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:e3119808ef19 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:1411484a8649 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:14e4b2712370` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:847a95df5a50` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:b226833e54ef` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:8bc54213843e` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:fb5f118e4012` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:7e4c80738d61` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:ca6b411c9537` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:0ef43c2048e9` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:e2848383adf7` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:af0e4c13b860` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12143

- bundle hash: `sha256:8b1051c73cfd1d2c25648323e6cc9018b3fe072efcfd26e1ccbdc82ef6ea32d9`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:142d4dfa0047241a6fc5110b1656d8dbe9a1a1a108989c27c8c25931f4b01015`
- authorization_head: `mu:0ffe66ff14cec37634c53a9dec5ed6490d90ed7d4767f51d07472982e9d10a06`
- accepted_head: `mu:63dddedca991ff900cc7bb4de83f5c0b2c593dacd7e7bfde07387472dc1ff682`
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
├── 1:GoalStateProposed:f2da817d2a07 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:9e52359c9bca AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:da5d38919771 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:c06291fc07b5 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:64021196f921 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:19992581c71b MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:e315bc711d27 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:db05e21879a2 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:cc58a1cf9275 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:f139aa3c7d6d FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:12c869835a2f RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:c9116532b996 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:0ffe66ff14ce WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:80555a6e05a0 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:9a0070e6738b MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:13fe6ddccf11 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:7b25abea470d BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:bf0c2d2f833c WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:15a71ad17a2b MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:e00e2c99ff83 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:53d4b9c25f79 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:4804be9faa73 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:b486a16c4f50 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:d4bbf3e73ac2 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:92d378c9fc43 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:63dddedca991 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:8bb68b0afccf MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:308e28923c00 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:142d4dfa0047 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:f2da817d2a07` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:da5d38919771` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:64021196f921` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:19992581c71b` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:db05e21879a2` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:c9116532b996` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:bf0c2d2f833c` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:15a71ad17a2b` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:92d378c9fc43` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:63dddedca991` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12155

- bundle hash: `sha256:24c7e673dee7b04ed483d008e19003e322b28a0bde31b7cfa2341c3a2af9e4ec`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:891ef6b3f17a4cafb15fd335f440bbfff06b4a0a183393778f1e9148050c1baf`
- authorization_head: `mu:a6565dcb03e84af1bcf69a0b3d1608fef149af0050300309bebbedb91994ba8a`
- accepted_head: `mu:1d7fbe7d94ef24e7c9530feeb0b37a01c94e632f03dcde6e1d5504405cf91b8f`
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
├── 1:GoalStateProposed:1266125aa77f GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:94f49961dd99 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:4736527e48a8 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:a9c768fd7b85 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:26acd50eb536 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:08e59f14dc1b MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:cf4882f26bad CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:42c0885eef03 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:d5207ebfe41a FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:4c76e22eb5b1 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:37fa1e00a21c RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:7fab38f10b1a WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:a6565dcb03e8 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:d8e83dc93840 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:3ac8a5a5f9ca MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:0aea39666f12 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:a232ccdebf8e BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:eba186082853 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:0b1e427c0b78 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:be4df821b21e FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:8383d11d115e FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:3e84e87dc132 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:81038206f5bd PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:d89b82d55424 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:73f7b2eda1ed OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:1d7fbe7d94ef CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:6a3db462c9ef MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:55a377d5d5a6 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:891ef6b3f17a PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:1266125aa77f` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:4736527e48a8` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:26acd50eb536` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:08e59f14dc1b` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:42c0885eef03` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:7fab38f10b1a` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:eba186082853` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:0b1e427c0b78` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:73f7b2eda1ed` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:1d7fbe7d94ef` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12193

- bundle hash: `sha256:ae2eea3d2d77034e21d2ad76002f88a0960944998c387d715706b5cbcb62e40c`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:b3e49f4c09cd97a590c12991eb72e6943f0619cd9211f7587af0155249945287`
- authorization_head: `mu:af7803e7c8560b21053d0af9edbff99c7e852a5f847229c93c4ada6a2494d64b`
- accepted_head: `mu:958fb0045a7d6e23dd0c18a41059d82230e378a21b66675a1520393f74b1b5d0`
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
├── 1:GoalStateProposed:b17acb361e9f GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:ad77524cb8eb AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:3cd1b81ef8f3 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:93d0d9f1dcd2 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:0b6ba3c8bf39 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:4deed6facdc6 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:6eb596a2dc83 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:38a9791e94cd OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:2f0ec64760cc FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:5480eb070999 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:5ebca46b4fb9 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:dc91281aa513 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:af7803e7c856 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:520af5ff76c0 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:e1f32717c4d5 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:6453316cbc55 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:ffeee4b8b2fe BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:00493d676638 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:588b043bcec9 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:2ef806faa9d1 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:72127a4722e7 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:0e21119cd08c CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:707e36c23789 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:084dbafba56b PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:204a44f283e1 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:958fb0045a7d CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:b3c4bee4e5de MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:a600886ef312 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:b3e49f4c09cd PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:b17acb361e9f` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:3cd1b81ef8f3` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:0b6ba3c8bf39` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:4deed6facdc6` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:38a9791e94cd` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:dc91281aa513` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:00493d676638` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:588b043bcec9` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:204a44f283e1` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:958fb0045a7d` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12209

- bundle hash: `sha256:1da56c0f64ba147c4311792960a3ef1acd6e25ff3878c36f137409969e29beb4`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:55cf47f31b72dc37b1eae7542816bfa5520825e5796dff11c3699842149e9fb2`
- authorization_head: `mu:69de608ed84aa1ff570fb2978dfd38054d30e0c025345aa91527b88b2915181d`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:c74f9ebacec7 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:8b31141104e0 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:f295a0c9c383 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:85216589e948 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:f63c6fe577b6 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:36f05bc82a61 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:1880aaa204e6 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:9a65ceee2729 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:efbefd6b220a FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:6e9272c0eff6 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:0ea6e2b773bb RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:1ee337e7bb14 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:69de608ed84a WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:48c5d2f7730c EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:cb02f1b81f92 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:d5b89db3a505 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:1786504b350e BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:e32502ec2a2c WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:3f015c798dbd MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:4e1a850fd973 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:1d95064bff81 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:d6ed99ea215f CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:d347c4968d76 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:5978234edb5f PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:473524c3cb3c OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:5d45cd714827 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:08ef63e557c4 MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:f2b404ffe246 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:55cf47f31b72 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-12262

- bundle hash: `sha256:641c005468dae643256330357b95b1f3c7641084bd2fa1eb6817bdf646959e25`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:ec9b2f6fe7e32de363e4ffc89d98d559fd4baa2c757cd44efb57284601d095da`
- authorization_head: `mu:f26553ccb6b4e043e965afc446da79d0e10e42d32e2b9fb22268516486b95b18`
- accepted_head: `mu:3dc7491e8c8193173e70c1f957f2c6556df5e86e4f019f83f412aadf22f51590`
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
├── 1:GoalStateProposed:848dbc7dd67d GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:2dcbaf58b08c AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:f0876ea610fb WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:1056d30018df WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:c609df5a8e1c WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:fc929fa4d666 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:270e36543a42 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:ba79e179744f OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:f9c19d81beb6 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:d48615f41c72 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:05c5f8af52c1 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:9cd88dcbb7d3 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:f26553ccb6b4 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:b727076af961 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:c3f4378da4df MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:bcf67643056f PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:a5c0974fb582 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:b6fd55f1590b WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:5c4b9d73deb8 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:9792d57f30e3 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:cb9ad310476e FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:a1a79975fa87 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:8e9639e7f4ad PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:124a22e2b5f1 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:d3369565fffc OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:3dc7491e8c81 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:ce32da09c1f1 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:a732bc9572f0 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:ec9b2f6fe7e3 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:848dbc7dd67d` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:f0876ea610fb` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:c609df5a8e1c` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:fc929fa4d666` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:ba79e179744f` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:9cd88dcbb7d3` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:b6fd55f1590b` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:5c4b9d73deb8` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:d3369565fffc` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:3dc7491e8c81` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12273

- bundle hash: `sha256:03e13537a96357b04cd6e567756f8e38d137cd5f350e1c3161807d8c6be9e8ce`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:3b126b2530583edc000a535af01d8084252b3f2ebf2189177dec549e04b6cab8`
- authorization_head: `mu:b1422459e2484734b841b27e96dcc3ecc2a58934aaa96c21f724e7cf3eef892b`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:3d7e34b05864 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:5f3df3b50736 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:544663e40792 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:80bcebeab47e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:d2502705b6a3 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:03ec7fdc081a MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:35a5ef2f56b7 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:b6a37163c5a3 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:c68a18f54601 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:09bf9faf7236 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:2942b17ce798 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:846f05771ff9 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:b1422459e248 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:ef52d018b8fb EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:8dfee1db9983 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:0732f0369cd8 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:0410eea03929 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:17e8fd3f91bc WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:333bd8186f1f MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:d5fe029d7dd1 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:c7c3cf187612 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:5853b234d990 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:2658adb118ed PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:c290d986d172 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:f6c41ae922c3 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:cce66e152ccd FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:42046646daaf MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:3a445f798fa7 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:3b126b253058 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-12276

- bundle hash: `sha256:e4ab0bd0fcf24211df270f164c78ca2e808253a6ec9b5b766d573b1b2b6156b3`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:4cc47de7235da2e8e717c05376baa31769d75e79456952a5e549c9b11c796a82`
- authorization_head: `mu:37de4d4d56895bc135a15b59bbb1fd268b2deb596055c5c8451853aa71259c91`
- accepted_head: `mu:6fc028cf6e0d2f28a5f9b636f179e362b207d0a0c70ea14fb2545f54b50e8708`
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
├── 1:GoalStateProposed:8dd0e007b5fa GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:fd0af7419f07 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:6ca04483bfc7 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:7c935f45e40c WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:2c21ab66f7d1 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:c5c3d0b88fa5 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:c395148515c5 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:5041b08b5651 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:3a45b13aab5d FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:0c5c824d48ad FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:423628ddd812 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:696f01f55721 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:37de4d4d5689 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:f01bef20f215 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:af230fd7f4a4 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:c493d0105154 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:65c687970baf BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:7eefaa0a9c3d WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:dd5510eeeaef MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:32f460f41975 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:ef4295a18a6a FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:4d962a81e39f CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:31f8d221efd6 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:26b93bffda64 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:62faeae3998e OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:6fc028cf6e0d CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:6b0abca6f836 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:f0979c26c4bf RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:4cc47de7235d PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:8dd0e007b5fa` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:6ca04483bfc7` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:2c21ab66f7d1` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:c5c3d0b88fa5` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:5041b08b5651` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:696f01f55721` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:7eefaa0a9c3d` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:dd5510eeeaef` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:62faeae3998e` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:6fc028cf6e0d` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12304

- bundle hash: `sha256:4f317d1c5fe8ae6f25fadacc8dd1d978cc2e35dad702bcdea9dec9156181d094`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:63f003f98dd2fd9dfe9abca38db69afe137e235d6d10fc07a853060bd3356f47`
- authorization_head: `mu:b44bc3b7163f93abf8ebbe302f5f3e5921cbd5202e6732f0c948e29baee94a7f`
- accepted_head: `mu:79991c82fe1a400af2a96d7970eabf692012573906c1da378cef1886ec7ad006`
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
├── 1:GoalStateProposed:6ad812e5c2b5 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:ba783be4ed3f AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:ef75a35bb04e WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:7e9a09bd7e30 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:01e8554e5b1d WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:d40a07ada94c MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:4cf10297e47e CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:cb6d5ad58fa9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:14aa18832159 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:045b1bced09b FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:3ff708aecca8 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:ede17eadf751 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:b44bc3b7163f WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:5160d0f2abdc EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:7251e844a654 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:4d869149507e PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:8e76ca1469bd BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:4056c63f27a5 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:5ae59d47710b MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:980dcd55d088 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:ea34f21fa88a FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:b2356b7a5832 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:8fd06f9f4348 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:c20891294ad7 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:bf62b11f896c OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 26:CandidateAccepted:79991c82fe1a CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 27:MarketSettled:ff693a824978 MarketSettled [PRESERVE/PASS] result=YES
├── 28:RewardDistributed:9eb6d7b5bca8 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:63f003f98dd2 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:6ad812e5c2b5` GoalStateProposed [PRESERVE/PASS]
2. `3:WorkCapsuleBuilt:ef75a35bb04e` WorkCapsuleBuilt [PRESERVE/PASS]
3. `5:WorkerReceiptImported:01e8554e5b1d` WorkerReceiptImported [PRESERVE/PASS]
4. `6:MacroObservationImported:d40a07ada94c` MacroObservationImported [PRESERVE/PASS]
5. `8:OfficialEvaluatorEvidenceImported:cb6d5ad58fa9` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `12:WorkCapsuleBuilt:ede17eadf751` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:4056c63f27a5` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:5ae59d47710b` MacroObservationImported [PRESERVE/PASS]
9. `25:OfficialEvaluatorEvidenceImported:bf62b11f896c` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `26:CandidateAccepted:79991c82fe1a` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12308

- bundle hash: `sha256:e3938cdc0493c12a36719a155e937b1ec1d499715c75e93222124094df814e4e`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:7cf4738fce0f95fecf3a44a4ecf2571ed76d59ee510d6cf67bb02fa01bf63175`
- authorization_head: `mu:435db5f29c5204b26b124de6da79a2046bcb754a9563dd6d1100510d6eaddadf`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:319bd61dc4dc GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:b0672fbaa435 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:a5016c086be4 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:7285e3f6beb6 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:e6441bcfa2da WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:cdffe5564d9a MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:4e7c56dd6590 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:e7db6dd71dc4 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:7e598ada08ae FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:410a3af0d602 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:e5d44c76ff69 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:4dbf55c81e59 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:435db5f29c52 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:4ff6e2033602 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:2a2b2b08e9eb MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:c0763d19fe7c PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:83b85fcd511a BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:9f6fda88d6c7 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:e6110c089ba2 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:53f9931b0d5c FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:d2c3bc53b291 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:11f78302be55 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:761a7c83af95 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:ff13abfd0a18 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:f74a4c8d44a1 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:8f3156d25e09 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:ab6752eca3c5 MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:bcb5e4d3926e RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:7cf4738fce0f PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-12325

- bundle hash: `sha256:64cab12debba8b17a8a6c50ba51f4a10458bbf18cfc401365bfe8f01f6f443db`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:929410534d50e4826c764d8c2f337744a0e4332d3af56b41a664fe9d1b1a2111`
- authorization_head: `mu:18ccf8ae76951a31537d856afd1f2e7901394ec1f7dbeed51ca2e8381adcccbf`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
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
PATH_CLASS failed_path
├── 0:SystemConstitutionAccepted:344937f91622 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:2a80fef7b0aa GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:9659ff79ba55 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:869f9b91af0f WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:eb3e000b43ca WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:dfb607a9bc96 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:aa6630ffb591 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:97237c9b7c4c CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:d9d73e583562 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:1bb00a2a1e6c FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:f2ceed8a52ec FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:569422a1b87b RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:21da442f2dfe WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:18ccf8ae7695 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:c3f77d5e92a3 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:e729453c2c27 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:527c8c8b34c0 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:1a92170f8959 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:8f60bd12f82b WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:46afb1452e0d MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:d264a1263095 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:c6e79a73128e FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:18a0bd9ebe7b CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:7be0073b3cee PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:9e6aa70b3836 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:cd03ecc6a516 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:a678cb15b14f FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:e2901a79a995 MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:361f0cbf42ff RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:929410534d50 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._
