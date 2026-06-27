# ADR: AMM, CTF, and MarketRouter Shadow Mode

Status: Accepted for P0 Greenfield execution baseline

## Context

The old Greenfield package treated wallet and market as future seams or P0 excludes. The Agent Economy upgrade corrects that: P0 does not need a real-money product or autonomous high-risk market controller, but it does need the market substrate, schemas, event replay, wallet projection, and anti-authority gates from the first day.

The market substrate is internal paper accounting for attention and budget. It has no external money semantics in P0.

## Decision

Implement a Polymarket-like internal market substrate using Conditional Token Framework conservation and a constant-product AMM.

CTF invariant:

```text
1 Coin = 1 YES + 1 NO
```

CPMM invariant:

```text
poolY * poolN = k
```

Buy YES:

```text
dN = payC
dY = - payC * poolY / (payC + poolN)
getY = payC + payC * poolY / (payC + poolN)
priceY = payC / getY
poolY1 = poolY - payC * poolY / (payC + poolN)
poolN1 = poolN + payC
```

Buy NO is symmetric:

```text
dY = payC
dN = - payC * poolN / (payC + poolY)
getN = payC + payC * poolN / (payC + poolY)
priceN = payC / getN
poolN1 = poolN - payC * poolN / (payC + poolY)
poolY1 = poolY + payC
```

All load-bearing market values use fixed units or `decimal_string`; floats are forbidden.

P0 MarketRouter runs in shadow mode:

- CapabilityProfileRouter executes dispatch.
- MarketRouter suggests worker and budget only.
- MarketRouter cannot authorize dispatch.
- MarketRouter cannot authorize macro action.
- MarketRouter cannot move `accepted_head`.

## Consequences

- Market, wallet, and price state are derived from Micro Tape.
- `AgentWalletProjection` is disposable and replay-derived.
- Market settlement references predicate, ground truth, or budget exhaustion evidence.
- Market price can influence exploration, but diversity policy must prevent collapse into the highest-current-price route.
- Real-money semantics, hosted markets, and gamified trading surfaces are out of P0 scope.

## Gates

- `G-MKT-01 ctf_conservation`
- `G-MKT-02 cpmm_invariant`
- `G-MKT-03 market_replay_from_tape`
- `G-MKT-04 wallet_projection_replay_from_tape`
- `G-MKT-05 price_not_predicate`
- `G-MKT-07 marketrouter_shadow_no_authority`
- `G-MKT-08 no_real_money_semantics_in_p0`
