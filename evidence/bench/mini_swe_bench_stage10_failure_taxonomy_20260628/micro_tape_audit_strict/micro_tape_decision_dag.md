# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 10 | **Events**: 160

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

- `AtomAuthorized`: 10
- `CostEvent`: 10
- `FailureCertificate`: 10
- `FailureNode`: 10
- `GoalStateProposed`: 10
- `MacroObservationImported`: 10
- `MarketCreated`: 10
- `MarketSettled`: 10
- `OfficialEvaluatorEvidenceImported`: 10
- `PPUTAccounted`: 10
- `PredicateEvaluated`: 10
- `RewardDistributed`: 10
- `SystemConstitutionAccepted`: 10
- `WorkCapsuleBuilt`: 10
- `WorkerDispatchAuthorized`: 10
- `WorkerReceiptImported`: 10

## Runs

### stage10_install_fail

- bundle hash: `sha256:c4c642dc6bdf00a0ecd7e5eaf8c91ec0b1747d6951ae95a9590c514316d1b737`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:d114ae23cfb8d4ff9da3d8703b32a1cacb7e482efd2eed854d65f6f4e5bf1a1b`
- authorization_head: `mu:5c4f90d8927b5acd327e4aaf97b2e5e23d4e17f442fbe4333f8475eef7ac764a`
- accepted_head: `mu:edb35dafab84139b2656d1d8cdddce5b4812921681cc0c16d2b9302ac8a2b09f`
- events: `16`

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
├── 0:SystemConstitutionAccepted:edb35dafab84 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:da63158250f7 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:b8b2a16c226c AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:5c4f90d8927b WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:a530debab159 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:cea04c541718 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:9d5b44553af3 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:12ef6f3907db MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:90849030b706 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:ec5af79794a8 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=INSTALL_FAIL EVIDENCE
├── 10:FailureNode:eaec86becd30 FailureNode [PRESERVE/NOT_RUN] class=INSTALL_FAIL ✗FAIL
├── 11:FailureCertificate:7de32199d6aa FailureCertificate [PRESERVE/PASS] class=INSTALL_FAIL
├── 12:MarketSettled:d82b9dd2178e MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:07792dfa5231 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:e6d4139ce766 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:d114ae23cfb8 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_test_timeout

- bundle hash: `sha256:41043b38aef228f28163c6452cff22d1d80a8024eb2a2b4858ea5d5c86cfa2bf`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:ebe47a8a8871affce2934f689b1c51f783560cf6c11588304decd620f20f7c40`
- authorization_head: `mu:4148c861fbc9bfe813210483f2541a947ff0f36f8e7814985f2514a7c6bd4b88`
- accepted_head: `mu:2a0bbb352119ad9f942a8965cab33ffa11a0cee9bd613ab700318017dcc95e73`
- events: `16`

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
├── 0:SystemConstitutionAccepted:2a0bbb352119 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:3610de4f082a GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:ffe09a24f155 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:4148c861fbc9 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:081ba6396766 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:c7bd20ed5c82 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:3ef541511f27 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:3382510748b3 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:eae3b6be2946 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:25adc420b106 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=TEST_TIMEOUT EVIDENCE
├── 10:FailureNode:14e2c5870237 FailureNode [PRESERVE/NOT_RUN] class=TEST_TIMEOUT ✗FAIL
├── 11:FailureCertificate:172f3d0f82a3 FailureCertificate [PRESERVE/PASS] class=TEST_TIMEOUT
├── 12:MarketSettled:7c1551c4d685 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:dd79e9e7cb71 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:d75508d5cd31 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:ebe47a8a8871 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_wrong_file

- bundle hash: `sha256:02c3a0f14bec6121a8f4e24393ff2bfac5238a7e8cbeca8337d82db1b5523b4f`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:2197d65020bb925ca16292da9ddbf4961f0e986c37768d1252227b4abecf1f10`
- authorization_head: `mu:4fd2591e20c23feeab7de89738ddd4a28c1f86376cdd0002ed0f8a6b1095a66c`
- accepted_head: `mu:2a0bbb352119ad9f942a8965cab33ffa11a0cee9bd613ab700318017dcc95e73`
- events: `16`

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
├── 0:SystemConstitutionAccepted:2a0bbb352119 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:6475d76012a2 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:480ca1a5e0eb AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:4fd2591e20c2 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:04cb39a98613 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:969ec444948b MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:6d4abf27166d WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:3d6bba74f1d9 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:1d35b9b5c675 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:2518114308e3 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=WRONG_FILE EVIDENCE
├── 10:FailureNode:a9debd0f382e FailureNode [PRESERVE/NOT_RUN] class=WRONG_FILE ✗FAIL
├── 11:FailureCertificate:ebefbc3cbcd6 FailureCertificate [PRESERVE/PASS] class=WRONG_FILE
├── 12:MarketSettled:2e62e0be657a MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:9f8e3076f935 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:da89cd27cc53 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:2197d65020bb PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_no_repro

- bundle hash: `sha256:a9256f26eef20cbec0183b8d001e4ee5feb925d473d82f0f161ca81421e1115c`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:9ffe939ab27f937cb5dee4f3639689c6684f359d4dc0e0b1ee821e72c73e5a22`
- authorization_head: `mu:1e9ebca4d640c145f8c0cf604e009fef735ece4821cfef79e8300b68dd259d4a`
- accepted_head: `mu:2a0bbb352119ad9f942a8965cab33ffa11a0cee9bd613ab700318017dcc95e73`
- events: `16`

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
├── 0:SystemConstitutionAccepted:2a0bbb352119 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:09d82782f652 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:af5a85e04ab8 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:1e9ebca4d640 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:ac653f498000 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:0549a4519018 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:00d28d60fe00 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:01be7bbc9b38 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:3f3815318e67 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:344bf095a5e4 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=NO_REPRO EVIDENCE
├── 10:FailureNode:9e50d7332c90 FailureNode [PRESERVE/NOT_RUN] class=NO_REPRO ✗FAIL
├── 11:FailureCertificate:418499dc8c7a FailureCertificate [PRESERVE/PASS] class=NO_REPRO
├── 12:MarketSettled:af43449e1393 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:1ca25b41c903 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:2675fef0f482 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:9ffe939ab27f PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_overbroad_patch

- bundle hash: `sha256:052c80d6c5d5f76d394d9a6143a52581fb90f7c8cf1d483e6ad6581f6a90ebb4`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:58676264c0f13353b8219979f0202b373539f449720456af761b4b0a25904033`
- authorization_head: `mu:d8f3770299df1ebf849c149e34e897edf15e8c16d9098f09f74a617681d11d25`
- accepted_head: `mu:2a0bbb352119ad9f942a8965cab33ffa11a0cee9bd613ab700318017dcc95e73`
- events: `16`

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
├── 0:SystemConstitutionAccepted:2a0bbb352119 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:02137d111619 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:7d6de2ae62ba AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:d8f3770299df WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:d4a4f934cbcd WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:dc19f598b032 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:c4663a560285 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:e85eca14818c MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:8bc618cb5676 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:1172e5ec030b OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=OVERBROAD_PATCH EVIDENCE
├── 10:FailureNode:01b989e8320f FailureNode [PRESERVE/NOT_RUN] class=OVERBROAD_PATCH ✗FAIL
├── 11:FailureCertificate:0eedbb0c37df FailureCertificate [PRESERVE/PASS] class=OVERBROAD_PATCH
├── 12:MarketSettled:07eee79f133f MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:10ac5319f2b3 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:09bd1443f3fa PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:58676264c0f1 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_semantic_fail

- bundle hash: `sha256:54150e660bfddc08028a530cd0f735ac10b95674a94ebc406c22a05ec078e388`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:81085429992b8de7d7eb40159f35b0dc8b979efd4787154d6e6340790ea84c99`
- authorization_head: `mu:c51d4274ed66520d8daf55cb678c463ab424ac140ca3da86534d793cd887be44`
- accepted_head: `mu:179d5c2d7045c8139549cee02be207082f8dda7812c136850bde157493f91180`
- events: `16`

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
├── 0:SystemConstitutionAccepted:179d5c2d7045 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:b19dc44504d4 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:cb86585cda73 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:c51d4274ed66 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:f558d918821d WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:58f482eaab74 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:324f0ec75ea8 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:d74455196331 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:e375cadfcfe9 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:ab4a8965c071 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=SEMANTIC_FAIL EVIDENCE
├── 10:FailureNode:917bf9805ca2 FailureNode [PRESERVE/NOT_RUN] class=SEMANTIC_FAIL ✗FAIL
├── 11:FailureCertificate:c76b7d975ad9 FailureCertificate [PRESERVE/PASS] class=SEMANTIC_FAIL
├── 12:MarketSettled:7df67e196915 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:abf6ac2e64f0 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:7f1c9baf759c PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:81085429992b PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_flaky_oracle

- bundle hash: `sha256:97dc641e5c2ba1156c54230f5c315443e1aabe06dbbdeea80cc60ebecd767963`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:d2ad09eb222da66d228fb8b5c0618961422f55c9f3e6b6df39ae8c892aac7308`
- authorization_head: `mu:d34aacf5d70a55b404402c2487305fb52ccaf7aab3f2b0db523b565150e9b665`
- accepted_head: `mu:179d5c2d7045c8139549cee02be207082f8dda7812c136850bde157493f91180`
- events: `16`

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
├── 0:SystemConstitutionAccepted:179d5c2d7045 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:9f124a71f9a0 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:f1f76cb66201 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:d34aacf5d70a WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:71faf0240f63 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:23cea49eda64 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:34e983a97df8 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:83750a6fd566 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:787783af4c8d CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:d9dd35dcb133 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=FLAKY_ORACLE EVIDENCE
├── 10:FailureNode:34e157afe3b9 FailureNode [PRESERVE/NOT_RUN] class=FLAKY_ORACLE ✗FAIL
├── 11:FailureCertificate:4f590ce89857 FailureCertificate [PRESERVE/PASS] class=FLAKY_ORACLE
├── 12:MarketSettled:f02a9da64746 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:1bafa1ec73ad RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:680e260c4f81 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:d2ad09eb222d PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_dependency_gap

- bundle hash: `sha256:3390a0a37da043346ca8e565d90bd84b4197ea4e966be1be224294c4e18f7baa`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:f24be249efe229388a9e7a7ed0a09e0eebcd32c1e29b0b6273fe9cc8403a16c9`
- authorization_head: `mu:7ddb0fe1ee84f604b24699b256ee817c5abc5d52f9c8dcdbfa12c2b9f00275b0`
- accepted_head: `mu:179d5c2d7045c8139549cee02be207082f8dda7812c136850bde157493f91180`
- events: `16`

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
├── 0:SystemConstitutionAccepted:179d5c2d7045 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:23814cb2655b GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:b7a6d4926122 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:7ddb0fe1ee84 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:38c1d5cfb9a1 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:55533c47b537 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:9ab309437277 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:bc0b10f460dd MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:d9cbbf7c299d CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:d77dd1d7ed32 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=DEPENDENCY_GAP EVIDENCE
├── 10:FailureNode:d81cfd060ba1 FailureNode [PRESERVE/NOT_RUN] class=DEPENDENCY_GAP ✗FAIL
├── 11:FailureCertificate:a1542b13d6df FailureCertificate [PRESERVE/PASS] class=DEPENDENCY_GAP
├── 12:MarketSettled:c22fe7ba6c4a MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:a35596d117ea RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:550e0f8bb210 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:f24be249efe2 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_context_missing

- bundle hash: `sha256:705325d101ce2d0ff457c6410f2f0c0b9558b968001bf7175366a963409324d6`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:7ba516961cb31b9c98082286c7ff72384dfaff007c293c17f2c56e72939d3dd0`
- authorization_head: `mu:45354cc212883ae18e5e78df11717f0455de6adcc73f31c80fd048c4f2f7e040`
- accepted_head: `mu:81edc1aa44d3bebfc786d045dbd97f93d12d076cab7fe66fe7545501096236f6`
- events: `16`

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
├── 0:SystemConstitutionAccepted:81edc1aa44d3 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:d992b8a544c6 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:42f60f1ede52 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:45354cc21288 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:456ccc94b340 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:1c934bd93453 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:4415eb224fcc WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:b95f746f0c70 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:98277f38be6d CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:2b0ce5ce090f OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=CONTEXT_MISSING EVIDENCE
├── 10:FailureNode:1e9dad63e20c FailureNode [PRESERVE/NOT_RUN] class=CONTEXT_MISSING ✗FAIL
├── 11:FailureCertificate:f28e096f0654 FailureCertificate [PRESERVE/PASS] class=CONTEXT_MISSING
├── 12:MarketSettled:89d6eb60b595 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:03fac70d163f RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:ab88dc5bf4b4 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:7ba516961cb3 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### stage10_patch_applies_but_wrong

- bundle hash: `sha256:359e25e16693c1df73a69d91276e009da4d69504380c328e5187ee60d579d03b`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:dd76cabf4d6dd5556cecbac2f8668cfcfad884875a5aab509511a0fb94ec4057`
- authorization_head: `mu:3c27e9396f44c914ab7cdd0f8ac2816e06d4d3bf050aeccf8062b57a39abbfb0`
- accepted_head: `mu:81edc1aa44d3bebfc786d045dbd97f93d12d076cab7fe66fe7545501096236f6`
- events: `16`

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
├── 0:SystemConstitutionAccepted:81edc1aa44d3 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:27a8e48bb0c1 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:fdc550863615 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:3c27e9396f44 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:3c3973578bcd WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:e5c9d63b8102 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:a38487923d88 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:e7c245d2ab96 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:0d603aa0b8b9 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:63374f2a111c OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=PATCH_APPLIES_BUT_WRONG EVIDENCE
├── 10:FailureNode:91a72659287f FailureNode [PRESERVE/NOT_RUN] class=PATCH_APPLIES_BUT_WRONG ✗FAIL
├── 11:FailureCertificate:3ec616463186 FailureCertificate [PRESERVE/PASS] class=PATCH_APPLIES_BUT_WRONG
├── 12:MarketSettled:199870f1bcb1 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:c0d5f5426fb0 RewardDistributed [PRESERVE/PASS]
├── 14:PPUTAccounted:7e78a243c949 PPUTAccounted [PRESERVE/PASS] progress=0
└── 15:PredicateEvaluated:dd76cabf4d6d PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._
