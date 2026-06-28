# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 7 | **Events**: 210

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
- `CandidateAccepted`: 2
- `CostEvent`: 14
- `EvidenceBound`: 7
- `FailureCertificate`: 7
- `FailureNode`: 26
- `GoalStateProposed`: 7
- `MacroObservationImported`: 14
- `MarketCreated`: 7
- `MarketSettled`: 7
- `OfficialEvaluatorEvidenceImported`: 14
- `PPUTAccounted`: 14
- `PositionMinted`: 7
- `PredicateEvaluated`: 7
- `RetryAuthorized`: 7
- `RewardDistributed`: 7
- `SystemConstitutionAccepted`: 7
- `WorkCapsuleBuilt`: 14
- `WorkerDispatchAuthorized`: 14
- `WorkerReceiptImported`: 14

## Runs

### django__django-11790

- bundle hash: `sha256:349d923efc850a0fbd5a38a64724d190bfed86ed575ab94114664ca2824c01e0`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:a88fbf2f1d7d97517a8552f5b30475c20a2af5291a7381d36fd87ea0aec4a5ba`
- authorization_head: `mu:cb8fa19dd5b525c2b3ca3a2c283f440d6a1f5c2c4c5eb9341512ed8cb7a81e4d`
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
├── 2:AtomAuthorized:1a3c5433a558 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:342cd4faa35a WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:620a28f03f55 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:645d3edfbf3d WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:45f12452d09e MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:fcfa8894e4c6 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:37d19814cc30 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:315d325a281a FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:8bcfc1c005ca FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:b02c17a002f3 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:6864a01a5026 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:cb8fa19dd5b5 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:495cc2b73ad1 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:4373c8dd529d MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:2d2b7d200eaf PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:a0bc91bb9e7b BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:7daccb469bc0 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:0219ac6df815 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:299477a70f59 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:18355606d8c6 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:3becd997b692 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:825a3d89ad66 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:17c1d8aefa4d PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:2e30029fb133 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 26:FailureNode:06d479dbf7a5 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:bb6ec628792c MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:5e417e1bcf14 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:a88fbf2f1d7d PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

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

- bundle hash: `sha256:40e732db5615ea3fa9864c1cfe45e53440ff97d5a817bf7e24764630aa8066b8`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:0a15f2492563492bb2e92cd66739f27784aedd35356f32699f2081a943977560`
- authorization_head: `mu:af084fd7e00b86954164b80d50c0a164cf160c4ea3e124ef21765f075a9b2d07`
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
├── 2:AtomAuthorized:c936ed3a1310 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:c286cea2f2c9 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:00f5bc627d1d WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:a2f5f1a3f435 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:d21ff0787eeb MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:4e7d29a6f0f1 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:0ba3c443adbc OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:0f6e9230a5b6 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:2e6c4911f790 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:7d1ca8882216 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:0a90c06c60a6 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:af084fd7e00b WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:077ec993fba1 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:74f238c0afed MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:702e68844477 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:d66d621b0aa1 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:c1b91bb69be1 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:92f7c69e3a93 MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:04d003e3ffb6 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:0a269fb8db27 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:134e68d693f6 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:5967c6ebaf01 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:6a91ed3ac902 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:572d7f443e5f OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 26:FailureNode:9b84e0e0d80d FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:11ac23dd7cc4 MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:16315b331d37 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:0a15f2492563 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-12209

- bundle hash: `sha256:f06b6f0c07d7e2dbb391dd5dc2eb8e63e9cf176b780a93ad2e0258b761105de4`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:4e0d3a7b7e84f891b50a7339daf274abaded340ac1352dd13734ff78cec663fc`
- authorization_head: `mu:58bd1a0b68aa0758d9a158f003308f6f6d07caaf10ac67c222fbe6612846bf6f`
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
├── 2:AtomAuthorized:17f9b63f1e30 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:6016b1075d31 WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:ecb7dc7582f7 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:42b3a0bce02a WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:eca52dac5a18 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:5d739a403953 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:77dd728d4778 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:bd022d6fb63a FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:f5cda506a669 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:9a539c5410ac RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:86eabc4e554d WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:58bd1a0b68aa WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:8cde8b801a67 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:6c92b651352f MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:31d42a01398b PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:82a4765bcb91 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:1bdd48705b4f WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:c3f81b9165bd MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:9eba7313908d FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:c56fe36d0c39 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:c840457db0d4 CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:cd0072e66651 PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:56f29e74fe15 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:bc49249298f1 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 26:FailureNode:31283baccc0a FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:65333177509f MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:95d6331e9723 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:4e0d3a7b7e84 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-12273

- bundle hash: `sha256:d524d8119d6b4a9e77629f2657bf254589fabac050883db18d23453fb4cca3c5`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:5be90532b1aa687ee534ad6091ebaf6dcafa72ed9b96eef6f2747c6920c76b78`
- authorization_head: `mu:930002d77a7e81a4b5683bcb01f68e2b6d83437f3251050d6b692fc290e4aac0`
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
├── 2:AtomAuthorized:590e7a71018c AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:9b376789a4de WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:85106c8663e4 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:f542c8c34391 WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:b021b347a29e MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:c1809f57a65d CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:e415e2a858fd OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:38008ce1e262 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:22925b7278ab FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:93900a762d99 RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:e693790c78c5 WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:930002d77a7e WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:9b96f126c7d6 EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:0333d3c7d225 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:8a4f1f3d292e PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:adba6691922c BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:a5f6b833a61d WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:8433d1c93f2a MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:440cbff83be7 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:e5a2f425d324 FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:c3d0ca4ab51d CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:3e1b2f5fc24e PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:7afa31b443e5 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:d502b1264ad9 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 26:FailureNode:02f8b4b4c648 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:f26c05a2370d MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:d3b52be68966 RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:5be90532b1aa PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-12308

- bundle hash: `sha256:7457b5976d9b001645a5a3139fb5ca5a2aa7ab1461b70c0467a34fd2a51891ea`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:235b64140a25e52b440d88ef79e3166d657c4a4f8d77d4a99317dbd82905c08b`
- authorization_head: `mu:eeecdfeb27f9a75257fea92405d4d090e9e93d35949b78a60e45cac36505ae91`
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
├── 2:AtomAuthorized:77f2d24478b7 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkCapsuleBuilt:a73eca4dfb6f WorkCapsuleBuilt [PRESERVE/PASS]
├── 4:WorkerDispatchAuthorized:afada08a5f74 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkerReceiptImported:17bee4da3d6f WorkerReceiptImported [PRESERVE/PASS]
├── 6:MacroObservationImported:dc5d7c75da74 MacroObservationImported [PRESERVE/PASS]
├── 7:CostEvent:a091feecf2e9 CostEvent [PRESERVE/PASS]
├── 8:OfficialEvaluatorEvidenceImported:b5f9fefb86c2 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH EVIDENCE
├── 9:FailureNode:012e3a7fcb06 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 10:FailureCertificate:7f8c8c7a6612 FailureCertificate [PRESERVE/PASS] class=MISSING_OR_EMPTY_PATCH
├── 11:RetryAuthorized:12e5d55acf4f RetryAuthorized [ADVANCE/PASS]
├── 12:WorkCapsuleBuilt:3c1027049dad WorkCapsuleBuilt [PRESERVE/PASS]
├── 13:WorkerDispatchAuthorized:eeecdfeb27f9 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 14:EvidenceBound:e50c3c5ab68e EvidenceBound [PRESERVE/PASS]
├── 15:MarketCreated:983b75ac5318 MarketCreated [PRESERVE/PASS]
├── 16:PositionMinted:fdc2b3324cb5 PositionMinted [PRESERVE/PASS]
├── 17:BudgetAllocated:feca6e8a69f1 BudgetAllocated [PRESERVE/PASS]
├── 18:WorkerReceiptImported:b41191d05ce2 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:61defc3e6dbd MacroObservationImported [PRESERVE/PASS]
├── 20:FailureNode:86a4d62e20b0 FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 21:FailureNode:4ec041757a4d FailureNode [PRESERVE/FAIL] class=STEER_REJECTED ✗FAIL
├── 22:CostEvent:66362f662d2b CostEvent [PRESERVE/PASS]
├── 23:PPUTAccounted:01261be88fbd PPUTAccounted [PRESERVE/PASS] progress=0
├── 24:PredicateEvaluated:177aa7516d36 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
├── 25:OfficialEvaluatorEvidenceImported:804dbb2ab048 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OFFICIAL_EVAL_FAIL EVIDENCE
├── 26:FailureNode:c9c1fbd6466d FailureNode [PRESERVE/FAIL] class=SEMANTIC_FAILURE ✗FAIL
├── 27:MarketSettled:8f15ba364b8a MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:a79f8044691d RewardDistributed [PRESERVE/PASS]
└── 29:PPUTAccounted:235b64140a25 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

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
