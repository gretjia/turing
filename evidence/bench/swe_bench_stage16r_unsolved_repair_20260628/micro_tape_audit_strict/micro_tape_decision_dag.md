# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 7 | **Events**: 147

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
- `BroadcastRuleActivated`: 7
- `BudgetAllocated`: 7
- `CandidateAccepted`: 7
- `CostEvent`: 7
- `EvidenceBound`: 7
- `FailureCertificate`: 7
- `GoalStateProposed`: 7
- `MacroObservationImported`: 7
- `MarketCreated`: 7
- `MarketSettled`: 7
- `OfficialEvaluatorEvidenceImported`: 7
- `PPUTAccounted`: 7
- `RetryAuthorized`: 7
- `RewardDistributed`: 7
- `SystemConstitutionAccepted`: 7
- `WorkCapsuleBuilt`: 14
- `WorkerDispatchAuthorized`: 14
- `WorkerReceiptImported`: 7

## Runs

### django__django-11790

- bundle hash: `sha256:465bf35259b69aaf9f2d6f1636ea270fb3753beafc916f90d0557cfb824a17a5`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:c5e9885b2d10f4ca602e51c22bc07f62c978930525d2bef297e8b70e5180a7b4`
- authorization_head: `mu:d2c7b6d3e440272ed44e5a21f7329fff342d1b4e5b4ae4edb392780b1addcbd8`
- accepted_head: `mu:5ae73113ab3a0f6ddd99b54aa40c2b1ab8c1c035f50ebbc8d262500ccbc273e2`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:5379ee3f1c05 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:7b85d30bb8de GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:b302115d2274 EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:1f96fc64d28d AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:4d1457a95cbe WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:9d8631585676 WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:95f4931f869d FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:e7ade375760f BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:55b55affe3cf RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:d2c7b6d3e440 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:0cb9891eb727 WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:c4beb52a7a40 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:dea82829dc08 BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:fe1125275592 WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:982a2bbb27a9 MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:c0b44692c157 CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:a8e02e90dd55 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:5ae73113ab3a CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:9d54b4b2ec85 MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:89db30ccd425 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:c5e9885b2d10 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:7b85d30bb8de` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:9d8631585676` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:0cb9891eb727` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:fe1125275592` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:982a2bbb27a9` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:a8e02e90dd55` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:5ae73113ab3a` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11815

- bundle hash: `sha256:baa14626a0320e5777e55421086df3c15eda6d7d6a9a92b6f726272f17bfc7a3`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:d4a2ba6fd496e43441622c726513b623ab8d3cf991d27749e51e5b57b8cdc1fe`
- authorization_head: `mu:d4b5541be1a19b26ad016fe1078e534567d542503d40074763f37b645bf7bf77`
- accepted_head: `mu:71f0857710eb8222270f4a2ea80b3c356b77e343cbe54a4d3e731f23c2fe9505`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:5379ee3f1c05 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:f9c52613db4b GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:2e1abbab586f EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:e9e04762763d AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:4f4c74d00afb WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:10bad2c44fc3 WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:99e2f4c2f18c FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:d8c0f7412ae1 BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:7f4ca9d8a402 RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:d4b5541be1a1 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:b1db173dd738 WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:e8c4b2912eb7 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:0344810fc5d7 BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:6a75e71e15e9 WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:053520199a15 MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:6c767d6233c4 CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:320ec1a79a2c OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:71f0857710eb CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:615dcbd7faaa MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:fc2b1b9d6669 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:d4a2ba6fd496 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:f9c52613db4b` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:10bad2c44fc3` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:b1db173dd738` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:6a75e71e15e9` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:053520199a15` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:320ec1a79a2c` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:71f0857710eb` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-11964

- bundle hash: `sha256:613161178d618beaf185c616166b1035a4819d24ebac5b254bb1330465b25851`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:de580a73c4e595bb6a6fd3469a3c5f0b87fabe34afecb3b5d1284059d288493b`
- authorization_head: `mu:ad21fb7d9172ba63509c1dd7500be59f2db1db62608b49eaa19d641641ea619b`
- accepted_head: `mu:e1322ab2e0d017c16891715e6c64fcf8b623b15d6fa6a324e73ef424d4c846ba`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:f13af1979ee0 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:fb25d6b4810b GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:c26e2b199f10 EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:5512ccd0a4a9 AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:1769f444abd8 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:6dc618ed64fd WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:dac5515e3c73 FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:87d24f50a733 BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:87fcab35d885 RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:ad21fb7d9172 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:4d5857058e87 WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:626e72425678 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:35a05400c199 BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:221c4c975e01 WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:6212a476d9ad MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:c67cd8614ec3 CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:67b0f6f82b95 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:e1322ab2e0d0 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:b7e9d602c727 MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:655bc5fdaab5 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:de580a73c4e5 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:fb25d6b4810b` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:6dc618ed64fd` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:4d5857058e87` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:221c4c975e01` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:6212a476d9ad` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:67b0f6f82b95` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:e1322ab2e0d0` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12209

- bundle hash: `sha256:b8fc5d8439cf016670364d65ff84d987f4d735b5b8c102227cccd6cd61e2c6c5`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:5cf3ad6d9ab4d9d86444eb5fef6653bbd49a994bf934291f6a905c5f50b0de2b`
- authorization_head: `mu:b8383cd00fd4bb6b2038b533e0d492e471ad3d558de313a322e8fc6beda446f2`
- accepted_head: `mu:a71e8370f0bb9a31583e10352bbbcab1eb9772445a9f1df74bfda7f8704fe895`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:f13af1979ee0 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:c5c405af2357 GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:fdbbc0672ef1 EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:1aeea57b1652 AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:bcf8eef1cdb2 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:7f172e398af4 WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:063196fe1ca4 FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:941a6d0f676d BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:f28e0a86ea01 RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:b8383cd00fd4 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:b018fec0514c WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:533912014671 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:5921dede711a BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:b8bacff34e59 WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:918c63bc894e MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:cd2b5b81bbed CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:f9031ce12d5c OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:a71e8370f0bb CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:d5d90bb9bf52 MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:97318a6c3294 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:5cf3ad6d9ab4 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:c5c405af2357` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:7f172e398af4` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:b018fec0514c` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:b8bacff34e59` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:918c63bc894e` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:f9031ce12d5c` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:a71e8370f0bb` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12273

- bundle hash: `sha256:2618a7e76887dc0870c567896013d2644d33abfd197ea1809b57526bdceb5c7c`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:2b5dcd5b6b292e9ddf5aa5ceae0ed9a5e2da1f6c820a369be727d4838ceb18bd`
- authorization_head: `mu:9dd71f690414a8f927fa0e7666e884b614e657d353afe76cd5102a634ff2f383`
- accepted_head: `mu:5764dd3d2b0042b032ce8b5f430ae1505fd2d4d4f37e73025ba7ec010abf0eb3`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:f047a7d487cb SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:13abb70be261 GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:08a9a1c982cf EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:dec6cf759dc9 AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:a091c1d51d24 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:b20f2e01ba14 WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:3ec11f228cf0 FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:f1e2c51bf469 BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:8b9f71cd7c5b RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:9dd71f690414 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:321706488dcd WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:86a2e79d2ca6 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:66d41411e964 BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:c0bfe4efcfc9 WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:7866cd2e83cf MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:c197f0805acb CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:1b2e3f8b1727 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:5764dd3d2b00 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:eed79ded461a MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:047ff683c9d4 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:2b5dcd5b6b29 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:13abb70be261` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:b20f2e01ba14` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:321706488dcd` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:c0bfe4efcfc9` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:7866cd2e83cf` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:1b2e3f8b1727` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:5764dd3d2b00` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12308

- bundle hash: `sha256:efe8656cbc3256f364a7e3043ec24322be026d222b72de6ae29d1f4e0e77c768`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:4c21707dbf4221eb436d265ed4493dcfc30788543cb516a85614b9d92d4cb36e`
- authorization_head: `mu:b89a35e96d7841a771dc84d4448690a31f154517d019d71dcfe6002beba11f63`
- accepted_head: `mu:e228c4f9eb836012b7ca1e1a985a248ef7f01b1111a40ca5baa2495006eeb050`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:f047a7d487cb SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:8b170b18df93 GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:3d36ea7f266b EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:2af6584440eb AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:24e7f01991fc WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:7d15845914df WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:22ab94632c3a FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:31b70283d55c BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:bfe0b19c3b7e RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:b89a35e96d78 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:c55353845986 WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:9f41f8c4dce4 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:7ce66c50367c BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:fcbe4f3d4a7a WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:9a855953eaf4 MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:c1caaa7fa412 CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:e9ed36345bde OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:e228c4f9eb83 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:00fd5896cd54 MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:cee11115e292 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:4c21707dbf42 PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:8b170b18df93` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:7d15845914df` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:c55353845986` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:fcbe4f3d4a7a` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:9a855953eaf4` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:e9ed36345bde` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:e228c4f9eb83` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12325

- bundle hash: `sha256:94b0d1286664a94c5246069f0c204709930c31400639fa71ca9dc11020585619`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:2e886355b38ce654d2aecb731a9c19f23713e31439926794bb578403cf609ef5`
- authorization_head: `mu:13cb24eb5e707140b90213670c7e4c7802e012ba8a05fb64c742892ad3c93dab`
- accepted_head: `mu:38a7975df9fd6943e9c2ae4efd06cf7ae84919d52d74537289bad30b907cbff9`
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
PATH_CLASS accepted_path
├── 0:SystemConstitutionAccepted:033c5d4ccffd SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:4e574f526524 GoalStateProposed [PRESERVE/PASS]
├── 2:EvidenceBound:c7185b7b8b62 EvidenceBound [PRESERVE/PASS]
├── 3:AtomAuthorized:8ef2f98af21a AtomAuthorized [ADVANCE/PASS]
├── 4:WorkerDispatchAuthorized:9f7b415fbb35 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 5:WorkCapsuleBuilt:7c27d028a224 WorkCapsuleBuilt [PRESERVE/PASS]
├── 6:FailureCertificate:8cd5587bc99b FailureCertificate [PRESERVE/PASS] class=OFFICIAL_EVAL_FAIL
├── 7:BroadcastRuleActivated:b9d437644b53 BroadcastRuleActivated [ADVANCE/PASS] class=OFFICIAL_EVAL_FAIL
├── 8:RetryAuthorized:cdf64f784ac2 RetryAuthorized [ADVANCE/PASS]
├── 9:WorkerDispatchAuthorized:13cb24eb5e70 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 10:WorkCapsuleBuilt:38091783652c WorkCapsuleBuilt [PRESERVE/PASS]
├── 11:MarketCreated:9a5710c64820 MarketCreated [PRESERVE/PASS]
├── 12:BudgetAllocated:0a1cc4b8ee23 BudgetAllocated [PRESERVE/PASS]
├── 13:WorkerReceiptImported:f2fe895ba3d2 WorkerReceiptImported [PRESERVE/PASS]
├── 14:MacroObservationImported:b1fca876689b MacroObservationImported [PRESERVE/PASS]
├── 15:CostEvent:09c33b062b21 CostEvent [PRESERVE/PASS]
├── 16:OfficialEvaluatorEvidenceImported:482fd21d32a6 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 17:CandidateAccepted:38a7975df9fd CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 18:MarketSettled:ba819f724d67 MarketSettled [PRESERVE/PASS] result=YES
├── 19:RewardDistributed:4eef3f3fbdf3 RewardDistributed [PRESERVE/PASS]
└── 20:PPUTAccounted:2e886355b38c PPUTAccounted [PRESERVE/PASS] progress=1
```

#### Accepted Path

1. `1:GoalStateProposed:4e574f526524` GoalStateProposed [PRESERVE/PASS]
2. `5:WorkCapsuleBuilt:7c27d028a224` WorkCapsuleBuilt [PRESERVE/PASS]
3. `10:WorkCapsuleBuilt:38091783652c` WorkCapsuleBuilt [PRESERVE/PASS]
4. `13:WorkerReceiptImported:f2fe895ba3d2` WorkerReceiptImported [PRESERVE/PASS]
5. `14:MacroObservationImported:b1fca876689b` MacroObservationImported [PRESERVE/PASS]
6. `16:OfficialEvaluatorEvidenceImported:482fd21d32a6` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
7. `17:CandidateAccepted:38a7975df9fd` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
