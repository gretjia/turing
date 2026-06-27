# ADR: Price Is Not Truth

Status: Accepted for P0 Greenfield execution baseline

## Context

Agent Economy markets compress distributed opportunity cost. They are useful for routing attention, selecting candidate branches, and suggesting budgets. They are not correctness proofs.

The runtime already has sovereign truth boundaries:

- Predicate decides correctness.
- Signature decides human authorization.
- Tape preserves all state.
- Projection, dashboard, market state, and wallet state are rebuildable views.

If price is allowed to advance truth, the system becomes vulnerable to local-optimum collapse, market manipulation, and reward hacking.

## Decision

Price is a statistical signal only.

Market events must have `head_effect: PRESERVE` unless a later explicit registry amendment says otherwise. The following event classes cannot advance `accepted_head`:

- `MarketCreated`
- `MarketLiquidityAdded`
- `PositionMinted`
- `AMMSwapExecuted`
- `AgentBidSubmitted`
- `BudgetAllocated`
- `MarketPriceBroadcast`
- `MarketSettled`
- `RewardDistributed`
- `MarketRouterSuggestion`

Market settlement must reference predicate or ground-truth settlement evidence. A high YES price is not evidence of completion, and a low price is not evidence of impossibility.

## Consequences

- MarketRouter can suggest allocation in P0 shadow mode only.
- CapabilityProfileRouter remains the dispatch executor in P0.
- Market prices may be broadcast as bounty or attention signals after shielding.
- Predicate failure still appends failure state even if the market favored the branch.
- UI, logs, handoff, and projection copy must not imply market price equals acceptance.

## Gates

- `G-MKT-03 market_replay_from_tape`
- `G-MKT-05 price_not_predicate`
- `G-MKT-06 market_settlement_requires_predicate`
- `G-MKT-07 marketrouter_shadow_no_authority`
- `G-CONST-01 tape_reconstructs_all_state`
