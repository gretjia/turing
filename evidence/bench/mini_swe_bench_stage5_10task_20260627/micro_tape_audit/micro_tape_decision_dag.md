# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Bundles**: 2 | **Events**: 36

## Aggregate Events

- `BudgetAllocated`: 2
- `CandidateAccepted`: 2
- `CostEvent`: 2
- `EvidenceBound`: 2
- `FailureNode`: 4
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
- `WorkCapsuleBuilt`: 2
- `WorkerReceiptImported`: 2

## Runs

### django__django-12039

- bundle hash: `sha256:de061d0204e987f779caebfc98b72941f3b7fe4d7f30a1cbf259426c863a3030`
- replay valid: `True`
- tape_tip: `mu:7a0726860fb58946a8f3731ae05754d77d6596c5b419f9926fea930d7313c224`
- accepted_head: `mu:7a0726860fb58946a8f3731ae05754d77d6596c5b419f9926fea930d7313c224`
- events: `18`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 607b217 #1 GoalStateProposed [PASS]
    └── 951c810 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 440b6e5 #3 EvidenceBound [PASS]
        ├── market: 8e9be31 #4 MarketCreated [PASS]
        │   ├── 4222bc1 #5 PositionMinted [PASS]
        │   ├── bf25011 #6 BudgetAllocated [PASS]
        │   └── c51f6c4 #11 MarketSettled [PASS] result=NO
        │       └── 95601a4 #12 RewardDistributed [PASS]
        ├── worker: faa2351 #7 WorkerReceiptImported [PASS]
        │   └── macro: a98a65b #8 MacroObservationImported [PASS]
        │       ├── 1511c3f #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 69436d1 #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: 22e47a6 #13 CostEvent [PASS]
        │   └── 50e6feb #14 PPUTAccounted [PASS]
        │       └── 4c1f9d5 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 8ed7564 #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── 7a07268 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `607b217` #1 GoalStateProposed [PASS]
2. `951c810` #2 WorkCapsuleBuilt [PASS]
3. `faa2351` #7 WorkerReceiptImported [PASS]
4. `a98a65b` #8 MacroObservationImported [PASS]
5. `8ed7564` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `7a07268` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-12050

- bundle hash: `sha256:6812ab9f027123474d50ce1ca964e36ca10f1f82d139919de0075f9d71b62a4e`
- replay valid: `True`
- tape_tip: `mu:c4509a8280817848b9d51cf2dd676aea2c02725d95de6b0b0b1a6e6069b5a4ad`
- accepted_head: `mu:c4509a8280817848b9d51cf2dd676aea2c02725d95de6b0b0b1a6e6069b5a4ad`
- events: `18`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 14e4b27 #1 GoalStateProposed [PASS]
    └── 1d3657b #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 9428713 #3 EvidenceBound [PASS]
        ├── market: 72820a3 #4 MarketCreated [PASS]
        │   ├── 160b9c7 #5 PositionMinted [PASS]
        │   ├── 15af614 #6 BudgetAllocated [PASS]
        │   └── 0a8e893 #11 MarketSettled [PASS] result=NO
        │       └── d0a52e1 #12 RewardDistributed [PASS]
        ├── worker: 899625a #7 WorkerReceiptImported [PASS]
        │   └── macro: 56c0205 #8 MacroObservationImported [PASS]
        │       ├── 3c0c7e7 #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── f17d9ab #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: 887d3fe #13 CostEvent [PASS]
        │   └── 4c130fc #14 PPUTAccounted [PASS]
        │       └── c38df25 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 74e426b #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── c4509a8 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `14e4b27` #1 GoalStateProposed [PASS]
2. `1d3657b` #2 WorkCapsuleBuilt [PASS]
3. `899625a` #7 WorkerReceiptImported [PASS]
4. `56c0205` #8 MacroObservationImported [PASS]
5. `74e426b` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `c4509a8` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.
