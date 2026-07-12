//! PART B (B.1) of `PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md`: one executable eval per
//! INV row in `crates/turing-economy/SPEC_ECONOMY.md` that is checkable from this crate
//! alone (INV-1/2/3/5/6/7/8/9/12/13/14). Every property loop below uses a **hand-written,
//! fixed-seed PRNG** (xorshift64* — no `proptest`/`quickcheck` dependency exists in this
//! workspace, and the capsule's general rule forbids `Math.random`/time-based seeding: the
//! seeds are literal constants so every run is bit-for-bit reproducible).
//!
//! These evals are written to test the SPEC's *stated invariant*, not to rubber-stamp
//! current behavior. Where `SPEC_ECONOMY.md` already documents a confirmed GAP (INV-7,
//! INV-8), the corresponding eval is written so it stays green while still making the gap
//! machine-checkable: INV-7 splits into a bounded-safe property test (genuinely green) plus
//! a `#[should_panic]` test that *pins* the known overflow panic as an explicit, named
//! regression marker (if a future fix adds checked arithmetic, that test starts failing —
//! which is the correct signal to convert it to an `Ok`/`Err` assertion and close the GAP);
//! INV-8 documents the absence of a minimum-liquidity floor as a directly observable,
//! passing fact about today's `AmmPool::new`.

use turing_economy::{
    AmmPool, AmmSwapExecuted, CandidateRoute, EconomyEvent, MarketRouter, MarketRouterMode,
    PositionMinted, PriceBroadcast, PriceSignal, check_conservation, check_principal_position_cap,
    check_proposer_conflict, check_self_trade, verify_swap_post_trade_invariant,
};

// --- deterministic PRNG (fixed seed, no time/Math.random per capsule rule) -----------------

/// xorshift64* — a hand-written, fixed-seed PRNG. Every call site below passes a literal
/// constant seed, so every property loop is exactly reproducible across runs/machines.
struct Rng(u64);

impl Rng {
    fn new(seed: u64) -> Self {
        Rng(seed | 1) // xorshift requires a non-zero state
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// Random `u64` in `[lo, hi)`.
    fn range(&mut self, lo: u64, hi: u64) -> u64 {
        assert!(hi > lo, "range requires hi > lo");
        lo + self.next_u64() % (hi - lo)
    }
}

/// Random non-negative `decimal_string` (SCALE=1e9 fixed-point) with whole part in
/// `[min_whole, max_whole]` and a random fractional part.
fn rand_decimal(rng: &mut Rng, min_whole: u64, max_whole: u64) -> String {
    let whole = rng.range(min_whole, max_whole + 1);
    let frac = rng.range(0, 1_000_000_000);
    if frac == 0 {
        whole.to_string()
    } else {
        format!("{whole}.{frac:09}")
    }
}

const SCALE: i128 = 1_000_000_000;

/// Parses a `decimal_string` into exact integer "units" for lossless comparison, without
/// float parsing (which could mask a genuine sub-epsilon money-pump leak).
fn parse_units_exact(raw: &str) -> i128 {
    let mut split = raw.split('.');
    let whole: i128 = split.next().unwrap_or("0").parse().expect("whole part");
    let fraction = match split.next() {
        Some(fraction) => {
            let padded = format!("{fraction:0<9}");
            padded[..9].parse::<i128>().expect("fraction part")
        }
        None => 0,
    };
    whole * SCALE + fraction
}

/// Hand-forged `AmmSwapExecuted` fixture for the D5 defense tests (INV-12/13/14), which
/// operate purely on tape facts (`market_id`/`trader_id`/`side`/`get_y`/`get_n`) and never
/// re-derive an AMM pool -- only those fields need to be meaningful; the rest are
/// placeholders that satisfy `parse_non_negative` where relevant.
fn fixture_swap(market_id: &str, trader_id: &str, side: &str) -> EconomyEvent {
    EconomyEvent::AmmSwapExecuted(AmmSwapExecuted {
        schema_id: "amm_swap_executed.v1".to_string(),
        market_id: market_id.to_string(),
        trader_id: trader_id.to_string(),
        side: side.to_string(),
        pay_coin: "1".to_string(),
        d_y: "0".to_string(),
        d_n: "0".to_string(),
        get_y: "0".to_string(),
        get_n: "0".to_string(),
        pool_y_before: "1".to_string(),
        pool_n_before: "1".to_string(),
        pool_y_after: "1".to_string(),
        pool_n_after: "1".to_string(),
        invariant_k_before: "1".to_string(),
        invariant_k_after: "1".to_string(),
        effective_price: "1".to_string(),
    })
}

/// Same fixture, but with caller-controlled `get_y`/`get_n` (the two fields
/// `principal_position` actually aggregates), for the position-cap / proposer-conflict
/// property tests.
fn fixture_swap_with_gets(market_id: &str, trader_id: &str, get_y: &str, get_n: &str) -> EconomyEvent {
    EconomyEvent::AmmSwapExecuted(AmmSwapExecuted {
        schema_id: "amm_swap_executed.v1".to_string(),
        market_id: market_id.to_string(),
        trader_id: trader_id.to_string(),
        side: "BUY_YES".to_string(),
        pay_coin: "0".to_string(),
        d_y: "0".to_string(),
        d_n: "0".to_string(),
        get_y: get_y.to_string(),
        get_n: get_n.to_string(),
        pool_y_before: "1".to_string(),
        pool_n_before: "1".to_string(),
        pool_y_after: "1".to_string(),
        pool_n_after: "1".to_string(),
        invariant_k_before: "1".to_string(),
        invariant_k_after: "1".to_string(),
        effective_price: "1".to_string(),
    })
}

const SETTLEMENT_ID: &str = "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

// --- INV-1: mint conservation (coin_in == yes_out == no_out) -------------------------------

/// 1000 fixed-seed iterations, alternating an honest mint (built via the public
/// `EconomyEvent::position_minted` API, which cannot structurally diverge) and a
/// hand-forged `PositionMinted` (`no_out != coin_in`), asserting `check_conservation`
/// accepts the former and hard-rejects the latter every time.
#[test]
fn inv1_mint_conservation_property() {
    let mut rng = Rng::new(0x1000_0001);
    for i in 0..1000u64 {
        let market_id = format!("mkt_inv1_{i}");
        let created = EconomyEvent::market_created(&market_id, "100", "100").expect("market created");
        let amount = rand_decimal(&mut rng, 0, 1_000_000);

        if i % 2 == 0 {
            let mint = EconomyEvent::position_minted(&market_id, "agent_a", &amount).expect("mint");
            let minted = mint.as_position_minted().expect("minted event");
            assert_eq!(minted.coin_in, minted.yes_out, "iteration {i}");
            assert_eq!(minted.yes_out, minted.no_out, "iteration {i}");

            let report = check_conservation(&[created, mint]).expect("conservation check runs");
            assert_eq!(report.len(), 1, "iteration {i}");
            assert!(report[0].holds, "iteration {i}: honest mint must hold: {:?}", report[0]);
        } else {
            let mut other = rand_decimal(&mut rng, 0, 1_000_000);
            while other == amount {
                other = rand_decimal(&mut rng, 0, 1_000_000);
            }
            let forged = EconomyEvent::PositionMinted(PositionMinted {
                schema_id: "position_minted.v1".to_string(),
                market_id: market_id.clone(),
                agent_id: "attacker".to_string(),
                coin_in: amount.clone(),
                yes_out: amount.clone(),
                no_out: other.clone(),
                invariant: "coin_in == yes_out == no_out".to_string(),
            });
            let result = check_conservation(&[created, forged]);
            assert!(
                result.is_err(),
                "iteration {i}: forged mint (coin_in={amount}, no_out={other}) must be rejected"
            );
        }
    }
}

// --- INV-2: settlement conservation (single market, random lifecycle) ---------------------

/// 1000 fixed-seed iterations, each building a fresh single-market lifecycle (random pool
/// size, 1-3 mints across 3 agents, 0-3 random-side swaps, one random-result settlement)
/// entirely through the public API, asserting `check_conservation` always reports
/// `holds == true` (redeemed <= minted + subsidy) -- the property must hold for *every*
/// tape this crate's own constructors can produce, not just the one hand-picked fixture in
/// `economy_market.rs`.
///
/// **CONFIRMED RED (not a test bug -- see PART C):** with this exact fixed seed
/// (`0x2000_0002`) this fails at iteration 638 with `holds == false` on a tape that never
/// forges anything (every event comes from the public API). Root cause, hand-verified with
/// a minimal standalone repro (3 mints totaling 212 Coin, pool created at 100/109 =
/// declared_subsidy 209, then 3 sequential `buy_yes` swaps by the same trader with
/// pay=190/150/199 against the shrinking pool, settled YES): `check_conservation`
/// (`crates/turing-economy/src/lib.rs:526-614`) only adds `EconomyEvent::PositionMinted.coin_in`
/// into `MarketConservationReport.minted_coin` -- it never adds `AmmSwapExecuted.pay_coin`,
/// even though the crate's own `WalletProjection::from_tape_events` doc comment
/// (lines 419-425) states a swap's pay side is itself an implicit CTF mint ("pay-side tokens
/// implicitly minted then swapped into the pool"). In the minimal repro:
/// `minted_coin=212`, `declared_subsidy=209` (sum 421), but `redeemed_coin=834.179012345`
/// (holds=false) -- yet `421 + (190+150+199=539 in unaccounted swap pay_coin) = 960 >=
/// 834.179012345`, i.e. conservation *does* actually hold once the swaps' own pay_coin is
/// counted as backing. This means `check_conservation`/`turing audit market` can report a
/// **false positive "conservation violated"** on a perfectly healthy, high-swap-volume
/// market -- a real bug in the audit function's accounting, not evidence of an actual
/// Coin leak (the per-wallet ledger in `WalletProjection` already debits `pay_coin`
/// correctly; only the standalone `check_conservation` report undercounts the backing).
/// Left red per the capsule's PART B rule (do not hand-fix `src` here; hand off to PART C
/// for CONFIRMED/REFUTED adjudication and PART D for the actual fix).
#[test]
fn inv2_settlement_conservation_property() {
    let mut rng = Rng::new(0x2000_0002);
    let agents = ["trader_a", "trader_b", "trader_c"];

    for i in 0..1000u64 {
        let market_id = format!("mkt_inv2_{i}");
        let pool_y0 = rng.range(10, 10_000);
        let pool_n0 = rng.range(10, 10_000);
        let created =
            EconomyEvent::market_created(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
                .expect("market created");
        let mut pool = AmmPool::new(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
            .expect("pool constructs");
        let mut events = vec![created];

        let mint_count = rng.range(1, 4);
        for _ in 0..mint_count {
            let agent = agents[rng.range(0, agents.len() as u64) as usize];
            let amount = rng.range(1, 500);
            events.push(
                EconomyEvent::position_minted(&market_id, agent, &amount.to_string())
                    .expect("mint"),
            );
        }

        let swap_count = rng.range(0, 4);
        for _ in 0..swap_count {
            let agent = agents[rng.range(0, agents.len() as u64) as usize];
            let pay = rng.range(1, 200);
            let buy_yes = rng.range(0, 2) == 0;
            let swap = if buy_yes {
                pool.buy_yes(agent, &pay.to_string())
            } else {
                pool.buy_no(agent, &pay.to_string())
            }
            .expect("swap succeeds against a non-degenerate pool");
            pool = AmmPool::new(&market_id, &swap.pool_y_after, &swap.pool_n_after)
                .expect("re-pool from recorded state");
            events.push(EconomyEvent::AmmSwapExecuted(swap));
        }

        let result_side = ["YES", "NO", "INVALID"][rng.range(0, 3) as usize];
        events.push(
            EconomyEvent::market_settled(&market_id, result_side, SETTLEMENT_ID)
                .expect("settlement"),
        );

        let report = check_conservation(&events).expect("conservation check runs");
        assert_eq!(report.len(), 1, "iteration {i}");
        assert!(
            report[0].holds,
            "iteration {i}: INV-2 violated: {:?}",
            report[0]
        );
    }
}

// --- INV-3: global (whole-tape) conservation -----------------------------------------------

/// 1000 fixed-seed iterations, each a multi-market (2-3 markets) tape built through the
/// public API. Asserts both the per-market form (every report `holds`) and the strictly
/// global form (`sum(redeemed) <= sum(minted) + sum(subsidy)` across *all* markets on the
/// tape), summed from independently re-parsed `decimal_string` fields rather than trusting
/// any single aggregate the crate computes.
///
/// **Scope note (see `SPEC_ECONOMY.md` INV-3):** this only covers the *redemption* side of
/// global conservation, which is what `EconomyEvent::position_minted` and
/// `check_conservation` are actually responsible for -- the constructor's public signature
/// has no balance/genesis parameter at all, so a "does minting agent X actually possess this
/// Coin" check cannot exist inside this crate by construction; that gap lives in
/// `turing-daemons::market_mint_response` (confirmed GAP, out of this crate's eval scope).
#[test]
fn inv3_global_conservation_property() {
    let mut rng = Rng::new(0x3000_0003);

    for i in 0..1000u64 {
        let market_count = rng.range(2, 4);
        let mut events = Vec::new();

        for m in 0..market_count {
            let market_id = format!("mkt_inv3_{i}_{m}");
            let pool_y0 = rng.range(10, 5_000);
            let pool_n0 = rng.range(10, 5_000);
            events.push(
                EconomyEvent::market_created(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
                    .expect("market created"),
            );
            let mut pool = AmmPool::new(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
                .expect("pool constructs");

            let mint_count = rng.range(1, 3);
            for _ in 0..mint_count {
                let amount = rng.range(1, 300);
                events.push(
                    EconomyEvent::position_minted(&market_id, "trader", &amount.to_string())
                        .expect("mint"),
                );
            }

            let swap_count = rng.range(0, 3);
            for _ in 0..swap_count {
                let pay = rng.range(1, 100);
                let buy_yes = rng.range(0, 2) == 0;
                let swap = if buy_yes {
                    pool.buy_yes("trader", &pay.to_string())
                } else {
                    pool.buy_no("trader", &pay.to_string())
                }
                .expect("swap succeeds");
                pool = AmmPool::new(&market_id, &swap.pool_y_after, &swap.pool_n_after)
                    .expect("re-pool");
                events.push(EconomyEvent::AmmSwapExecuted(swap));
            }

            let result_side = ["YES", "NO"][rng.range(0, 2) as usize];
            events.push(
                EconomyEvent::market_settled(&market_id, result_side, SETTLEMENT_ID)
                    .expect("settlement"),
            );
        }

        let report = check_conservation(&events).expect("conservation check runs");
        assert_eq!(report.len(), market_count as usize, "iteration {i}");

        let mut sum_minted_plus_subsidy: i128 = 0;
        let mut sum_redeemed: i128 = 0;
        for market_report in &report {
            assert!(
                market_report.holds,
                "iteration {i}: per-market conservation violated: {market_report:?}"
            );
            sum_minted_plus_subsidy += parse_units_exact(&market_report.minted_coin)
                + parse_units_exact(&market_report.declared_subsidy);
            sum_redeemed += parse_units_exact(&market_report.redeemed_coin);
        }
        assert!(
            sum_redeemed <= sum_minted_plus_subsidy,
            "iteration {i}: INV-3 global conservation violated: redeemed={sum_redeemed} minted+subsidy={sum_minted_plus_subsidy}"
        );
    }
}

// --- INV-5 / INV-6: k-monotonic + rounding-favors-pool (money-pump defense) ----------------

/// 2000-round randomized round-trip: alternating random `buy_yes`/`buy_no` with random
/// payment sizes against a thin pool (fixed seed), re-deriving the pool from the recorded
/// tape state each round (so a hidden-state bug could not silently mask a violation).
/// Asserts, every round: (1) the recorded swap independently re-verifies its own D6
/// post-trade predicate (`verify_swap_post_trade_invariant`); (2) `k` never decreases
/// (INV-5); (3) the tape is self-consistent (`k_before` of this round equals `k_after` of
/// the previous round). Per the doc comment on `assert_k_non_decreasing`
/// (`crates/turing-economy/src/lib.rs:294-300`), k-monotonicity under non-negative,
/// floor-rounded operands *is* the money-pump defense (INV-6): if rounding ever favored the
/// trader, k would shrink and this loop would catch it immediately.
#[test]
fn inv5_inv6_k_monotonic_money_pump_property() {
    let mut rng = Rng::new(0x5000_0005);
    let mut pool = AmmPool::new("mkt_pump", "1000", "1000").expect("pool");
    let mut previous_k: Option<i128> = None;

    for i in 0..2000u64 {
        let buy_yes = rng.range(0, 2) == 0;
        let pay = rng.range(1, 50); // small vs. the 1000/1000 pool: forces frequent truncation
        let swap = if buy_yes {
            pool.buy_yes("trader", &pay.to_string())
        } else {
            pool.buy_no("trader", &pay.to_string())
        }
        .expect("swap should succeed against a non-degenerate pool");

        assert!(
            verify_swap_post_trade_invariant(&swap).is_ok(),
            "iteration {i}: recorded swap fails independent post-trade invariant re-check: {swap:?}"
        );

        let k_before = parse_units_exact(&swap.invariant_k_before);
        let k_after = parse_units_exact(&swap.invariant_k_after);
        assert!(
            k_after >= k_before,
            "iteration {i}: k decreased (money pump): {k_before} -> {k_after}"
        );
        if let Some(prev) = previous_k {
            assert_eq!(
                k_before, prev,
                "iteration {i}: tape inconsistency -- k_before does not match previous round's k_after"
            );
        }
        previous_k = Some(k_after);

        pool = AmmPool::new("mkt_pump", &swap.pool_y_after, &swap.pool_n_after)
            .expect("re-pool from recorded state");
    }
}

// --- INV-7: no overflow/panic on extreme inputs --------------------------------------------

/// 1000 fixed-seed iterations plus explicit boundary cases (0, smallest unit) across a
/// magnitude range that stays well under `i128::MAX` headroom even after `mul`/`mul_div`'s
/// unchecked multiplication (pool/pay units bounded so their product never exceeds ~1e30,
/// far below `i128::MAX` ~1.7e38). This is the range where SPEC_ECONOMY.md's INV-7 *does*
/// hold today -- asserts no panic ever occurs, using `catch_unwind` as a hard backstop (not
/// just trusting the `Result` type).
#[test]
fn inv7_bounded_extreme_values_do_not_panic_property() {
    let dust_pool = AmmPool::new("mkt_edge", "1", "1").expect("dust pool constructs");
    assert!(
        matches!(dust_pool.buy_yes("trader", "0"), Err(_)),
        "zero pay must be a clean Err (ZeroPay), not accepted"
    );
    assert!(
        dust_pool.buy_yes("trader", "0.000000001").is_ok(),
        "the smallest non-zero unit (1) must not panic"
    );

    let mut rng = Rng::new(0x7000_0007);
    for i in 0..1000u64 {
        let pool_y = rand_decimal(&mut rng, 1, 1_000_000);
        let pool_n = rand_decimal(&mut rng, 1, 1_000_000);
        let pay = rand_decimal(&mut rng, 0, 1_000_000);

        let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let pool = AmmPool::new("mkt_edge", &pool_y, &pool_n)?;
            pool.buy_yes("trader", &pay)
        }));
        assert!(
            outcome.is_ok(),
            "iteration {i}: bounded values panicked instead of returning Ok/Err: pool_y={pool_y} pool_n={pool_n} pay={pay}"
        );
    }
}

/// **INV-7 ENFORCED (was GAP, fixed in PART D.1):** `DecimalAmount::mul`/`mul_div`/`ratio`
/// used to use bare `*`/`/` with no `checked_mul`. At pool/pay magnitudes still comfortably
/// inside what `parse_non_negative`'s own `checked_mul` allows to be *parsed*
/// (~1e26 decimal, i.e. ~1e35 raw units -- nowhere near `i128::MAX`/`SCALE` on their own),
/// the very next multiplication inside `mul_div` (`self.units * numerator.units`) overflowed
/// `i128`: a debug-build panic (`overflow-checks = true`, Cargo's dev-profile default), or a
/// **silent wraparound** in a release build (`overflow-checks = false`, no workspace
/// override) that corrupted pool state past every existing k-monotonicity guard (both
/// `assert_k_non_decreasing` and `verify_swap_post_trade_invariant` re-derive `k` with the
/// same vulnerable multiply).
///
/// Fix: `mul`/`mul_div`/`ratio` now use `i128::checked_mul` and return
/// `EconomyError::ArithmeticOverflow` instead of panicking or wrapping, in both profiles.
/// This regression pins the fixed behaviour: the overflow-inducing swap above is now cleanly
/// refused, never panics, and never corrupts pool state.
#[test]
fn inv7_extreme_pool_sizes_overflow_is_now_refused_not_gap() {
    let huge = "100000000000000000000000000"; // 1e26 decimal -> ~1e35 raw units
    let pool = AmmPool::new("mkt_overflow", huge, huge).expect("huge pool constructs fine");
    let result = pool.buy_yes("attacker", huge);
    assert_eq!(
        result,
        Err(turing_economy::EconomyError::ArithmeticOverflow),
        "INV-7 regression: overflow-inducing swap must be cleanly refused, not panic/wrap: got {result:?}"
    );
}

// --- INV-8: minimum-liquidity floor (confirmed GAP, documented as a passing fact) ----------

/// **Confirmed GAP (`SPEC_ECONOMY.md` INV-8):** `AmmPool::new` only rejects an exact-zero
/// pool; there is no minimum-liquidity floor anywhere in the crate. 1000 fixed-seed
/// iterations sweep pool sizes down to the dust range (1..1_000_000 raw units, i.e.
/// 1e-9..1e-3 decimal) and confirm every one of them constructs successfully -- exact zero
/// remains the *only* rejected case. This is a genuinely passing test today (there is no
/// invariant violation to catch), but it makes the absence of a floor a machine-checked,
/// re-runnable fact rather than an inspection claim.
#[test]
fn inv8_no_minimum_liquidity_floor_property() {
    let mut rng = Rng::new(0x8000_0008);
    for i in 1..=1000u64 {
        let units = rng.range(1, 1_000_000);
        let decimal = format!("0.{units:09}");
        assert!(
            AmmPool::new("mkt_dust_sweep", &decimal, &decimal).is_ok(),
            "iteration {i}: pool at {decimal} (well above zero) should construct -- \
             confirms no minimum-liquidity floor exists anywhere below this magnitude"
        );
    }
    assert!(
        matches!(AmmPool::new("mkt_dust_sweep", "0", "1"), Err(_)),
        "exact zero remains the only rejected case"
    );
}

// --- INV-9: price never moves accepted_head -------------------------------------------------

/// 1000 fixed-seed iterations of random `MarketCreated`, `PriceBroadcast`, and
/// `MarketRouter::suggest` calls, asserting every one of them carries
/// `head_effect == "PRESERVE"` (and, for `BudgetSuggestion`, `can_move_accepted_head ==
/// false` / `emits_authorization == false`) regardless of the random input -- i.e. no random
/// input can ever flip these hardcoded constants, because no caller-supplied field feeds
/// them (structural guarantee, exercised across many inputs rather than the single example
/// in `market_router.rs`).
#[test]
fn inv9_price_never_moves_accepted_head_property() {
    let mut rng = Rng::new(0x9000_0009);
    let digest = format!("sha256:{}", "a".repeat(64));

    for i in 0..1000u64 {
        let market_id = format!("mkt_inv9_{i}");
        let pool_y = rand_decimal(&mut rng, 1, 1_000_000);
        let pool_n = rand_decimal(&mut rng, 1, 1_000_000);

        let created = EconomyEvent::market_created(&market_id, &pool_y, &pool_n)
            .expect("market created");
        let EconomyEvent::MarketCreated(created) = created else {
            unreachable!("market_created always returns MarketCreated")
        };
        assert_eq!(created.head_effect, "PRESERVE", "iteration {i}");

        let yes_price = format!("0.{:09}", rng.range(0, 1_000_000_000));
        let no_price = format!("0.{:09}", rng.range(0, 1_000_000_000));
        let broadcast = PriceBroadcast::new(&market_id, &yes_price, &no_price, &digest)
            .expect("price broadcast");
        assert_eq!(broadcast.head_effect, "PRESERVE", "iteration {i}");
        assert_eq!(broadcast.truth_status, "statistical_signal_only", "iteration {i}");

        let route = CandidateRoute {
            route_id: format!("route_{i}"),
            market_id: market_id.clone(),
            expected_failure_domain: "domain".to_string(),
            requested_tokens: rng.range(1, 100_000),
        };
        let signal = PriceSignal {
            market_id: market_id.clone(),
            yes_price,
            no_price,
            truth_status: "statistical_signal_only".to_string(),
        };
        let suggestion = MarketRouter::new(MarketRouterMode::Shadow)
            .suggest(&[route], &[signal], &digest, &digest, &digest)
            .expect("shadow suggestion");
        assert!(!suggestion.can_move_accepted_head, "iteration {i}");
        assert!(!suggestion.emits_authorization, "iteration {i}");
        assert_eq!(suggestion.head_effect, "PRESERVE", "iteration {i}");
    }
}

// --- INV-12: self-trade rejection ----------------------------------------------------------

/// 1000 fixed-seed iterations constructing randomized attack/non-attack scenarios: a
/// trader who just took one side may not immediately take the opposite side (rejected); may
/// freely repeat the same side (allowed); and may take the opposite side once a *different*
/// principal has traded in between (allowed again).
#[test]
fn inv12_self_trade_rejection_property() {
    let mut rng = Rng::new(0x1200_0012);
    let sides = ["BUY_YES", "BUY_NO"];

    for i in 0..1000u64 {
        let market_id = format!("mkt_inv12_{}", i % 11);
        let trader_a = format!("agent_{}", rng.range(0, 5));
        let side_a = sides[rng.range(0, 2) as usize];
        let opposite = if side_a == "BUY_YES" { "BUY_NO" } else { "BUY_YES" };

        let mut events = vec![fixture_swap(&market_id, &trader_a, side_a)];

        assert!(
            check_self_trade(&events, &market_id, &trader_a, opposite).is_err(),
            "iteration {i}: same trader taking the opposite side with no interposed principal must be refused"
        );
        assert!(
            check_self_trade(&events, &market_id, &trader_a, side_a).is_ok(),
            "iteration {i}: same trader repeating the same side must be allowed"
        );

        let interposer = format!("{trader_a}_other");
        events.push(fixture_swap(&market_id, &interposer, opposite));
        assert!(
            check_self_trade(&events, &market_id, &trader_a, opposite).is_ok(),
            "iteration {i}: opposite side must be allowed once a different principal has traded"
        );
    }
}

// --- INV-13: principal-level position cap ---------------------------------------------------

/// 1000 fixed-seed iterations: build a random existing position (mint + swap-derived
/// exposure) for a principal, then independently predict whether adding a random
/// `pending_yes`/`pending_no` against a random `cap` should be accepted or refused, and
/// assert `check_principal_position_cap` matches that independently computed prediction
/// exactly in every case (not just the boundary example).
#[test]
fn inv13_principal_position_cap_property() {
    let mut rng = Rng::new(0x1300_0013);

    for i in 0..1000u64 {
        let market_id = format!("mkt_inv13_{}", i % 5);
        let principal = format!("agent_{}", i % 4);

        let mint_amt = rng.range(0, 500);
        let swap_get_y = rng.range(0, 500);
        let swap_get_n = rng.range(0, 500);
        let pending_yes = rng.range(0, 500);
        let pending_no = rng.range(0, 500);
        let cap = rng.range(0, 1_500);

        let mint = EconomyEvent::position_minted(&market_id, &principal, &mint_amt.to_string())
            .expect("mint");
        let swap = fixture_swap_with_gets(
            &market_id,
            &principal,
            &swap_get_y.to_string(),
            &swap_get_n.to_string(),
        );
        let events = vec![mint, swap];

        let existing_yes = mint_amt + swap_get_y;
        let existing_no = mint_amt + swap_get_n;
        let expect_err = (existing_yes + pending_yes > cap) || (existing_no + pending_no > cap);

        let result = check_principal_position_cap(
            &events,
            &market_id,
            &principal,
            &pending_yes.to_string(),
            &pending_no.to_string(),
            &cap.to_string(),
        );
        assert_eq!(
            result.is_err(),
            expect_err,
            "iteration {i}: existing_yes={existing_yes} existing_no={existing_no} \
             pending_yes={pending_yes} pending_no={pending_no} cap={cap}"
        );
    }
}

// --- INV-14: proposer conflict (net-NO cap) --------------------------------------------------

/// 1000 fixed-seed iterations mirroring INV-13's structure but for `check_proposer_conflict`,
/// including the no-op branches (empty `proposer_id`, `trader_id != proposer_id`) and the
/// net-NO semantics (`no - yes`, floored at zero): independently predicts accept/refuse and
/// asserts the function matches every time.
#[test]
fn inv14_proposer_conflict_property() {
    let mut rng = Rng::new(0x1400_0014);

    for i in 0..1000u64 {
        let market_id = format!("mkt_inv14_{}", i % 5);
        let proposer = format!("agent_{}", i % 3);
        let trader = if i % 2 == 0 {
            proposer.clone()
        } else {
            format!("agent_{}", (i + 1) % 3)
        };
        let proposer_arg = if i % 13 == 0 {
            String::new() // exercise the "no proposer bound" no-op path
        } else {
            proposer.clone()
        };

        let mint_amt = rng.range(0, 500);
        let swap_get_y = rng.range(0, 500);
        let swap_get_n = rng.range(0, 500);
        let pending_yes = rng.range(0, 500);
        let pending_no = rng.range(0, 500);
        let cap = rng.range(0, 800);

        let mint = EconomyEvent::position_minted(&market_id, &proposer, &mint_amt.to_string())
            .expect("mint");
        let swap = fixture_swap_with_gets(
            &market_id,
            &proposer,
            &swap_get_y.to_string(),
            &swap_get_n.to_string(),
        );
        let events = vec![mint, swap];

        let existing_yes = mint_amt + swap_get_y;
        let existing_no = mint_amt + swap_get_n;
        let total_yes = existing_yes + pending_yes;
        let total_no = existing_no + pending_no;
        let net_no = total_no.saturating_sub(total_yes);

        let is_noop = proposer_arg.is_empty() || trader != proposer_arg;
        let expect_err = !is_noop && net_no > cap;

        let result = check_proposer_conflict(
            &events,
            &market_id,
            &proposer_arg,
            &trader,
            &pending_yes.to_string(),
            &pending_no.to_string(),
            &cap.to_string(),
        );
        assert_eq!(
            result.is_err(),
            expect_err,
            "iteration {i}: proposer_arg={proposer_arg:?} trader={trader} net_no={net_no} cap={cap} is_noop={is_noop}"
        );
    }
}
