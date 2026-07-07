# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 4 | **Events**: 60

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

- `AtomAuthorized`: 4
- `BroadcastRuleActivated`: 1
- `CandidateAccepted`: 1
- `CostEvent`: 4
- `FailureCertificate`: 3
- `FailureNode`: 3
- `GoalStateProposed`: 4
- `MacroObservationImported`: 4
- `MarketCreated`: 4
- `MarketSettled`: 4
- `OfficialEvaluatorEvidenceImported`: 4
- `PPUTAccounted`: 4
- `RewardDistributed`: 4
- `SystemConstitutionAccepted`: 4
- `WorkCapsuleBuilt`: 4
- `WorkerDispatchAuthorized`: 4
- `WorkerReceiptImported`: 4

## Runs

### django__django-11790

- bundle hash: `sha256:55a93b5595dae00c1c01aef7fbc4f2713174bd22cdfbf855f1e587098f4766e3`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:7f0baeba0dd80b70eeb34982a4bfee588f55515fa2f7076e2215ba06acf6fb18`
- authorization_head: `mu:21a4927086ab506de645f31e9ac3bb78f9719e9b8854891b96485a8e1f9c2e9c`
- accepted_head: `mu:b3086f5aead4a9c5782631babd081aa5ede760bec5650f0ced3a23928d6ef797`
- events: `15`

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
├── 0:SystemConstitutionAccepted:b3086f5aead4 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:58e43e0b23f3 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:ed6da12b5d12 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:21a4927086ab WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:2dd0d0785108 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:58623a2060b7 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:8147d9c27da9 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:dda0d9c035e5 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:983286597cdd CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:a8eddb8470b2 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=CONTEXT_MISSING EVIDENCE
├── 10:FailureNode:90081f5bedc4 FailureNode [PRESERVE/NOT_RUN] class=CONTEXT_MISSING ✗FAIL
├── 11:FailureCertificate:b1960ed24eb9 FailureCertificate [PRESERVE/PASS] class=CONTEXT_MISSING
├── 12:MarketSettled:5758e5d4df51 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:0a67d3d3187b RewardDistributed [PRESERVE/PASS]
└── 14:PPUTAccounted:7f0baeba0dd8 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-11815

- bundle hash: `sha256:cfd69abe09f7979dc54d0d3ba69f2feeb6e85820ada08f3e7a4cf3fbfb9349d1`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:ef07561b192be7546f6ab16e7067b1c25bb3cfc736248a940a8d07763debf92b`
- authorization_head: `mu:dfdb8590757c098f16dd74b5f3f70b11e76ee907b8ac90ab231faffc11627003`
- accepted_head: `mu:b3086f5aead4a9c5782631babd081aa5ede760bec5650f0ced3a23928d6ef797`
- events: `15`

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
├── 0:SystemConstitutionAccepted:b3086f5aead4 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:99eb0cc59d9d GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:ccc47dfb4f4e AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:dfdb8590757c WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:c7293a37680d WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:ef26dd75dd1f MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:6504bc612a44 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:f48cc966c47f MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:568667ef0caf CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:dd21d91292d5 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=CONTEXT_MISSING EVIDENCE
├── 10:FailureNode:aefffa0502b0 FailureNode [PRESERVE/NOT_RUN] class=CONTEXT_MISSING ✗FAIL
├── 11:FailureCertificate:bd5776aad21c FailureCertificate [PRESERVE/PASS] class=CONTEXT_MISSING
├── 12:MarketSettled:e520e71ae069 MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:cc5d218d6435 RewardDistributed [PRESERVE/PASS]
└── 14:PPUTAccounted:ef07561b192b PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-11848

- bundle hash: `sha256:00433a2295664df378f0a78a5d898d3dc92771f6f2b3a9cc060ad4120a74e85c`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:d24cb33cd426aadd988a42fefe941c2c69c27dce88be588f418d90c52db7e54a`
- authorization_head: `mu:c2413b9287a65828dda7e375322e138f27b83efe4bf3a62fcabf2514f6281f53`
- accepted_head: `mu:44c009818cefd82268545271add6d4ccf088f95b7ae8868b96eb5d1ae6c016c7`
- events: `15`

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
├── 0:SystemConstitutionAccepted:44c009818cef SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:0f0920343fcc GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:0b369a0bed23 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:c2413b9287a6 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:9765d723d0ce WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:922490efd5ce MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:b70077d3fd60 WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:b49dc5d12d86 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:350ede7678d8 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:1cec42858afe OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=CONTEXT_MISSING EVIDENCE
├── 10:FailureNode:7b46810f0139 FailureNode [PRESERVE/NOT_RUN] class=CONTEXT_MISSING ✗FAIL
├── 11:FailureCertificate:8425fe9b0172 FailureCertificate [PRESERVE/PASS] class=CONTEXT_MISSING
├── 12:MarketSettled:1031452df62c MarketSettled [PRESERVE/PASS] result=NO
├── 13:RewardDistributed:af127356f283 RewardDistributed [PRESERVE/PASS]
└── 14:PPUTAccounted:d24cb33cd426 PPUTAccounted [PRESERVE/PASS] progress=0
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._

### django__django-11880

- bundle hash: `sha256:fa5ab7741561495bcf131fe9d1cb1006187afb1b9a160eae8475bdfeb6472f78`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:d5a9b4558a2ceab687820ba5ee94c57ff7dd5ee151d8835740e72aedb92c7430`
- authorization_head: `mu:125c52436e423017ae08df91a6784421c5d9c80f19a669edbfc5ef85b73189de`
- accepted_head: `mu:c3f69962fdcba0c35efb46dcd4c4466f2c9614c3cc4f21618117d36e4d2740ab`
- events: `15`

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
├── 0:SystemConstitutionAccepted:44c009818cef SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:6da350e9c03a GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:c9609c69da9c AtomAuthorized [ADVANCE/PASS]
├── 3:BroadcastRuleActivated:3aa9b0258eef BroadcastRuleActivated [ADVANCE/PASS] class=CONTEXT_MISSING
├── 4:WorkerDispatchAuthorized:125c52436e42 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:eaadf88a22d4 WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:MarketCreated:faf3179c0dc5 MarketCreated [PRESERVE/PASS]
├── 7:WorkerReceiptImported:82dc43c24d8f WorkerReceiptImported [PRESERVE/PASS]
├── 8:MacroObservationImported:3e5db2226e51 MacroObservationImported [PRESERVE/PASS]
├── 9:CostEvent:efa08191e3a2 CostEvent [PRESERVE/PASS]
├── 10:OfficialEvaluatorEvidenceImported:5a70a4a5515b OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 11:CandidateAccepted:c3f69962fdcb CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 12:MarketSettled:ed11396cc31a MarketSettled [PRESERVE/PASS] result=YES
├── 13:RewardDistributed:05970093afe0 RewardDistributed [PRESERVE/PASS]
└── 14:PPUTAccounted:d5a9b4558a2c PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:6da350e9c03a` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:eaadf88a22d4` WorkCapsuleBuilt [PRESERVE/PASS]
3. `7:WorkerReceiptImported:82dc43c24d8f` WorkerReceiptImported [PRESERVE/PASS]
4. `8:MacroObservationImported:3e5db2226e51` MacroObservationImported [PRESERVE/PASS]
5. `10:OfficialEvaluatorEvidenceImported:5a70a4a5515b` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `11:CandidateAccepted:c3f69962fdcb` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
