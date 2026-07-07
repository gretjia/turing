# EVAL_INDEX — INV-1..INV-18 → executable eval + run command

Produced under capsule PART B (B.1) of `PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md`
(branch `hci/software3-20260705`). Maps every invariant row in `SPEC_ECONOMY.md` to
its executable eval, or records why none exists yet (GAP, per the capsule's honesty
rule — a documented absence of a check is a valid finding).

All B.1 property tests live in `crates/turing-economy/tests/spec_evals.rs`, use a
hand-written fixed-seed xorshift64* PRNG (no `proptest`/`quickcheck` dependency;
seeds are literal constants, never `Math.random`/time-based), and run ≥1000
iterations per property (≥2000 for the INV-5/6 money-pump loop).

**Run the full B.1 suite:**
```
cargo test -p turing-economy --test spec_evals
```
(Note: `cargo test -p turing-economy spec_evals` — i.e. `spec_evals` as a bare
positional filter rather than `--test spec_evals` — filters by *test name*
substring across every target, not by file, and matches 0 of these tests since
none of their names contain the literal substring `spec_evals`; it reports
"0 filtered out ... test result: ok" for each target without actually running
this suite. Use `--test spec_evals` to select the binary.)

**Current result (2026-07-07, this exact seed set): 10 passed, 1 failed.**

| INV | Eval | Run command | Result (this run) |
|---|---|---|---|
| INV-1 | `inv1_mint_conservation_property` (`tests/spec_evals.rs`) — 1000 iters, alternating honest mint (public API) vs. hand-forged `PositionMinted` | `cargo test -p turing-economy --test spec_evals inv1_` | GREEN |
| INV-2 | `inv2_settlement_conservation_property` (`tests/spec_evals.rs`) — 1000 iters, random single-market lifecycle (mints + swaps + settle) via public API only | `cargo test -p turing-economy --test spec_evals inv2_` | **RED — CONFIRMED bug candidate** (see below; not a test error) |
| INV-3 | `inv3_global_conservation_property` (`tests/spec_evals.rs`) — 1000 iters, 2-3 markets/tape, sums `MarketConservationReport` fields across all markets | `cargo test -p turing-economy --test spec_evals inv3_` | GREEN in this run. Shares the exact root cause found by INV-2 (see below) — did not happen to trigger with seed `0x3000_0003`'s smaller swap-pay range (1..99), but is not structurally immune; flagged for PART C to re-check with a wider range. Mint-side genesis gap (no `CoinIssued`/balance check on `market.mint`, per SPEC INV-3) lives in `turing-daemons::market_mint_response`, outside this crate's public API surface — no B.1 eval possible here; would need a B.2/daemons-level eval (not written — out of this capsule's stated scope, which is B.1+B.2 skip-B.3 but the concrete deliverable list for this run was `spec_evals.rs` + this index only). |
| INV-4 | **No eval — GAP.** No reputation system exists anywhere in the codebase (confirmed 0 hits for `reputation`/`Reputation` across `turing-economy`/`turing-daemons`/`turing-predicate`). Nothing to test until it lands; SPEC_ECONOMY.md records the `derive_from_tape`/`assert_eq!` pattern to use once it does. | n/a | N/A (not machine-checkable today) |
| INV-5 | `inv5_inv6_k_monotonic_money_pump_property` (`tests/spec_evals.rs`) — 2000 rounds, random side/amount round-trip, fixed seed, re-derives pool from tape each round | `cargo test -p turing-economy --test spec_evals inv5_inv6_` | GREEN |
| INV-6 | Same test as INV-5 (`inv5_inv6_k_monotonic_money_pump_property`) — k-monotonicity under non-negative, floor-rounded operands *is* the rounding-favors-pool / no-money-pump guarantee (see `assert_k_non_decreasing`'s own doc comment, `src/lib.rs:294-300`) | `cargo test -p turing-economy --test spec_evals inv5_inv6_` | GREEN |
| INV-7 | `inv7_bounded_extreme_values_do_not_panic_property` (1000 iters + explicit 0/1-unit boundary cases, magnitudes bounded well under overflow headroom) **and** `inv7_extreme_pool_sizes_overflow_is_a_confirmed_gap` (`#[should_panic]`, pins the confirmed overflow panic at ~1e26-magnitude pools as a named regression marker) | `cargo test -p turing-economy --test spec_evals inv7_` | GREEN (both tests pass — the second passes *because* it expects the panic; if a future fix adds checked arithmetic, that test starts failing, which is the correct signal to flip INV-7 to ENFORCED) |
| INV-8 | `inv8_no_minimum_liquidity_floor_property` — 1000 iters sweeping pool sizes down to the smallest non-zero unit, confirming no floor rejects any of them (only exact zero is rejected) | `cargo test -p turing-economy --test spec_evals inv8_` | GREEN (passes because it documents the *absence* of a floor as a fact — this is the confirmed GAP from `SPEC_ECONOMY.md`, made machine-checkable rather than closed) |
| INV-9 | `inv9_price_never_moves_accepted_head_property` — 1000 iters of random `MarketCreated`/`PriceBroadcast`/`MarketRouter::suggest`, asserting `head_effect=="PRESERVE"`/`can_move_accepted_head==false`/`emits_authorization==false` always | `cargo test -p turing-economy --test spec_evals inv9_` | GREEN |
| INV-10 | **No B.1 eval — this is a static grep-based CI check per `SPEC_ECONOMY.md`** (no economy identifier reachable from `candidate_decision_response`/`derive_candidate_predicate_checks` in `turing-daemons`), not a `turing-economy`-crate runtime test. Existing verification: `grep -n "MarketRouter\|BudgetSuggestion\|PriceSignal" crates/turing-daemons/src/lib.rs` (manually re-verified during PART A; all hits are inside `market_shadow_suggest_response`, never the accept path). | `grep -n "MarketRouter\|BudgetSuggestion\|PriceSignal" crates/turing-daemons/src/lib.rs` | Not re-run in this capsule (out of `turing-economy` scope); PART A's manual verification stands |
| INV-11 | **Covered by existing `turing-predicate` test, not a new B.1 eval** — `market_pput_predicates` (`crates/turing-predicate/tests/predicate_kernel.rs`) already exercises `market_settlement_gate_g_mkt_06`. This capsule's concrete deliverable list (spec_evals.rs + this index) did not include a new `turing-cli`/tape-level B.2 fixture; that remains open for a future capsule if deeper G-MKT-06 fixture coverage (wrong-capsule reference, predicate-set weakening, ordering violation, each as a distinct fixture case) is wanted beyond what `predicate_kernel.rs` already has. | `cargo test -p turing-predicate market_pput_predicates` | Existing test GREEN (not modified by this capsule) |
| INV-12 | `inv12_self_trade_rejection_property` — 1000 iters of randomized same-side/opposite-side/interposed-principal scenarios | `cargo test -p turing-economy --test spec_evals inv12_` | GREEN |
| INV-13 | `inv13_principal_position_cap_property` — 1000 iters, independently predicts accept/refuse from random existing+pending exposure vs. random cap, asserts exact match | `cargo test -p turing-economy --test spec_evals inv13_` | GREEN |
| INV-14 | `inv14_proposer_conflict_property` — 1000 iters, same structure as INV-13 plus the no-op branches (empty `proposer_id`, `trader_id != proposer_id`) and net-NO semantics | `cargo test -p turing-economy --test spec_evals inv14_` | GREEN |
| INV-15 | **No eval — critical GAP**, confirmed in `SPEC_ECONOMY.md`: no difficulty-weighting/reuse-count reputation mechanism exists at all. Not machine-checkable until it lands. | n/a | N/A |
| INV-16 | **No eval — GAP.** `MarketRouter::suggest` is a hard argmax (0 hits for `softmax`/`temperature`/τ in the crate). SPEC_ECONOMY.md records the τ-sweep property test to write once G1 (PART D.3) lands. | n/a | N/A |
| INV-17 | **No eval — GAP.** No settlement→prior backup mechanism exists. | n/a | N/A |
| INV-18 | **No eval — latent GAP.** Trivially holds today only because no τ/price formula exists yet to leak; SPEC_ECONOMY.md flags this as needing a firewall grep/test *before or alongside* INV-16/17 landing, not after. | n/a | N/A |

## CONFIRMED bug candidate surfaced by INV-2/INV-3 (do not fix here — hand off to PART C)

`inv2_settlement_conservation_property` fails deterministically at iteration 638
(seed `0x2000_0002`). Minimal standalone repro (hand-verified independently of the
property loop, see the doc comment directly above the test in `spec_evals.rs`):

- Market created with pool `100`/`109` (`declared_subsidy = 209`).
- Three mints totaling `212` Coin across 3 agents (`minted_coin = 212`).
- Same trader does three sequential `buy_yes` swaps, `pay = 190, 150, 199`, against
  the shrinking pool.
- Settle `YES`.
- `check_conservation` reports `minted_coin=212`, `declared_subsidy=209`,
  `redeemed_coin=834.179012345`, **`holds=false`**.
- But `212 + 209 + (190+150+199 = 539, the swaps' own unaccounted `pay_coin`) = 960
  ≥ 834.179012345` — conservation *does* actually hold once each swap's `pay_coin`
  (itself an implicit CTF mint, per `WalletProjection::from_tape_events`'s own doc
  comment, `src/lib.rs:419-425`) is counted as backing.

**Root cause**: `check_conservation` (`src/lib.rs:526-614`) only accumulates
`EconomyEvent::PositionMinted.coin_in` into `MarketConservationReport.minted_coin`;
it never accumulates `AmmSwapExecuted.pay_coin`, even though the crate's own design
treats a swap's pay side as an implicit mint. **Effect**: a perfectly healthy market
with real swap volume can be reported as `holds=false` ("conservation violated") by
`check_conservation` and therefore by `turing audit market` — a false-positive audit
failure, not an actual Coin leak (the per-wallet ledger already debits `pay_coin`
correctly in `WalletProjection`).

Per this capsule's rule, `src/lib.rs` was **not** modified to fix this — it is left
for PART C (independent CONFIRMED/REFUTED adjudication) and PART D (the actual fix,
almost certainly: accumulate `AmmSwapExecuted.pay_coin` into `minted_coin`, or a
new `implicit_mint_coin` field, inside `check_conservation`'s `AmmSwapExecuted` match
arm at `src/lib.rs:569-578`).
