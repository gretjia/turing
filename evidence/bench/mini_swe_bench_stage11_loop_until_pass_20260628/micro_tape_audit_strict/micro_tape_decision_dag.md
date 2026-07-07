# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 3 | **Events**: 78

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

- `AtomAuthorized`: 3
- `BroadcastRuleActivated`: 3
- `CandidateAccepted`: 3
- `CostEvent`: 6
- `FailureCertificate`: 3
- `FailureNode`: 3
- `GoalStateProposed`: 3
- `MacroObservationImported`: 6
- `MarketCreated`: 3
- `MarketSettled`: 3
- `OfficialEvaluatorEvidenceImported`: 6
- `PPUTAccounted`: 6
- `PredicateEvaluated`: 3
- `RetryAuthorized`: 3
- `RewardDistributed`: 3
- `SystemConstitutionAccepted`: 3
- `WorkCapsuleBuilt`: 6
- `WorkerDispatchAuthorized`: 6
- `WorkerReceiptImported`: 6

## Runs

### stage11_case_1

- bundle hash: `sha256:47cc03074a8407edb8e4ad412e173e43077170b108d60853edf2397d3037f266`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:29f3f96bbb789a6ed8728b59aec080a7ab29297c6b6ba307b69405a39409dc4d`
- authorization_head: `mu:91dea85cb8bf8f3e47f57ee6d26246dfda2294885cf78e726e0c8c36baf0b772`
- accepted_head: `mu:fcf84f25893809b9d4b44a173a694a2352c4acf0c37ddd95dfa6a7eefeeb2937`
- events: `26`

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
├── 0:SystemConstitutionAccepted:a2d1ba27eb73 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:244d736a2802 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:8ce3742a5b34 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:48ac398f693c WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:047614a3e6e5 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:1a05350099ee MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:1f29d17af42d WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:9fc09efa6add MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:2256ecc693ea CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:04660e4b19cb OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=WRONG_FILE EVIDENCE
├── 10:FailureNode:280f34f56b35 FailureNode [PRESERVE/NOT_RUN] class=WRONG_FILE ✗FAIL
├── 11:PPUTAccounted:9c7c0fbdba82 PPUTAccounted [PRESERVE/PASS] progress=0
├── 12:FailureCertificate:0115b0cfcffe FailureCertificate [PRESERVE/PASS] class=WRONG_FILE
├── 13:BroadcastRuleActivated:efa37cda18f0 BroadcastRuleActivated [ADVANCE/PASS] class=WRONG_FILE
├── 14:RetryAuthorized:78fc6c99dc3f RetryAuthorized [ADVANCE/PASS]
├── 15:WorkerDispatchAuthorized:91dea85cb8bf WorkerDispatchAuthorized [ADVANCE/PASS]
├── 16:WorkCapsuleBuilt:71c238a3b63b WorkCapsuleBuilt [PRESERVE/PASS]
├── 17:CostEvent:f1c8386fd68b CostEvent [PRESERVE/PASS]
├── 18:WorkerReceiptImported:ec9b59bfdd57 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:36968d3ec960 MacroObservationImported [PRESERVE/PASS]
├── 20:OfficialEvaluatorEvidenceImported:ad83cf50d45d OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 21:CandidateAccepted:fcf84f258938 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 22:MarketSettled:a457aebfb372 MarketSettled [PRESERVE/PASS] result=YES
├── 23:RewardDistributed:a6305f3b6899 RewardDistributed [PRESERVE/PASS]
├── 24:PPUTAccounted:16b3399cd548 PPUTAccounted [PRESERVE/PASS] progress=1
└── 25:PredicateEvaluated:29f3f96bbb78 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:244d736a2802` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:047614a3e6e5` WorkCapsuleBuilt [PRESERVE/PASS]
3. `6:WorkerReceiptImported:1f29d17af42d` WorkerReceiptImported [PRESERVE/PASS]
4. `7:MacroObservationImported:9fc09efa6add` MacroObservationImported [PRESERVE/PASS]
5. `9:OfficialEvaluatorEvidenceImported:04660e4b19cb` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `16:WorkCapsuleBuilt:71c238a3b63b` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:ec9b59bfdd57` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:36968d3ec960` MacroObservationImported [PRESERVE/PASS]
9. `20:OfficialEvaluatorEvidenceImported:ad83cf50d45d` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `21:CandidateAccepted:fcf84f258938` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### stage11_case_2

- bundle hash: `sha256:88497d0f1da090c7bfa2c3caaaa2f20ebd2a31ad69c239c82140dd838a2a7ae6`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:9fc89811f1d2edcbc15721c37d509fd6987f1d975732c8c4f8ce3c18f9174845`
- authorization_head: `mu:1776f11bb52521daeb0586cd23485fd7a0edf313aec1c2b60c788f3e3e79adcb`
- accepted_head: `mu:a64951c70215cc6549a39eb3ada69f285d6d8ab704f4659a40a9b5435b761917`
- events: `26`

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
├── 0:SystemConstitutionAccepted:c6b2006ad05a SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:11d0f298d8e8 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:d736e1e56915 AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:4464eed96f30 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:0c422d9c7dcb WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:b626c65cb2d4 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:6408aa6891ae WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:76391d99ac34 MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:3d115c554454 CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:f70bb8ff3f8c OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=CONTEXT_MISSING EVIDENCE
├── 10:FailureNode:35acc35fcb65 FailureNode [PRESERVE/NOT_RUN] class=CONTEXT_MISSING ✗FAIL
├── 11:PPUTAccounted:403e195f05cd PPUTAccounted [PRESERVE/PASS] progress=0
├── 12:FailureCertificate:c694d85baeec FailureCertificate [PRESERVE/PASS] class=CONTEXT_MISSING
├── 13:BroadcastRuleActivated:e97ec1a277d9 BroadcastRuleActivated [ADVANCE/PASS] class=CONTEXT_MISSING
├── 14:RetryAuthorized:ad70e0f934bd RetryAuthorized [ADVANCE/PASS]
├── 15:WorkerDispatchAuthorized:1776f11bb525 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 16:WorkCapsuleBuilt:747474463584 WorkCapsuleBuilt [PRESERVE/PASS]
├── 17:CostEvent:e0de9431a22e CostEvent [PRESERVE/PASS]
├── 18:WorkerReceiptImported:66fa8d5c3842 WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:7c67b9b6025d MacroObservationImported [PRESERVE/PASS]
├── 20:OfficialEvaluatorEvidenceImported:cba66fca7dd6 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 21:CandidateAccepted:a64951c70215 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 22:MarketSettled:df3d6fe51eba MarketSettled [PRESERVE/PASS] result=YES
├── 23:RewardDistributed:47cde30f4cae RewardDistributed [PRESERVE/PASS]
├── 24:PPUTAccounted:32fe23e33702 PPUTAccounted [PRESERVE/PASS] progress=1
└── 25:PredicateEvaluated:9fc89811f1d2 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:11d0f298d8e8` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:0c422d9c7dcb` WorkCapsuleBuilt [PRESERVE/PASS]
3. `6:WorkerReceiptImported:6408aa6891ae` WorkerReceiptImported [PRESERVE/PASS]
4. `7:MacroObservationImported:76391d99ac34` MacroObservationImported [PRESERVE/PASS]
5. `9:OfficialEvaluatorEvidenceImported:f70bb8ff3f8c` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `16:WorkCapsuleBuilt:747474463584` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:66fa8d5c3842` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:7c67b9b6025d` MacroObservationImported [PRESERVE/PASS]
9. `20:OfficialEvaluatorEvidenceImported:cba66fca7dd6` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `21:CandidateAccepted:a64951c70215` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### stage11_case_3

- bundle hash: `sha256:b2c728fff389438027de218e778e52a46aa85a07dadfa5478bdb31a41fe52eb8`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:89f9aea031b858387ef1a36d5e435416c36bdab0b083c518c5f415fffd0f52f5`
- authorization_head: `mu:4d060bc4fc598baa5c71f61a2b9128c3e6e3f0c7bdf6c319a886c7afc91962fa`
- accepted_head: `mu:108b9e61ba38d78621acf30fdbb6c5c1dbf47f3b207e94a3b298fb322f8eb8c1`
- events: `26`

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
├── 0:SystemConstitutionAccepted:c6b2006ad05a SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:cf84698fe53a GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:af0a5a07a7dc AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:c061dec52706 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:53b9a9125905 WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:842b5e4db528 MarketCreated [PRESERVE/PASS]
├── 6:WorkerReceiptImported:94a28ec7d81b WorkerReceiptImported [PRESERVE/PASS]
├── 7:MacroObservationImported:ea827d7bddab MacroObservationImported [PRESERVE/PASS]
├── 8:CostEvent:5e3b0193d58c CostEvent [PRESERVE/PASS]
├── 9:OfficialEvaluatorEvidenceImported:daff4fd7c17d OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=SEMANTIC_FAIL EVIDENCE
├── 10:FailureNode:7c5590af376b FailureNode [PRESERVE/NOT_RUN] class=SEMANTIC_FAIL ✗FAIL
├── 11:PPUTAccounted:60bae55996ac PPUTAccounted [PRESERVE/PASS] progress=0
├── 12:FailureCertificate:c83b5ad821d6 FailureCertificate [PRESERVE/PASS] class=SEMANTIC_FAIL
├── 13:BroadcastRuleActivated:3517bbe2e28b BroadcastRuleActivated [ADVANCE/PASS] class=SEMANTIC_FAIL
├── 14:RetryAuthorized:646d7cb239f0 RetryAuthorized [ADVANCE/PASS]
├── 15:WorkerDispatchAuthorized:4d060bc4fc59 WorkerDispatchAuthorized [ADVANCE/PASS]
├── 16:WorkCapsuleBuilt:36b1070b706e WorkCapsuleBuilt [PRESERVE/PASS]
├── 17:CostEvent:c72e8d6fec67 CostEvent [PRESERVE/PASS]
├── 18:WorkerReceiptImported:0498db75ad8a WorkerReceiptImported [PRESERVE/PASS]
├── 19:MacroObservationImported:647d147d9426 MacroObservationImported [PRESERVE/PASS]
├── 20:OfficialEvaluatorEvidenceImported:9730d74794f3 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 21:CandidateAccepted:108b9e61ba38 CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 22:MarketSettled:2e1fb4cb0a9d MarketSettled [PRESERVE/PASS] result=YES
├── 23:RewardDistributed:e88c32c4c712 RewardDistributed [PRESERVE/PASS]
├── 24:PPUTAccounted:8d9104688e9d PPUTAccounted [PRESERVE/PASS] progress=1
└── 25:PredicateEvaluated:89f9aea031b8 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:cf84698fe53a` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:53b9a9125905` WorkCapsuleBuilt [PRESERVE/PASS]
3. `6:WorkerReceiptImported:94a28ec7d81b` WorkerReceiptImported [PRESERVE/PASS]
4. `7:MacroObservationImported:ea827d7bddab` MacroObservationImported [PRESERVE/PASS]
5. `9:OfficialEvaluatorEvidenceImported:daff4fd7c17d` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `16:WorkCapsuleBuilt:36b1070b706e` WorkCapsuleBuilt [PRESERVE/PASS]
7. `18:WorkerReceiptImported:0498db75ad8a` WorkerReceiptImported [PRESERVE/PASS]
8. `19:MacroObservationImported:647d147d9426` MacroObservationImported [PRESERVE/PASS]
9. `20:OfficialEvaluatorEvidenceImported:9730d74794f3` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
10. `21:CandidateAccepted:108b9e61ba38` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
