# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Event registry**: `/home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json`
**Canonicalization**: `turingos.jcs.v1-compatible-no-floats-ascii-keys`
**Bundles**: 2 | **Events**: 60

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
- `FailureNode`: 1
- `GoalStateProposed`: 2
- `MacroObservationImported`: 2
- `MarketCreated`: 2
- `MarketSettled`: 2
- `OfficialEvaluatorEvidenceImported`: 2
- `PPUTAccounted`: 2
- `PositionMinted`: 2
- `PredicateEvaluated`: 2
- `RewardDistributed`: 2
- `SystemConstitutionAccepted`: 2
- `ToolActionAuthorized`: 13
- `ToolReceiptAppended`: 13
- `WorkCapsuleBuilt`: 2
- `WorkerDispatchAuthorized`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:0044db5afb946f22eaa5b8c713152aaac16ecf80fc15b6bb6fc38e2ca5e02b47`
- replay valid: `True`
- path class: `accepted_path`
- tape_tip: `mu:ba4b0b159c702316449b7ea223b0625e6418199cdc09b51758f52feda44ea0b4`
- authorization_head: `mu:f280de76e986f7c37a3025c8802f84aed86fa675bf147007d365e72b219c719e`
- accepted_head: `mu:cae4b247c28d9202bbf647452522d0a35c3549188beb37337892126b53333407`
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
├── 0:SystemConstitutionAccepted:133b2ba12c63 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:9b4f025517b2 GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:6899efedf01e AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:59c216042a1b WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:3b4f890ccf9d WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:765cb7bba9c0 MarketCreated [PRESERVE/PASS]
├── 6:PositionMinted:3adf6cdfcabc PositionMinted [PRESERVE/PASS]
├── 7:ToolActionAuthorized:27b9703187b2 ToolActionAuthorized [ADVANCE/PASS]
├── 8:ToolReceiptAppended:6726cbea0eba ToolReceiptAppended [PRESERVE/PASS]
├── 9:ToolActionAuthorized:bf5353680055 ToolActionAuthorized [ADVANCE/PASS]
├── 10:ToolReceiptAppended:c76ee99607ce ToolReceiptAppended [PRESERVE/PASS]
├── 11:ToolActionAuthorized:7655e414ee4b ToolActionAuthorized [ADVANCE/PASS]
├── 12:ToolReceiptAppended:8f66c2ce7f32 ToolReceiptAppended [PRESERVE/PASS]
├── 13:ToolActionAuthorized:92a490902acd ToolActionAuthorized [ADVANCE/PASS]
├── 14:ToolReceiptAppended:b07eebb8235f ToolReceiptAppended [PRESERVE/PASS]
├── 15:ToolActionAuthorized:e1d7ac5920ab ToolActionAuthorized [ADVANCE/PASS]
├── 16:ToolReceiptAppended:2d2697a89522 ToolReceiptAppended [PRESERVE/PASS]
├── 17:ToolActionAuthorized:f280de76e986 ToolActionAuthorized [ADVANCE/PASS]
├── 18:ToolReceiptAppended:8f0d1c3d56e5 ToolReceiptAppended [PRESERVE/PASS]
├── 19:BudgetAllocated:f0834c4a9e83 BudgetAllocated [PRESERVE/PASS]
├── 20:WorkerReceiptImported:8bc04744d7d6 WorkerReceiptImported [PRESERVE/PASS]
├── 21:MacroObservationImported:bdaeb1cff835 MacroObservationImported [PRESERVE/PASS]
├── 22:CostEvent:ed90858928f8 CostEvent [PRESERVE/PASS]
├── 23:OfficialEvaluatorEvidenceImported:94379d05db35 OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=PASS EVIDENCE
├── 24:CandidateAccepted:cae4b247c28d CandidateAccepted [ADVANCE/PASS] ✓ACCEPT
├── 25:MarketSettled:d60a8dc99c96 MarketSettled [PRESERVE/PASS] result=YES
├── 26:RewardDistributed:2246614e9fd8 RewardDistributed [PRESERVE/PASS]
├── 27:PPUTAccounted:832de7faf8e4 PPUTAccounted [PRESERVE/PASS] progress=1
└── 28:PredicateEvaluated:ba4b0b159c70 PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

1. `1:GoalStateProposed:9b4f025517b2` GoalStateProposed [PRESERVE/PASS]
2. `4:WorkCapsuleBuilt:3b4f890ccf9d` WorkCapsuleBuilt [PRESERVE/PASS]
3. `20:WorkerReceiptImported:8bc04744d7d6` WorkerReceiptImported [PRESERVE/PASS]
4. `21:MacroObservationImported:bdaeb1cff835` MacroObservationImported [PRESERVE/PASS]
5. `23:OfficialEvaluatorEvidenceImported:94379d05db35` OfficialEvaluatorEvidenceImported [PRESERVE/PASS]
6. `24:CandidateAccepted:cae4b247c28d` CandidateAccepted [ADVANCE/PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.

### django__django-12050

- bundle hash: `sha256:9f64731b45c18a5bb04f983d7484fbdfe91c7fb34abdb3283b853adb011d7ce5`
- replay valid: `True`
- path class: `failed_path`
- tape_tip: `mu:2093d806c34fb02e4bd7d21ab8532a291211945fbb6b15d6e3decc422ccd5a12`
- authorization_head: `mu:57d13a297f28fe3fd684f401fc1c8bd5bbefa4c24ac61f974c4e7911da3580d5`
- accepted_head: `mu:5f513416dc68bc4da51a6b2af979d90e8f2e9ba85b0b2ef36b3e5606c13d85cf`
- events: `31`

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
├── 0:SystemConstitutionAccepted:5f513416dc68 SystemConstitutionAccepted [ADVANCE/PASS]
├── 1:GoalStateProposed:cfa4bb0303ed GoalStateProposed [PRESERVE/PASS]
├── 2:AtomAuthorized:7e2c594b77ec AtomAuthorized [ADVANCE/PASS]
├── 3:WorkerDispatchAuthorized:f53e5d5e6ddb WorkerDispatchAuthorized [ADVANCE/PASS]
├── 4:WorkCapsuleBuilt:032938e4562f WorkCapsuleBuilt [PRESERVE/PASS]
├── 5:MarketCreated:2366f33e9ea6 MarketCreated [PRESERVE/PASS]
├── 6:PositionMinted:c27b016f318c PositionMinted [PRESERVE/PASS]
├── 7:ToolActionAuthorized:323f4b749282 ToolActionAuthorized [ADVANCE/PASS]
├── 8:ToolReceiptAppended:5219eefbdbd0 ToolReceiptAppended [PRESERVE/PASS]
├── 9:ToolActionAuthorized:a876b39aa5e7 ToolActionAuthorized [ADVANCE/PASS]
├── 10:ToolReceiptAppended:5ccdd3b42d75 ToolReceiptAppended [PRESERVE/PASS]
├── 11:ToolActionAuthorized:a5cd16db7c3e ToolActionAuthorized [ADVANCE/PASS]
├── 12:ToolReceiptAppended:48f60cd3c7b5 ToolReceiptAppended [PRESERVE/PASS]
├── 13:ToolActionAuthorized:73610f839566 ToolActionAuthorized [ADVANCE/PASS]
├── 14:ToolReceiptAppended:4876c3c2dce3 ToolReceiptAppended [PRESERVE/PASS]
├── 15:ToolActionAuthorized:55ab7888bae6 ToolActionAuthorized [ADVANCE/PASS]
├── 16:ToolReceiptAppended:4bec675e6e87 ToolReceiptAppended [PRESERVE/PASS]
├── 17:ToolActionAuthorized:4f4893f674a6 ToolActionAuthorized [ADVANCE/PASS]
├── 18:ToolReceiptAppended:5290ef8fa57c ToolReceiptAppended [PRESERVE/PASS]
├── 19:ToolActionAuthorized:57d13a297f28 ToolActionAuthorized [ADVANCE/PASS]
├── 20:ToolReceiptAppended:747de58ec66f ToolReceiptAppended [PRESERVE/PASS]
├── 21:BudgetAllocated:406616f0adfa BudgetAllocated [PRESERVE/PASS]
├── 22:WorkerReceiptImported:02548f028bb6 WorkerReceiptImported [PRESERVE/PASS]
├── 23:MacroObservationImported:40cb272c3c4b MacroObservationImported [PRESERVE/PASS]
├── 24:CostEvent:d3ed33734c3f CostEvent [PRESERVE/PASS]
├── 25:OfficialEvaluatorEvidenceImported:4861ba2710ac OfficialEvaluatorEvidenceImported [PRESERVE/PASS] result=FAIL class=PATCH_APPLIES_BUT_WRONG EVIDENCE
├── 26:FailureNode:167a32515639 FailureNode [PRESERVE/NOT_RUN] class=PATCH_APPLIES_BUT_WRONG ✗FAIL
├── 27:MarketSettled:7d179a067428 MarketSettled [PRESERVE/PASS] result=NO
├── 28:RewardDistributed:ab64c2b32e3b RewardDistributed [PRESERVE/PASS]
├── 29:PPUTAccounted:95168af73b04 PPUTAccounted [PRESERVE/PASS] progress=0
└── 30:PredicateEvaluated:2093d806c34f PredicateEvaluated [PRESERVE/NOT_RUN] result=PASS
```

#### Accepted Path

_No accepted path: this run is failed or incomplete._
