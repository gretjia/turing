# Micro Tape Independent Decision DAG Audit

**Verdict**: PASS
**Truth source**: micro_tape_bundle_only
**Bundles**: 11 | **Events**: 212

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
- tape_tip: `mu:cba842066ce0c29649cf95e8aeefc2ecfe61653006cd83d04819196a2acf5945`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
- events: `18`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── a6a9efd #1 GoalStateProposed [PASS]
    └── e3e0c44 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 155bfb9 #3 EvidenceBound [PASS]
        ├── market: 157ec18 #4 MarketCreated [PASS]
        │   ├── 9a35e34 #5 PositionMinted [PASS]
        │   ├── 85f2846 #6 BudgetAllocated [PASS]
        │   └── 95d15f0 #11 MarketSettled [PASS] result=NO
        │       └── 64e3bc5 #12 RewardDistributed [PASS]
        ├── worker: 2a05779 #7 WorkerReceiptImported [PASS]
        │   └── macro: c30f7c9 #8 MacroObservationImported [PASS]
        │       ├── 67072ee #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       ├── cca4d24 #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        │       └── cba8420 #17 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        ├── pput/replay: 5561a61 #13 CostEvent [PASS]
        │   └── 1a77f0d #14 PPUTAccounted [PASS]
        │       └── 78bd257 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: a20c03d #16 OfficialEvaluatorEvidenceImported [PASS] result=FAIL class=OFFICIAL_EVAL_FAIL
            └── (missing)
```

#### Golden Path

1. `a6a9efd` #1 GoalStateProposed [PASS]
2. `e3e0c44` #2 WorkCapsuleBuilt [PASS]
3. `2a05779` #7 WorkerReceiptImported [PASS]
4. `c30f7c9` #8 MacroObservationImported [PASS]
5. `a20c03d` #16 OfficialEvaluatorEvidenceImported [PASS]

### django__django-11790

- bundle hash: `sha256:b1415dab11f9856d8e2ef7ba9c4067a103c3cdf672bafc0eda0d83aee13c9f4c`
- replay valid: `True`
- tape_tip: `mu:457f67e58114de1e1eed41c7279b358996b2e62535da08ea5acbe08d02d34872`
- accepted_head: `mu:457f67e58114de1e1eed41c7279b358996b2e62535da08ea5acbe08d02d34872`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 2728f7f #1 GoalStateProposed [PASS]
    └── d8b6a26 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 095e57c #3 EvidenceBound [PASS]
        ├── market: 275bcf7 #4 MarketCreated [PASS]
        │   ├── 26a98a2 #5 PositionMinted [PASS]
        │   ├── 246d23c #6 BudgetAllocated [PASS]
        │   └── f3933e8 #11 MarketSettled [PASS] result=NO
        │       └── 1d66381 #12 RewardDistributed [PASS]
        ├── worker: 12bd9df #7 WorkerReceiptImported [PASS]
        │   └── macro: cfabf49 #8 MacroObservationImported [PASS]
        │       ├── 6cc897a #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 2ff6a48 #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: ffdd8d4 #13 CostEvent [PASS]
        │   └── e5a3f1c #14 PPUTAccounted [PASS]
        │       └── b5790b1 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 3cfcee4 #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── 0872475 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `2728f7f` #1 GoalStateProposed [PASS]
2. `d8b6a26` #2 WorkCapsuleBuilt [PASS]
3. `12bd9df` #7 WorkerReceiptImported [PASS]
4. `cfabf49` #8 MacroObservationImported [PASS]
5. `3cfcee4` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `0872475` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-11815

- bundle hash: `sha256:f488034f71fdcfbaf7f0225ef651c225f855fe4d6b83a300038c9c6e55a14fb2`
- replay valid: `True`
- tape_tip: `mu:53dd6e3b01302885a6f3d36879f5e641867f13bd20a58cb61fce1eb528d973c5`
- accepted_head: `mu:53dd6e3b01302885a6f3d36879f5e641867f13bd20a58cb61fce1eb528d973c5`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 96283b4 #1 GoalStateProposed [PASS]
    └── 1c48a33 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 182e89c #3 EvidenceBound [PASS]
        ├── market: ec5b05c #4 MarketCreated [PASS]
        │   ├── ea917bc #5 PositionMinted [PASS]
        │   ├── e368be6 #6 BudgetAllocated [PASS]
        │   └── 3b05ee0 #11 MarketSettled [PASS] result=NO
        │       └── 29b62fc #12 RewardDistributed [PASS]
        ├── worker: dcdb6d5 #7 WorkerReceiptImported [PASS]
        │   └── macro: b5666e8 #8 MacroObservationImported [PASS]
        │       ├── b68a3a8 #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 52bce5b #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: c4a2dc9 #13 CostEvent [PASS]
        │   └── e2c02f0 #14 PPUTAccounted [PASS]
        │       └── 7f65e1e #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 8979da6 #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── 0572e76 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `96283b4` #1 GoalStateProposed [PASS]
2. `1c48a33` #2 WorkCapsuleBuilt [PASS]
3. `dcdb6d5` #7 WorkerReceiptImported [PASS]
4. `b5666e8` #8 MacroObservationImported [PASS]
5. `8979da6` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `0572e76` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-11848

- bundle hash: `sha256:2da0fe316b55ef6c99a9ac9b2e61b26837766e4bdd88507c325d42fc806e3375`
- replay valid: `True`
- tape_tip: `mu:671e0e609c7e8be3a37ef76720cbdc3b249f1c0d9e538c02c4a107b2a9bf1b40`
- accepted_head: `mu:671e0e609c7e8be3a37ef76720cbdc3b249f1c0d9e538c02c4a107b2a9bf1b40`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 6c9873b #1 GoalStateProposed [PASS]
    └── e48c8e6 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 54a8224 #3 EvidenceBound [PASS]
        ├── market: 0e873b2 #4 MarketCreated [PASS]
        │   ├── a9fadaf #5 PositionMinted [PASS]
        │   ├── b26c722 #6 BudgetAllocated [PASS]
        │   └── bea220e #11 MarketSettled [PASS] result=NO
        │       └── b72455d #12 RewardDistributed [PASS]
        ├── worker: 5d0a897 #7 WorkerReceiptImported [PASS]
        │   └── macro: b865235 #8 MacroObservationImported [PASS]
        │       ├── d8351ed #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 1d82a27 #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: 42e8dcd #13 CostEvent [PASS]
        │   └── fec38ca #14 PPUTAccounted [PASS]
        │       └── a6c4198 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 4a5c904 #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── 2ef469a #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `6c9873b` #1 GoalStateProposed [PASS]
2. `e48c8e6` #2 WorkCapsuleBuilt [PASS]
3. `5d0a897` #7 WorkerReceiptImported [PASS]
4. `b865235` #8 MacroObservationImported [PASS]
5. `4a5c904` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `2ef469a` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-11880

- bundle hash: `sha256:a6d1844e079b38fdf153f67c5b299024317d7d5d3ce2691828763b68aa2a60da`
- replay valid: `True`
- tape_tip: `mu:0d0478b8165f80e41cedb4c43d58761ef0a7ab0d791a517cc932126b3d842fe7`
- accepted_head: `mu:0d0478b8165f80e41cedb4c43d58761ef0a7ab0d791a517cc932126b3d842fe7`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 1ee0a0c #1 GoalStateProposed [PASS]
    └── 0c6ee5c #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 5adfaaa #3 EvidenceBound [PASS]
        ├── market: ef1f44b #4 MarketCreated [PASS]
        │   ├── 7fc4e2d #5 PositionMinted [PASS]
        │   ├── a86ad06 #6 BudgetAllocated [PASS]
        │   └── 8318356 #11 MarketSettled [PASS] result=NO
        │       └── 70f7ff8 #12 RewardDistributed [PASS]
        ├── worker: 81a8634 #7 WorkerReceiptImported [PASS]
        │   └── macro: 28ed9ce #8 MacroObservationImported [PASS]
        │       ├── a468b05 #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 607d3fc #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: 891ea1a #13 CostEvent [PASS]
        │   └── 8e473c7 #14 PPUTAccounted [PASS]
        │       └── b4b714d #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: d5e037e #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── bcc46b6 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `1ee0a0c` #1 GoalStateProposed [PASS]
2. `0c6ee5c` #2 WorkCapsuleBuilt [PASS]
3. `81a8634` #7 WorkerReceiptImported [PASS]
4. `28ed9ce` #8 MacroObservationImported [PASS]
5. `d5e037e` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `bcc46b6` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-11885

- bundle hash: `sha256:6205209c0ed89c660bbfa42fcae88dc6ff1e3eb120eb0a373c4b45bdb6c4d3e2`
- replay valid: `True`
- tape_tip: `mu:3eb5b63787b0633ef86982c46717a9fb421df5954e458cd30d6d476d3226a4a7`
- accepted_head: `mu:3eb5b63787b0633ef86982c46717a9fb421df5954e458cd30d6d476d3226a4a7`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 321414a #1 GoalStateProposed [PASS]
    └── cf3b24c #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 1ea7562 #3 EvidenceBound [PASS]
        ├── market: 8f60a09 #4 MarketCreated [PASS]
        │   ├── ba50449 #5 PositionMinted [PASS]
        │   ├── ac6bb86 #6 BudgetAllocated [PASS]
        │   └── a36c7b9 #11 MarketSettled [PASS] result=NO
        │       └── 74afd3e #12 RewardDistributed [PASS]
        ├── worker: b477a54 #7 WorkerReceiptImported [PASS]
        │   └── macro: 3e11c55 #8 MacroObservationImported [PASS]
        │       ├── 3f31e9a #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 1f27484 #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: f9ab259 #13 CostEvent [PASS]
        │   └── 0fe3b58 #14 PPUTAccounted [PASS]
        │       └── 3e8e6e4 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: ffbdd3a #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── 8226190 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `321414a` #1 GoalStateProposed [PASS]
2. `cf3b24c` #2 WorkCapsuleBuilt [PASS]
3. `b477a54` #7 WorkerReceiptImported [PASS]
4. `3e11c55` #8 MacroObservationImported [PASS]
5. `ffbdd3a` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `8226190` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-11951

- bundle hash: `sha256:4a9f6b5bc30b6d36920c46781ed603ecc8d258767365c39bfc7c4fc3986cc01e`
- replay valid: `True`
- tape_tip: `mu:18b58be6277b801fc63910c524ce08721af3d30c9ec99019413c88249039f42b`
- accepted_head: `mu:18b58be6277b801fc63910c524ce08721af3d30c9ec99019413c88249039f42b`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── faa6914 #1 GoalStateProposed [PASS]
    └── 83f6cea #2 WorkCapsuleBuilt [PASS]
        ├── evidence: f141f28 #3 EvidenceBound [PASS]
        ├── market: c1a1ce4 #4 MarketCreated [PASS]
        │   ├── ea43b62 #5 PositionMinted [PASS]
        │   ├── 212dc2c #6 BudgetAllocated [PASS]
        │   └── 893b95b #11 MarketSettled [PASS] result=NO
        │       └── 7ea6631 #12 RewardDistributed [PASS]
        ├── worker: 89d90d2 #7 WorkerReceiptImported [PASS]
        │   └── macro: e863780 #8 MacroObservationImported [PASS]
        │       ├── 65ada2e #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── c0ffe3b #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: c6dc23d #13 CostEvent [PASS]
        │   └── 7b2fe2c #14 PPUTAccounted [PASS]
        │       └── dcfe274 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 34a511e #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── d5a97b4 #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `faa6914` #1 GoalStateProposed [PASS]
2. `83f6cea` #2 WorkCapsuleBuilt [PASS]
3. `89d90d2` #7 WorkerReceiptImported [PASS]
4. `e863780` #8 MacroObservationImported [PASS]
5. `34a511e` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `d5a97b4` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

### django__django-11964

- bundle hash: `sha256:4433df9680286f48cd1d56384c4d579ce492b2f9752feb801a096f77dd087853`
- replay valid: `True`
- tape_tip: `mu:a616e84ae23b4aa06a1d9e801f45389190c489663d5fcff5f182968046291ba5`
- accepted_head: `mu:344937f916226ed32a38cbe9866a28f06e5a89d560ec3efa668a1b0ae005ebe2`
- events: `18`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── a6a9efd #1 GoalStateProposed [PASS]
    └── e3e0c44 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: 155bfb9 #3 EvidenceBound [PASS]
        ├── market: 157ec18 #4 MarketCreated [PASS]
        │   ├── 9a35e34 #5 PositionMinted [PASS]
        │   ├── 85f2846 #6 BudgetAllocated [PASS]
        │   └── 198f3c4 #11 MarketSettled [PASS] result=NO
        │       └── c00e3de #12 RewardDistributed [PASS]
        ├── worker: f07b074 #7 WorkerReceiptImported [PASS]
        │   └── macro: cc94fda #8 MacroObservationImported [PASS]
        │       ├── 79cdf5a #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       ├── 9e8cd9d #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        │       └── a616e84 #17 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        ├── pput/replay: 2fdf0b7 #13 CostEvent [PASS]
        │   └── ed5e34c #14 PPUTAccounted [PASS]
        │       └── 884c1dd #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: ffa964d #16 OfficialEvaluatorEvidenceImported [PASS] result=FAIL class=MISSING_OR_EMPTY_PATCH
            └── (missing)
```

#### Golden Path

1. `a6a9efd` #1 GoalStateProposed [PASS]
2. `e3e0c44` #2 WorkCapsuleBuilt [PASS]
3. `f07b074` #7 WorkerReceiptImported [PASS]
4. `cc94fda` #8 MacroObservationImported [PASS]
5. `ffa964d` #16 OfficialEvaluatorEvidenceImported [PASS]

### django__django-11999

- bundle hash: `sha256:c6f7fa5115749fc1e28c9ba32400baa44eb8d584fcbb69d670383d478a70011b`
- replay valid: `True`
- tape_tip: `mu:33f5b532bc6a8ce690b0b6459812991946b8ca9f5a62235efad1a71e46c25a0e`
- accepted_head: `mu:33f5b532bc6a8ce690b0b6459812991946b8ca9f5a62235efad1a71e46c25a0e`
- events: `20`

#### Decision Tree

```
ROOT 344937f #0 SystemConstitutionAccepted [PASS]
└── 64f9208 #1 GoalStateProposed [PASS]
    └── 32556f4 #2 WorkCapsuleBuilt [PASS]
        ├── evidence: ba3ded1 #3 EvidenceBound [PASS]
        ├── market: fba630e #4 MarketCreated [PASS]
        │   ├── efd6ceb #5 PositionMinted [PASS]
        │   ├── e0c48cd #6 BudgetAllocated [PASS]
        │   └── a05a561 #11 MarketSettled [PASS] result=NO
        │       └── c61a0f3 #12 RewardDistributed [PASS]
        ├── worker: 1326a83 #7 WorkerReceiptImported [PASS]
        │   └── macro: 0aa04be #8 MacroObservationImported [PASS]
        │       ├── 93f374f #9 FailureNode [FAIL] class=SEMANTIC_FAILURE ✗FAIL
        │       └── 13cdd20 #10 FailureNode [FAIL] class=STEER_REJECTED ✗FAIL
        ├── pput/replay: 7307a8b #13 CostEvent [PASS]
        │   └── 60147dc #14 PPUTAccounted [PASS]
        │       └── dcf23b8 #15 PredicateEvaluated [NOT_RUN] result=PASS
        └── official: 15b83af #16 OfficialEvaluatorEvidenceImported [PASS] result=PASS
            └── 0db537d #17 CandidateAccepted [PASS] ✓ACCEPT
```

#### Golden Path

1. `64f9208` #1 GoalStateProposed [PASS]
2. `32556f4` #2 WorkCapsuleBuilt [PASS]
3. `1326a83` #7 WorkerReceiptImported [PASS]
4. `0aa04be` #8 MacroObservationImported [PASS]
5. `15b83af` #16 OfficialEvaluatorEvidenceImported [PASS]
6. `0db537d` #17 CandidateAccepted [PASS]

#### Execution Findings

- **INFO** `official_evidence_precedes_accept`: CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.
- **WARN** `market_settled_before_official_evidence`: MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.
- **WARN** `pput_accounted_before_final_accept`: PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.

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
