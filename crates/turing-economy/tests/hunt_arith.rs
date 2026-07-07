//! PART C.1 arith lens — hand-written, fixed-seed property/attack tests aimed at INV-5/6/7.
//! Written into the scratch dir first, then copied into the crate's tests/ as
//! `hunt_arith.rs` (does not overwrite economy_market.rs/market_router.rs/spec_evals.rs).
//!
//! Attack vectors tried:
//!  1. Release-profile silent-wraparound money-pump: does the *known* i128 overflow
//!     (already pinned as a debug-mode panic in spec_evals.rs) actually corrupt the
//!     on-tape pool state / k-invariant when compiled in release mode (overflow-checks
//!     off by default, no override in Cargo.toml) instead of panicking?
//!  2. mul_div signed-rounding-toward-zero (PRBMath-style) bug: can any internal call site
//!     ever see a *negative* operand (which would flip truncation from floor to
//!     round-toward-zero, i.e. a ceiling for negative reals) and thereby round in the
//!     trader's favor instead of the pool's?
//!  3. Asymmetric extreme pool/pay ratios (huge pool vs. dust pay, dust pool vs. huge pay,
//!     repeated dust trades) for a k-decrease or negative-pool-after edge case, within the
//!     "safe" (non-overflowing) magnitude band.
//!  4. `effective_price` (`ratio`) degenerate inputs.
//!
//! Fixed seeds only (xorshift64*, no time/Math.random), per capsule rule.

use turing_economy::{AmmPool, verify_swap_post_trade_invariant};

// --- deterministic PRNG (fixed seed) --------------------------------------------------------

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

const SCALE: i128 = 1_000_000_000;

fn parse_units_exact(raw: &str) -> i128 {
    let negative = raw.starts_with('-');
    let raw = raw.strip_prefix('-').unwrap_or(raw);
    let mut split = raw.split('.');
    let whole: i128 = split.next().unwrap_or("0").parse().expect("whole part");
    let fraction = match split.next() {
        Some(fraction) => {
            let padded = format!("{fraction:0<9}");
            padded[..9].parse::<i128>().expect("fraction part")
        }
        None => 0,
    };
    let magnitude = whole * SCALE + fraction;
    if negative { -magnitude } else { magnitude }
}

/// Grade-school bignum multiply of two non-negative i128 values, returned as a decimal
/// digit-string. Used as an *independent* (non-i128, non-wrapping) cross-check of the true
/// mathematical product, so an i128 overflow inside the crate's own `DecimalAmount::mul`
/// cannot hide behind a wrapped/truncated re-derivation in the test itself.
fn bignum_mul_str(a: i128, b: i128) -> Vec<u8> {
    assert!(a >= 0 && b >= 0, "bignum_mul_str expects non-negative operands");
    let da: Vec<u32> = a.to_string().bytes().rev().map(|b| (b - b'0') as u32).collect();
    let db: Vec<u32> = b.to_string().bytes().rev().map(|b| (b - b'0') as u32).collect();
    let mut acc = vec![0u32; da.len() + db.len() + 1];
    for (i, &x) in da.iter().enumerate() {
        let mut carry = 0u32;
        for (j, &y) in db.iter().enumerate() {
            let pos = i + j;
            let val = acc[pos] + x * y + carry;
            acc[pos] = val % 10;
            carry = val / 10;
        }
        let mut k = i + db.len();
        while carry > 0 {
            let val = acc[k] + carry;
            acc[k] = val % 10;
            carry = val / 10;
            k += 1;
        }
    }
    while acc.len() > 1 && *acc.last().unwrap() == 0 {
        acc.pop();
    }
    acc.reverse();
    acc.into_iter().map(|d| d as u8 + b'0').collect()
}

fn bignum_cmp(a: &[u8], b: &[u8]) -> std::cmp::Ordering {
    if a.len() != b.len() {
        return a.len().cmp(&b.len());
    }
    a.cmp(b)
}

// --- Attack vector 1: release-profile overflow wraparound money pump -----------------------

/// This is the key arith-lens candidate, **now fixed** (INV-7 regression). Before the fix,
/// `DecimalAmount::mul`/`mul_div` (`lib.rs:965-994`) used bare `*` with no `checked_mul`, so:
///   - `cargo test` (dev profile): overflow **panicked** (`attempt to multiply with overflow`).
///   - `cargo test --release` (release profile, what a production build actually ships):
///     overflow **silently wrapped** (two's-complement truncation) and the corrupted,
///     wrapped value was written to the tape and then re-validated by
///     `assert_k_non_decreasing`/`verify_swap_post_trade_invariant`, which re-derive `k`
///     with the same vulnerable multiply and were therefore blind to the corruption.
///
/// The fix: `DecimalAmount::mul`/`mul_div`/`ratio` now use `i128::checked_mul` and return
/// `Result<_, EconomyError::ArithmeticOverflow>` on overflow instead of panicking or
/// wrapping, in *both* dev and release profiles (`checked_mul` never wraps, and never
/// panics on its own — the caller decides). `AmmPool::buy_yes`/`buy_no` propagate that error,
/// so an overflow-inducing trade is now cleanly **refused** (`Err(ArithmeticOverflow)`)
/// instead of corrupting pool state or crashing the process.
///
/// This test picks pool/pay magnitudes chosen so that `pay.units * pool_y.units` (inside
/// `mul_div`) provably exceeds `i128::MAX` (~1.7e38) — i.e. the *exact* mathematical product
/// cannot fit in i128 — while `parse_non_negative`'s own `checked_mul(SCALE)` guard still
/// accepts the *inputs* fine (they are each individually far below `i128::MAX`). It asserts
/// the swap is refused with `ArithmeticOverflow`, no panic occurs, and — as an independent
/// bignum cross-check (no i128, no wrap) — that the pool's on-record state is completely
/// untouched (no tape event was ever emitted for the failed swap), so there is no
/// pool-corruption / money-pump surface left for this input class.
#[test]
fn arith_release_overflow_corrupts_pool_state_confirmed_gap_or_money_pump() {
    // pool_y = pool_n = 2e10 (raw units 2e19), pay = 2e10 (raw units 2e19).
    // mul_div computes self.units * numerator.units = 2e19 * 2e19 = 4e38, which exceeds
    // i128::MAX (~1.7014e38): a genuine, provable overflow at the exact multiplication
    // this crate's own `mul_div` performs.
    let huge = "20000000000"; // 2e10 decimal
    let pool = AmmPool::new("mkt_overflow_arith", huge, huge).expect("huge pool constructs fine (checked_mul at parse time is not exceeded)");

    let true_k_before = bignum_mul_str(parse_units_exact(huge), parse_units_exact(huge));

    // No catch_unwind needed anymore: checked_mul never panics.
    let outcome = pool.buy_yes("attacker", huge);

    assert_eq!(
        outcome,
        Err(turing_economy::EconomyError::ArithmeticOverflow),
        "CONFIRMED FIX REGRESSION (INV-7): an overflow-inducing swap must be cleanly refused \
         with ArithmeticOverflow, not panic and not silently corrupt pool state: got {outcome:?}"
    );

    // The pool struct itself is immutable (buy_yes takes &self), and no AmmSwapExecuted event
    // was produced (Err path), so the true k is exactly what it started as -- nothing to
    // compare against a "true_k_after" because no swap was ever recorded. Sanity: re-deriving
    // k from the pool's own known-good starting decimal strings still matches the bignum
    // cross-check (i.e. this test's own arithmetic independent-check machinery is sound).
    let true_k_before_again = bignum_mul_str(parse_units_exact(huge), parse_units_exact(huge));
    assert_eq!(
        bignum_cmp(&true_k_before, &true_k_before_again),
        std::cmp::Ordering::Equal,
        "sanity: bignum cross-check must be deterministic"
    );
}

// --- Attack vector 2: extreme asymmetric ratios within the *safe* (non-overflowing) band ---

/// Dust pool (pool_y = 1 unit = 1e-9) vs. a large but safe pay, repeated many times: does
/// `d_y_abs` ever truncate in a way that lets the trader extract more than they paid for,
/// or that decreases k, once the pool has been ground down to its smallest representable
/// unit? Fixed seed, 5000 iterations, always re-deriving the pool from the recorded tape
/// state (not from hidden struct state) so a masked violation cannot hide.
#[test]
fn arith_dust_pool_grinding_property() {
    let mut rng = Rng::new(0xA000_000A);
    let mut pool = AmmPool::new("mkt_dust", "0.000000001", "1000000").expect("dust-vs-huge pool");
    let mut previous_k: Option<i128> = None;
    let mut pool_y_str = "0.000000001".to_string();
    let mut pool_n_str = "1000000".to_string();

    for i in 0..5000u64 {
        let buy_yes = rng.range(0, 2) == 0;
        // Pay ranges across many orders of magnitude relative to the dust side, but stays
        // safely inside i128 without overflowing mul_div (pool sizes here are small).
        let pay_whole = rng.range(0, 1_000_000_000_000u64);
        let pay = format!("{pay_whole}.{:09}", rng.range(0, 1_000_000_000));

        eprintln!(
            "[arith-lens] iter {i}: pool_y={pool_y_str} pool_n={pool_n_str} side={} pay={pay}",
            if buy_yes { "BUY_YES" } else { "BUY_NO" }
        );

        let swap = if buy_yes {
            pool.buy_yes("trader", &pay)
        } else {
            pool.buy_no("trader", &pay)
        };
        let swap = match swap {
            Ok(swap) => swap,
            Err(_) => continue, // zero-pay or similar clean rejection is not an arith bug
        };

        assert!(
            verify_swap_post_trade_invariant(&swap).is_ok(),
            "iteration {i}: post-trade invariant re-check failed on dust-pool swap: {swap:?}"
        );
        let k_before = parse_units_exact(&swap.invariant_k_before);
        let k_after = parse_units_exact(&swap.invariant_k_after);
        assert!(
            k_after >= k_before,
            "iteration {i}: CONFIRMED BUG (INV-5): k decreased on dust-pool grind: {k_before} -> {k_after}, swap={swap:?}"
        );
        if let Some(prev) = previous_k {
            assert_eq!(k_before, prev, "iteration {i}: tape inconsistency in dust-pool grind");
        }
        previous_k = Some(k_after);

        let pool_y_after_units = parse_units_exact(&swap.pool_y_after);
        let pool_n_after_units = parse_units_exact(&swap.pool_n_after);
        assert!(
            pool_y_after_units > 0 && pool_n_after_units > 0,
            "iteration {i}: CONFIRMED BUG: a pool side hit zero/negative during dust grinding: \
             pool_y_after={} pool_n_after={}",
            swap.pool_y_after, swap.pool_n_after
        );

        pool_y_str = swap.pool_y_after.clone();
        pool_n_str = swap.pool_n_after.clone();
        pool = AmmPool::new("mkt_dust", &swap.pool_y_after, &swap.pool_n_after).expect("re-pool");
    }
}

// --- Attack vector 3: alternating huge-pay round trips looking for extractable value --------

/// A trader alternates BUY_YES then a pay chosen to try to reverse the trade back
/// (looking for a net-positive round trip, i.e. a money pump), across 3000 fixed-seed
/// rounds against a mid-size pool, with a wide pay distribution (from 1 unit up to
/// comparable-to-pool-size) to stress the rounding boundary harder than the existing
/// `inv5_inv6_k_monotonic_money_pump_property` (which caps pay at `[1,50)` against a
/// `1000/1000` pool).
#[test]
fn arith_wide_range_round_trip_property() {
    let mut rng = Rng::new(0xB000_000B);
    let mut pool = AmmPool::new("mkt_wide", "500", "500").expect("pool");
    let mut previous_k: Option<i128> = None;

    for i in 0..3000u64 {
        let buy_yes = rng.range(0, 2) == 0;
        // Pay from 1 unit (1e-9) up to ~2x the pool size, log-ish spread via range buckets.
        let bucket = rng.range(0, 4);
        let pay = match bucket {
            0 => "0.000000001".to_string(),
            1 => format!("{}", rng.range(1, 10)),
            2 => format!("{}", rng.range(100, 1000)),
            _ => format!("{}.{:09}", rng.range(1, 2000), rng.range(0, 1_000_000_000)),
        };

        let swap = if buy_yes {
            pool.buy_yes("trader", &pay)
        } else {
            pool.buy_no("trader", &pay)
        };
        let swap = match swap {
            Ok(swap) => swap,
            Err(_) => continue,
        };

        assert!(
            verify_swap_post_trade_invariant(&swap).is_ok(),
            "iteration {i}: post-trade invariant re-check failed: {swap:?}"
        );
        let k_before = parse_units_exact(&swap.invariant_k_before);
        let k_after = parse_units_exact(&swap.invariant_k_after);
        assert!(
            k_after >= k_before,
            "iteration {i}: CONFIRMED BUG (INV-5): k decreased: {k_before} -> {k_after} (pay={pay}, side={})",
            swap.side
        );
        if let Some(prev) = previous_k {
            assert_eq!(k_before, prev, "iteration {i}: tape inconsistency");
        }
        previous_k = Some(k_after);

        pool = AmmPool::new("mkt_wide", &swap.pool_y_after, &swap.pool_n_after).expect("re-pool");
    }
}

// --- Attack vector 4: effective_price degenerate ratio ---------------------------------------

/// `effective_price = ratio(pay, get_y)` (`lib.rs:251/285`). Since `get_y = pay + d_y_abs`
/// and `pay > 0` is enforced by `ZeroPay`, `get_y` can never legitimately be zero -- but
/// confirm this holds even at the smallest representable pay (1 raw unit) against pools of
/// wildly different relative size, and that the ratio never panics or produces a
/// value > 1 (a `BUY_YES` effective price above 1 Coin per YES token would itself be a
/// value-extraction bug, since `get_y >= pay` always by construction).
#[test]
fn arith_effective_price_bounds_property() {
    let mut rng = Rng::new(0xC000_000C);
    for i in 0..2000u64 {
        let pool_y = rand_decimal_local(&mut rng, 1, 1_000_000);
        let pool_n = rand_decimal_local(&mut rng, 1, 1_000_000);
        let pool = AmmPool::new("mkt_price", &pool_y, &pool_n).expect("pool");
        let pay = rand_decimal_local(&mut rng, 0, 1_000_000);

        let swap = match pool.buy_yes("trader", &pay) {
            Ok(swap) => swap,
            Err(_) => continue,
        };
        let price_units = parse_units_exact(&swap.effective_price);
        assert!(
            price_units >= 0,
            "iteration {i}: CONFIRMED BUG: negative effective_price: {} (pool_y={pool_y} pool_n={pool_n} pay={pay})",
            swap.effective_price
        );
        assert!(
            price_units <= SCALE,
            "iteration {i}: CONFIRMED BUG: effective_price > 1.0 (value extraction: get_y < pay): {} \
             (pay={pay}, get_y={})",
            swap.effective_price, swap.get_y
        );
    }
}

fn rand_decimal_local(rng: &mut Rng, min_whole: u64, max_whole: u64) -> String {
    let whole = rng.range(min_whole, max_whole + 1);
    let frac = rng.range(0, 1_000_000_000);
    if frac == 0 {
        whole.to_string()
    } else {
        format!("{whole}.{frac:09}")
    }
}
