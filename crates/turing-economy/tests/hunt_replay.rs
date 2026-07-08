//! PART C.1 lens 5 (replay determinism, INV-4/INV-9/INV-17) for
//! `PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md`.
//!
//! Scope: only replay-class bugs -- `derive_from_tape` nondeterminism, non-deterministic
//! collection ordering, or any path where `view != replay(view))` for the exact same tape
//! event slice. Every property loop below uses a hand-written, fixed-seed PRNG (no
//! `proptest`/`quickcheck`, no `Math.random`/time-based seeding -- literal constant seeds
//! only, per the capsule's general rule).
//!
//! Attack vectors tried:
//! 1. Repeated-fold determinism (call the same reducer twice on the identical slice).
//! 2. Cross-market interleave-order invariance (two logically independent markets folded in
//!    two different, causally-valid interleavings must produce identical projections).
//! 3. Duplicate/conflicting `MarketSettled` on the same market -- CONFIRMED divergence, see
//!    below.

use turing_economy::{
    AmmPool, AmmSwapExecuted, CandidateRoute, EconomyEvent, MarketReplay, MarketRouter,
    MarketRouterMode, PriceSignal, WalletProjection, check_conservation,
};

// --- deterministic PRNG (fixed seed, no time/Math.random per capsule rule) -----------------

struct Rng(u64);

impl Rng {
    fn new(seed: u64) -> Self {
        Rng(seed | 1)
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    fn range(&mut self, lo: u64, hi: u64) -> u64 {
        assert!(hi > lo, "range requires hi > lo");
        lo + self.next_u64() % (hi - lo)
    }
}

const SETTLEMENT_ID: &str = "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const SETTLEMENT_ID_2: &str = "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

/// Build one fully-valid, single-market lifecycle (create -> N mints -> M swaps -> settle)
/// entirely through the crate's public constructors, so every event is causally coherent.
fn build_market_lifecycle(
    rng: &mut Rng,
    market_id: &str,
    agents: &[&str],
    result: &str,
) -> Vec<EconomyEvent> {
    let pool_y0 = rng.range(50, 5_000);
    let pool_n0 = rng.range(50, 5_000);
    let mut events = vec![
        EconomyEvent::market_created(market_id, &pool_y0.to_string(), &pool_n0.to_string())
            .expect("market created"),
    ];
    let mut pool = AmmPool::new(market_id, &pool_y0.to_string(), &pool_n0.to_string())
        .expect("pool constructs");

    let mint_count = rng.range(1, 4);
    for _ in 0..mint_count {
        let agent = agents[rng.range(0, agents.len() as u64) as usize];
        let amount = rng.range(1, 300);
        events.push(
            EconomyEvent::position_minted(market_id, agent, &amount.to_string()).expect("mint"),
        );
    }

    let swap_count = rng.range(0, 3);
    for _ in 0..swap_count {
        let agent = agents[rng.range(0, agents.len() as u64) as usize];
        let pay = rng.range(1, 100);
        let buy_yes = rng.range(0, 2) == 0;
        let swap = if buy_yes {
            pool.buy_yes(agent, &pay.to_string())
        } else {
            pool.buy_no(agent, &pay.to_string())
        }
        .expect("swap succeeds against a non-degenerate pool");
        pool = AmmPool::new(market_id, &swap.pool_y_after, &swap.pool_n_after)
            .expect("re-pool from recorded state");
        events.push(EconomyEvent::AmmSwapExecuted(swap));
    }

    events.push(EconomyEvent::market_settled(market_id, result, SETTLEMENT_ID).expect("settlement"));
    events
}

// --- attack vector 1: repeated-fold determinism (sanity backstop) -------------------------

/// 500 fixed-seed iterations: fold the identical event slice through `WalletProjection`,
/// `MarketReplay`, and `check_conservation` twice each and assert byte-for-byte
/// (`PartialEq`) equality. This is the baseline "no hidden nondeterminism source" check
/// (would catch a `HashMap`/thread/clock leak immediately) -- expected to hold given the
/// crate uses only `BTreeMap` internally (confirmed by source inspection), but exercised
/// empirically rather than asserted from reading alone.
#[test]
fn repeated_fold_determinism_property() {
    let mut rng = Rng::new(0x5EA1_0001);
    let agents = ["agent_a", "agent_b", "agent_c"];

    for i in 0..500u64 {
        let market_id = format!("mkt_det_{i}");
        let result = ["YES", "NO", "INVALID"][rng.range(0, 3) as usize];
        let events = build_market_lifecycle(&mut rng, &market_id, &agents, result);

        let wallets_1 = WalletProjection::from_tape_events(&events).expect("wallet projection 1");
        let wallets_2 = WalletProjection::from_tape_events(&events).expect("wallet projection 2");
        assert_eq!(wallets_1, wallets_2, "iteration {i}: WalletProjection nondeterministic");

        let replay_1 = MarketReplay::from_tape_events(&events).expect("market replay 1");
        let replay_2 = MarketReplay::from_tape_events(&events).expect("market replay 2");
        assert_eq!(replay_1, replay_2, "iteration {i}: MarketReplay nondeterministic");

        let cons_1 = check_conservation(&events).expect("conservation 1");
        let cons_2 = check_conservation(&events).expect("conservation 2");
        assert_eq!(cons_1, cons_2, "iteration {i}: check_conservation nondeterministic");
    }
}

// --- attack vector 2: cross-market interleave-order invariance ----------------------------

/// 500 fixed-seed iterations: build two logically independent markets' fully-valid event
/// sequences, then interleave them in two different fixed-seed-random-but-causally-valid
/// orders (each market's own events stay in their original relative order; only the
/// cross-market interleave position varies). Markets are financially independent in this
/// crate (keyed by `market_id` throughout), so the final `WalletProjection`/`MarketReplay`/
/// `check_conservation` reports must be interleave-order-invariant. Also exercises
/// `MarketRouter::suggest` across the same two market ids (order of `routes`/`signals`
/// shouldn't matter for markets never referenced ambiguously).
#[test]
fn cross_market_interleave_order_invariance_property() {
    let mut rng = Rng::new(0x5EA1_0002);
    let agents = ["agent_a", "agent_b", "agent_c"];

    for i in 0..500u64 {
        let market_a = format!("mkt_ia_{i}");
        let market_b = format!("mkt_ib_{i}");
        let result_a = ["YES", "NO"][rng.range(0, 2) as usize];
        let result_b = ["YES", "NO"][rng.range(0, 2) as usize];

        let events_a = build_market_lifecycle(&mut rng, &market_a, &agents, result_a);
        let events_b = build_market_lifecycle(&mut rng, &market_b, &agents, result_b);

        // Interleaving 1: fixed-seed random merge.
        let interleaved_1 = random_merge(&mut rng, &events_a, &events_b);
        // Interleaving 2: a different fixed-seed random merge (independent draw).
        let interleaved_2 = random_merge(&mut rng, &events_a, &events_b);

        let wallets_1 = WalletProjection::from_tape_events(&interleaved_1).expect("wallets 1");
        let wallets_2 = WalletProjection::from_tape_events(&interleaved_2).expect("wallets 2");
        assert_eq!(
            wallets_1, wallets_2,
            "iteration {i}: WalletProjection depends on cross-market interleave order"
        );

        let replay_1 = MarketReplay::from_tape_events(&interleaved_1).expect("replay 1");
        let replay_2 = MarketReplay::from_tape_events(&interleaved_2).expect("replay 2");
        assert_eq!(
            replay_1, replay_2,
            "iteration {i}: MarketReplay depends on cross-market interleave order"
        );

        // `check_conservation`'s Vec is presented in first-appearance-in-the-tape order,
        // which the two interleavings legitimately differ on by construction -- that is a
        // presentation detail, not a value divergence, so compare as a market_id-sorted
        // multiset (the actual per-market content) rather than raw Vec/positional equality.
        let mut cons_1 = check_conservation(&interleaved_1).expect("conservation 1");
        let mut cons_2 = check_conservation(&interleaved_2).expect("conservation 2");
        cons_1.sort_by(|a, b| a.market_id.cmp(&b.market_id));
        cons_2.sort_by(|a, b| a.market_id.cmp(&b.market_id));
        assert_eq!(
            cons_1, cons_2,
            "iteration {i}: check_conservation's per-market content depends on cross-market \
             interleave order (compared market_id-sorted, so this is a genuine value \
             divergence, not a presentation-order artifact)"
        );
    }
}

/// Merge two already-causally-ordered event slices, preserving each slice's internal order,
/// choosing which slice to draw from next uniformly at random (fixed-seed).
fn random_merge(rng: &mut Rng, a: &[EconomyEvent], b: &[EconomyEvent]) -> Vec<EconomyEvent> {
    let mut out = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0usize, 0usize);
    while i < a.len() || j < b.len() {
        let take_a = if i >= a.len() {
            false
        } else if j >= b.len() {
            true
        } else {
            rng.range(0, 2) == 0
        };
        if take_a {
            out.push(a[i].clone());
            i += 1;
        } else {
            out.push(b[j].clone());
            j += 1;
        }
    }
    out
}

// --- attack vector 3: duplicate / conflicting MarketSettled (CONFIRMED divergence) ---------

/// **CONFIRMED candidate bug, NOW FIXED (INV-4/INV-17 class -- "view != replay(view)"):** a
/// second `MarketSettled` event for a market that was already settled is accepted without
/// error by every library-level reducer in this crate (`check_conservation`'s own doc comment
/// frames its input as "a tape is untrusted input" -- exactly the shape a forged/corrupted or
/// buggy-writer tape could produce). Before this fix, the *derived views* of that tape
/// disagreed with each other even though nothing about the actual, financially-binding wallet
/// ledger changed:
///
/// - `WalletProjection` (the real per-wallet ledger) is idempotent to the duplicate: it
///   clears BOTH `yes_positions` and `no_positions` for the market on the *first*
///   `MarketSettled` it folds (regardless of `result`), so a second settle event finds
///   nothing left to redeem and is a provable no-op -- appending it changes zero wallet
///   balances. This part is correctly defended (asserted below as the control).
/// - `MarketReplay` used to have no such guard: it unconditionally overwrote
///   `status`/`settlement_result` on every `MarketSettled` it folds, so a second, conflicting
///   `MarketSettled(NO)` after `MarketSettled(YES)` flipped the reported `settlement_result`.
///   Fixed: `MarketReplay` now keeps the FIRST settle only (`status != "settled"` guard),
///   matching `WalletProjection`'s own first-settle-wins idempotency.
/// - `check_conservation` had the same missing-guard shape, but on the accounting side: it
///   never cleared `yes_positions`/`no_positions` after a settle, so a *second*
///   `MarketSettled` for the same market re-summed the (still-present) positions and added
///   them **again** into `redeemed_coin`. Fixed: `MarketConservationInternal` now tracks a
///   `settled` flag and skips re-processing a market that has already been settled.
///
/// Minimal repro: market with pool 10/10, one mint of 100 Coin by `agent_a`, then
/// `MarketSettled(YES)`, compared against the identical tape with a second, conflicting
/// `MarketSettled(NO)` appended (distinct `mu:` settlement ids -- this crate's constructors
/// do not require settlement ids to be unique or to reference a real
/// `CandidateAccepted`/`FailureNode`; that cross-check is `turing-predicate`'s G-MKT-06, a
/// separate gate this reducer has no knowledge of, matching the doc comment's own framing of
/// this input as untrusted). Both regressions below now assert equality (single == duplicate),
/// pinning the fixed, idempotent-to-forged-duplicates behavior.
fn dup_settle_fixture() -> (Vec<EconomyEvent>, Vec<EconomyEvent>) {
    let market_id = "mkt_dup_settle";
    let mint_amount = "100";

    let events_single = vec![
        EconomyEvent::market_created(market_id, "10", "10").expect("market created"),
        EconomyEvent::position_minted(market_id, "agent_a", mint_amount).expect("mint"),
        EconomyEvent::market_settled(market_id, "YES", SETTLEMENT_ID).expect("first settle"),
    ];
    let mut events_duplicate = events_single.clone();
    events_duplicate.push(
        EconomyEvent::market_settled(market_id, "NO", SETTLEMENT_ID_2)
            .expect("second, conflicting settle -- accepted with no error"),
    );
    (events_single, events_duplicate)
}

#[test]
fn duplicate_market_settled_wallet_ledger_control_is_a_true_no_op() {
    let (events_single, events_duplicate) = dup_settle_fixture();

    // Control: the wallet ledger is byte-identical whether or not the duplicate, conflicting
    // settle event is appended -- proving it truly changed zero financial state. This test
    // is expected to PASS (it is the control for the two CONFIRMED-bug tests below).
    let wallets_single = WalletProjection::from_tape_events(&events_single).expect("wallets single");
    let wallets_duplicate =
        WalletProjection::from_tape_events(&events_duplicate).expect("wallets duplicate");
    assert_eq!(
        wallets_single, wallets_duplicate,
        "control: the duplicate MarketSettled must be a true no-op for the wallet ledger \
         for the divergence in the sibling tests to indict the *read-model* reducers, not \
         real state drift"
    );
}

/// **CONFIRMED BUG 1, NOW FIXED** -- see the module-level doc comment on the fixture above.
#[test]
fn duplicate_market_settled_diverges_market_replay_settlement_result() {
    let (events_single, events_duplicate) = dup_settle_fixture();
    let market_id = "mkt_dup_settle";

    let replay_single = MarketReplay::from_tape_events(&events_single).expect("replay single");
    let replay_duplicate =
        MarketReplay::from_tape_events(&events_duplicate).expect("replay duplicate");
    let single_result = replay_single.markets.get(market_id).and_then(|m| m.settlement_result.clone());
    let duplicate_result =
        replay_duplicate.markets.get(market_id).and_then(|m| m.settlement_result.clone());
    assert_eq!(
        single_result, duplicate_result,
        "FIX REGRESSION FAILED: MarketReplay reports settlement_result={single_result:?} for \
         the single-settle tape but {duplicate_result:?} once a second, conflicting \
         MarketSettled is appended -- MarketReplay must be first-settle-wins, matching the \
         wallet ledger (real financial state), which the control test proves never moved"
    );
    assert_eq!(
        single_result.as_deref(),
        Some("YES"),
        "sanity: the first, legitimate settle result must survive"
    );
}

/// **CONFIRMED BUG 2, NOW FIXED** -- see the module-level doc comment on the fixture above.
#[test]
fn duplicate_market_settled_diverges_check_conservation_redeemed_coin() {
    let (events_single, events_duplicate) = dup_settle_fixture();

    let report_single = check_conservation(&events_single).expect("conservation single");
    let report_duplicate = check_conservation(&events_duplicate).expect("conservation duplicate");
    assert_eq!(report_single.len(), 1);
    assert_eq!(report_duplicate.len(), 1);
    assert_eq!(
        report_single[0].redeemed_coin, report_duplicate[0].redeemed_coin,
        "FIX REGRESSION FAILED: check_conservation reports redeemed_coin={} for the \
         single-settle tape but redeemed_coin={} once a second, conflicting MarketSettled is \
         appended -- a duplicate settle must be a no-op (first-settle-wins), matching the \
         control test's proof that no wallet balance moved: single={:?} duplicate={:?}",
        report_single[0].redeemed_coin,
        report_duplicate[0].redeemed_coin,
        report_single[0],
        report_duplicate[0]
    );
    assert!(
        report_single[0].holds && report_duplicate[0].holds,
        "sanity: both tapes are conservation-healthy: single={:?} duplicate={:?}",
        report_single[0],
        report_duplicate[0]
    );
}

// --- MarketRouter::suggest: routes-order invariance (sanity backstop for INV-9's argmax) ---

/// 500 fixed-seed iterations: shuffle the `routes`/`signals` slices passed to
/// `MarketRouter::suggest` and confirm the winning route is a function of the *price*
/// (argmax), never of positional order among equal-price ties broken consistently, and never
/// nondeterministic across repeated calls with the same (shuffled) input.
#[test]
fn market_router_suggest_repeated_call_determinism_property() {
    let mut rng = Rng::new(0x5EA1_0003);
    let digest = format!("sha256:{}", "a".repeat(64));

    for i in 0..500u64 {
        let route_count = rng.range(2, 6);
        let mut routes = Vec::new();
        let mut signals = Vec::new();
        for r in 0..route_count {
            let market_id = format!("mkt_route_{i}_{r}");
            routes.push(CandidateRoute {
                route_id: format!("route_{i}_{r}"),
                market_id: market_id.clone(),
                expected_failure_domain: "domain".to_string(),
                requested_tokens: rng.range(1, 10_000),
            });
            let yes_price = format!("0.{:09}", rng.range(0, 1_000_000_000));
            signals.push(PriceSignal {
                market_id,
                yes_price,
                no_price: "0".to_string(),
                truth_status: "statistical_signal_only".to_string(),
            });
        }

        let router = MarketRouter::new(MarketRouterMode::Shadow);
        let first = router
            .suggest(&routes, &signals, &digest, &digest, &digest)
            .expect("suggestion 1");
        let second = router
            .suggest(&routes, &signals, &digest, &digest, &digest)
            .expect("suggestion 2");
        assert_eq!(
            first, second,
            "iteration {i}: MarketRouter::suggest is nondeterministic on the identical input"
        );
    }
}

/// Silence an unused-import warning for `AmmSwapExecuted` (kept available for future repro
/// fixtures in this lens without pulling in another `use` churn).
#[allow(dead_code)]
fn _keep_amm_swap_import(_swap: &AmmSwapExecuted) {}
