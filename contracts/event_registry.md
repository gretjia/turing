# Contract: 18-Event Registry (B-3, ADR-0003)

**Status:** PROVISIONAL versioned PROJECT contract, subordinate to the constitution — **NOT law**. Frozen
ONLY after Stage-1 S-7 validates the first E2E loop. Machine-readable source of truth: `event_registry.json`.

## Three classes (down from the >1.0 reference's 6)
| Class | Effect | Touches | Predicate gates advance? |
|---|---|---|---|
| `SOVEREIGN_ACCEPT` | ADVANCE | `accepted_head` (+`tape_tip`) | **yes** (each requires a deterministic Predicate PASS) |
| `PROPOSAL` | PRESERVE | `tape_tip` only | n/a |
| `OBSERVATION` | PRESERVE | `tape_tip` only | n/a |

## The 18 events
**SOVEREIGN_ACCEPT (7):** SystemBootstrapped · ProjectAdopted · GoalStateAccepted · ModulePlanAccepted ·
CandidateAccepted · ExplorationArchived · ExplorationPromoted.
**PROPOSAL (4):** AtomProposed · WorkCapsuleBuilt · WorkerDispatched · HumanSteerInjected.
**OBSERVATION (7):** WorkerReceiptImported · MacroObservationImported · PredicateEvaluated ·
CandidateRejected · FailureNode · ReplayVerified · HandoffGenerated.

## Rules
- **Closed-world:** `unknown_event_type => reject`.
- **head_effect is registry-derived**, never writer-trusted; an envelope whose carried `head_effect`
  disagrees with `registry[type].class` is rejected.
- Names are **append-only**, never renumbered; a new type is a project-level registry amendment.
- `failure_class` (payload axis on `FailureNode`) is orthogonal to `event_type` (envelope axis).

## Illustrative-but-NOT-1.0 names (roadmap only — do not implement as events)
`ModuleMapRatified`, `AtomAuthorized`, `WorkerDispatchAuthorized`, `MacroMergeAuthorization`,
`BroadcastRule*`, `HandoffAccepted`, the 8 AUTHORIZATION-as-ADVANCE events, `EvidenceBound/Tombstoned`,
`ProjectLawAmended`, `BudgetExhausted`, `FailureCertificate`, `OutsideGovernanceObserved`.
In 1.0 these collapse into the 18 (ordinary authorizations are PRESERVE Tape events).
