//! WP2 (`RES_ECON_emergence_toplevel_design_20260707.md` §4 "价格活化" row / §7 WP2;
//! spec source `ADR-ECON-003` Decision 6.1) acceptance tests for
//! `turing_economy::derive_price_signals`.
//!
//! Independent, hand-written (no `proptest`/`quickcheck`, no `Math.random`/time-based
//! seeding -- literal fixed constants only, per this crate's general test-suite convention;
//! see `tests/hunt_conserv.rs`/`tests/hunt_replay.rs`) reimplementation of the crate's
//! decimal_string <-> fixed-point conversion, kept deliberately independent of the
//! production `DecimalAmount` (private, not exported) so this suite exercises the public
//! contract as a black box rather than the internals.
//!
//! Scope covered:
//! 1. `BUY_YES` swap -> `yes_price` reads `effective_price` directly; `no_price` is its
//!    complement (Decision 6.1: "取最近一次 AmmSwapExecuted.effective_price 的 yes 侧").
//! 2. `BUY_NO` swap -> `yes_price` is the complement of `effective_price`; `no_price` reads
//!    it back out exactly.
//! 3. Markets with no `AmmSwapExecuted` in the tape emit no signal (not a zero/default).
//! 4. The *latest* `AmmSwapExecuted` per market (tape order) wins when a market is swapped
//!    more than once.
//! 5. `[0, 1]` clamp on out-of-range (forged/untrusted) `effective_price` values -- the tape
//!    is untrusted input (same attacker-mindset convention as `tests/hunt_conserv.rs`'s
//!    `forged_swap` helper), and Decision 6.1 explicitly requires the clamp regardless of
//!    how an out-of-range value reached the tape.
//! 6. Conservation/replay determinism (design doc §7 WP2 acceptance predicate, literal:
//!    `assert_eq!(derive(tape), derive(replay(tape)))`): re-deriving from the identical tape
//!    slice, and re-deriving after a causally-valid reordering of independent markets'
//!    events, both produce a byte-identical `Vec<PriceSignal>` -- this is a pure fold with no
//!    hidden state (Art 0.2), so replay can never diverge from the original derivation.
//! 7. `truth_status` is always `"statistical_signal_only"` (Art I.1: price is never truth).

use turing_economy::{AmmPool, EconomyEvent, PriceSignal, derive_price_signals};

const SCALE: i128 = 1_000_000_000;

/// Parses a `decimal_string` into exact integer "units", independent of the crate's private
/// `DecimalAmount` (mirrors `tests/hunt_conserv.rs::parse_units_exact`).
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

/// Formats non-negative integer "units" back into the crate's `decimal_string` convention
/// (trailing-zero-trimmed fraction), independent reimplementation of
/// `DecimalAmount::to_decimal_string`'s non-negative path -- used only to compute expected
/// values in this test file, never called by production code.
fn units_to_decimal_string(units: i128) -> String {
    assert!(units >= 0, "test helper only handles non-negative units");
    let whole = units / SCALE;
    let mut fraction = format!("{:09}", units % SCALE);
    while fraction.ends_with('0') {
        fraction.pop();
    }
    if fraction.is_empty() {
        whole.to_string()
    } else {
        format!("{whole}.{fraction}")
    }
}

fn expected_complement(decimal_string: &str) -> String {
    let complement = SCALE - parse_units_exact(decimal_string);
    units_to_decimal_string(complement.max(0))
}

fn signal_for<'a>(signals: &'a [PriceSignal], market_id: &str) -> Option<&'a PriceSignal> {
    signals.iter().find(|signal| signal.market_id == market_id)
}

#[test]
fn derive_price_signals_empty_tape_is_empty() {
    assert_eq!(derive_price_signals(&[]).expect("derive"), Vec::new());
}

#[test]
fn derive_price_signals_buy_yes_reads_effective_price_directly() {
    let created = EconomyEvent::market_created("mkt_yes", "100", "100").expect("created");
    let swap = AmmPool::new("mkt_yes", "100", "100")
        .expect("pool")
        .buy_yes("trader_a", "25")
        .expect("buy yes");
    let tape = vec![created, EconomyEvent::AmmSwapExecuted(swap.clone())];

    let signals = derive_price_signals(&tape).expect("derive");
    assert_eq!(signals.len(), 1);
    let signal = signal_for(&signals, "mkt_yes").expect("mkt_yes signal");
    assert_eq!(signal.yes_price, swap.effective_price);
    assert_eq!(signal.no_price, expected_complement(&swap.effective_price));
    assert_eq!(signal.truth_status, "statistical_signal_only");
}

#[test]
fn derive_price_signals_buy_no_complements_to_yes_side() {
    let created = EconomyEvent::market_created("mkt_no", "100", "100").expect("created");
    let swap = AmmPool::new("mkt_no", "100", "100")
        .expect("pool")
        .buy_no("trader_b", "25")
        .expect("buy no");
    let tape = vec![created, EconomyEvent::AmmSwapExecuted(swap.clone())];

    let signals = derive_price_signals(&tape).expect("derive");
    let signal = signal_for(&signals, "mkt_no").expect("mkt_no signal");
    assert_eq!(signal.yes_price, expected_complement(&swap.effective_price));
    // Complementing twice (yes = 1 - price, no = 1 - yes) is exact integer subtraction, so
    // no_price reads back out to precisely the original effective_price.
    assert_eq!(signal.no_price, swap.effective_price);
    assert_eq!(signal.truth_status, "statistical_signal_only");
}

#[test]
fn derive_price_signals_ignores_markets_with_no_swap() {
    let created_a = EconomyEvent::market_created("mkt_swapped", "100", "100").expect("created a");
    let created_b = EconomyEvent::market_created("mkt_quiet", "50", "50").expect("created b");
    let swap = AmmPool::new("mkt_swapped", "100", "100")
        .expect("pool")
        .buy_yes("trader_a", "10")
        .expect("buy yes");
    let tape = vec![created_a, created_b, EconomyEvent::AmmSwapExecuted(swap)];

    let signals = derive_price_signals(&tape).expect("derive");
    assert_eq!(signals.len(), 1, "quiet market must emit no signal at all");
    assert!(signal_for(&signals, "mkt_quiet").is_none());
    assert!(signal_for(&signals, "mkt_swapped").is_some());
}

#[test]
fn derive_price_signals_latest_swap_in_tape_order_wins() {
    let pool = AmmPool::new("mkt_multi", "100", "100").expect("pool");
    let first_swap = pool.buy_yes("trader_a", "10").expect("first swap");
    let pool_after_first = AmmPool::new(
        "mkt_multi",
        &first_swap.pool_y_after,
        &first_swap.pool_n_after,
    )
    .expect("pool after first swap");
    let second_swap = pool_after_first
        .buy_no("trader_b", "40")
        .expect("second swap");

    let tape = vec![
        EconomyEvent::market_created("mkt_multi", "100", "100").expect("created"),
        EconomyEvent::AmmSwapExecuted(first_swap.clone()),
        EconomyEvent::AmmSwapExecuted(second_swap.clone()),
    ];

    let signals = derive_price_signals(&tape).expect("derive");
    let signal = signal_for(&signals, "mkt_multi").expect("mkt_multi signal");
    // Must reflect the *second* (latest in tape order) swap, not the first.
    assert_ne!(signal.yes_price, first_swap.effective_price);
    assert_eq!(
        signal.yes_price,
        expected_complement(&second_swap.effective_price)
    );
}

// Attacker-mindset fixtures below (mirrors `tests/hunt_conserv.rs::forged_swap`): the tape is
// untrusted input, so `effective_price` can carry an out-of-range value regardless of whether
// real `AmmPool` arithmetic could ever produce it. Decision 6.1's `[0, 1]` clamp must hold
// unconditionally.

#[test]
fn derive_price_signals_clamps_out_of_range_effective_price() {
    let over_one = EconomyEvent::AmmSwapExecuted(turing_economy::AmmSwapExecuted {
        schema_id: "amm_swap_executed.v1".to_string(),
        market_id: "mkt_forged_high".to_string(),
        trader_id: "trader_forged".to_string(),
        side: "BUY_YES".to_string(),
        pay_coin: "0".to_string(),
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
        effective_price: "1.5".to_string(),
    });
    let complement_would_be_negative =
        EconomyEvent::AmmSwapExecuted(turing_economy::AmmSwapExecuted {
            schema_id: "amm_swap_executed.v1".to_string(),
            market_id: "mkt_forged_negative_complement".to_string(),
            trader_id: "trader_forged".to_string(),
            side: "BUY_NO".to_string(),
            pay_coin: "0".to_string(),
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
            effective_price: "1.5".to_string(),
        });

    let tape = vec![over_one, complement_would_be_negative];
    let signals = derive_price_signals(&tape).expect("derive");

    let high = signal_for(&signals, "mkt_forged_high").expect("high signal");
    assert_eq!(
        high.yes_price, "1",
        "BUY_YES effective_price > 1 must clamp yes_price to 1"
    );
    assert_eq!(
        high.no_price, "0",
        "clamped yes_price of 1 must complement to no_price 0"
    );

    let negative_complement =
        signal_for(&signals, "mkt_forged_negative_complement").expect("negative signal");
    assert_eq!(
        negative_complement.yes_price, "0",
        "BUY_NO effective_price > 1 complements to a negative value, which must clamp to 0"
    );
    assert_eq!(negative_complement.no_price, "1");
}

#[test]
fn derive_price_signals_conservation_replay_equality() {
    let pool = AmmPool::new("mkt_conserv", "200", "300").expect("pool");
    let swap_a = pool.buy_yes("trader_a", "17").expect("swap a");
    let pool_after_a =
        AmmPool::new("mkt_conserv", &swap_a.pool_y_after, &swap_a.pool_n_after).expect("pool a");
    let swap_b = pool_after_a.buy_no("trader_b", "9").expect("swap b");

    let tape = vec![
        EconomyEvent::market_created("mkt_conserv", "200", "300").expect("created"),
        EconomyEvent::AmmSwapExecuted(swap_a),
        EconomyEvent::AmmSwapExecuted(swap_b),
    ];

    // Literal WP2 acceptance predicate: assert_eq!(derive(tape), derive(replay(tape))). This
    // is a pure fold over already-committed tape events with no hidden state (Art 0.2), so
    // "replaying" the identical tape -- re-running the fold again -- must be byte-identical
    // to the first derivation.
    let derived_once = derive_price_signals(&tape).expect("derive once");
    let derived_replayed = derive_price_signals(&tape).expect("derive replayed");
    assert_eq!(derived_once, derived_replayed);
}

#[test]
fn derive_price_signals_cross_market_interleave_order_invariance() {
    let pool_x = AmmPool::new("mkt_x", "100", "100").expect("pool x");
    let swap_x = pool_x.buy_yes("trader_x", "13").expect("swap x");
    let pool_y = AmmPool::new("mkt_y", "150", "80").expect("pool y");
    let swap_y = pool_y.buy_no("trader_y", "6").expect("swap y");

    let created_x = EconomyEvent::market_created("mkt_x", "100", "100").expect("created x");
    let created_y = EconomyEvent::market_created("mkt_y", "150", "80").expect("created y");
    let swap_event_x = EconomyEvent::AmmSwapExecuted(swap_x);
    let swap_event_y = EconomyEvent::AmmSwapExecuted(swap_y);

    // Two independent markets' events, interleaved in two different causally-valid orders
    // (each market's own internal order -- created before its swap -- is preserved in both).
    let interleaving_a = vec![
        created_x.clone(),
        swap_event_x.clone(),
        created_y.clone(),
        swap_event_y.clone(),
    ];
    let interleaving_b = vec![created_y, created_x, swap_event_y, swap_event_x];

    let derived_a = derive_price_signals(&interleaving_a).expect("derive a");
    let derived_b = derive_price_signals(&interleaving_b).expect("derive b");
    assert_eq!(derived_a, derived_b);
}
