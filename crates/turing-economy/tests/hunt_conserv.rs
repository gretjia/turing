//! PART C.1 (conserv lens) of `PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md`.
//!
//! Independent attacker-mindset property/attack tests targeting the conservation lens only
//! (INV-1 mint conservation, INV-2 settlement conservation, INV-3 global no-free-Coin,
//! WalletProjection swap/settle bookkeeping, and the historical "event filter reads wrong
//! field -> drops 4/5 events" class of bug). Written from scratch, independent of
//! `tests/spec_evals.rs` (PART B), with our own fixed seeds and our own attack vectors.
//!
//! No `proptest`/`quickcheck` dependency exists in this workspace: every property loop below
//! uses a hand-written, fixed-seed PRNG (xorshift64*), never `Math.random`/time-based seeding,
//! so every run is bit-for-bit reproducible.

use turing_economy::{AmmPool, AmmSwapExecuted, EconomyEvent, RewardDistributed, check_conservation};

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

/// Parses a `decimal_string` into exact integer "units" for lossless comparison.
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

const SETTLEMENT_ID: &str = "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

/// Hand-forged `AmmSwapExecuted` with attacker-controlled `get_y`/`get_n` (the fields
/// `check_conservation` actually trusts to compute redemption), independent of any real
/// `AmmPool` math -- this is exactly the "untrusted tape" scenario `check_conservation`'s own
/// doc comment says it defends against.
fn forged_swap(market_id: &str, trader_id: &str, get_y: &str, get_n: &str) -> EconomyEvent {
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

// =============================================================================================
// CANDIDATE 1 (independent re-confirmation, NOW FIXED): swap `pay_coin` was never counted as
// backing by `check_conservation`, so a healthy high-swap-volume market could be falsely
// reported as `holds == false` (INV-2). Fixed in PART D.1: `check_conservation` now tracks
// `swap_pay_coin` per market and includes it in the `holds` predicate
// (`redeemed_coin + reward_coin <= minted_coin + declared_subsidy + swap_pay_coin + slash_coin`).
// This regression pins the fix: `check_conservation`'s own `holds` field must never go false on
// a real (non-forged) tape, matching the TRUE conservation predicate.
// =============================================================================================

/// 500 fixed-seed iterations, each a single-market lifecycle (small pool, 1 mint, 1-5
/// same-trader `buy_yes` swaps draining an increasingly thin pool, settled YES). Asserts both
/// the *true* conservation predicate (redeemed <= minted + subsidy + sum of swap pay_coin) and
/// `check_conservation`'s own `holds` field agree -- always true on this healthy tape -- proving
/// the previous false-negative pessimism is fixed.
#[test]
fn candidate1_check_conservation_ignores_swap_pay_coin_backing() {
    let mut rng = Rng::new(0xC0A5_0001);

    for i in 0..500u64 {
        let market_id = format!("mkt_c1_{i}");
        let pool_y0 = rng.range(5, 500);
        let pool_n0 = rng.range(5, 500);
        let created =
            EconomyEvent::market_created(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
                .expect("market created");
        let mut pool = AmmPool::new(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
            .expect("pool constructs");
        let mut events = vec![created];

        let mint_amt = rng.range(1, 300);
        events.push(
            EconomyEvent::position_minted(&market_id, "trader", &mint_amt.to_string())
                .expect("mint"),
        );

        let mut sum_pay: i128 = 0;
        let swap_count = rng.range(1, 6);
        for _ in 0..swap_count {
            let pay = rng.range(1, 400);
            let swap = pool.buy_yes("trader", &pay.to_string());
            let Ok(swap) = swap else { break };
            sum_pay += parse_units_exact(&swap.pay_coin);
            pool = AmmPool::new(&market_id, &swap.pool_y_after, &swap.pool_n_after)
                .expect("re-pool from recorded state");
            events.push(EconomyEvent::AmmSwapExecuted(swap));
        }

        events.push(
            EconomyEvent::market_settled(&market_id, "YES", SETTLEMENT_ID).expect("settlement"),
        );

        let report = check_conservation(&events).expect("conservation check runs");
        assert_eq!(report.len(), 1, "iteration {i}");
        let r = &report[0];

        let minted = parse_units_exact(&r.minted_coin);
        let subsidy = parse_units_exact(&r.declared_subsidy);
        let redeemed = parse_units_exact(&r.redeemed_coin);

        // The TRUE conservation predicate, counting swap pay_coin as backing.
        let true_holds = redeemed <= minted + subsidy + sum_pay;
        assert!(
            true_holds,
            "iteration {i}: even the TRUE predicate (with swap pay_coin counted) is violated -- \
             this would be a real Coin leak: redeemed={redeemed} minted={minted} subsidy={subsidy} sum_pay={sum_pay}"
        );

        // FIX REGRESSION: check_conservation's own holds must now agree with the true
        // predicate on every healthy iteration -- no more false-negative pessimism.
        assert!(
            r.holds,
            "iteration {i}: CONFIRMED-FIX REGRESSION FAILED: check_conservation still reports \
             holds=false on a healthy tape once swap pay_coin is counted as backing: {r:?} \
             (sum_pay={sum_pay})"
        );
    }
}

// =============================================================================================
// CANDIDATE 2 (NOW FIXED): `RewardDistributed.reward_coin`/`slash_coin` were never validated
// against any backing and `check_conservation` explicitly ignored the variant
// (`EconomyEvent::RewardDistributed(_) => {}`), a completely unconstrained, audit-invisible
// Coin-creation channel defeating INV-3 "凭空 Coin". Fixed in PART D.1: `check_conservation`
// now tracks `reward_coin`/`slash_coin` per market and folds them into the `holds` predicate
// (reward_coin counted on the "must be backed" side, slash_coin on the "backing" side,
// symmetric with `minted_coin`/`declared_subsidy`/`swap_pay_coin`). This regression pins the
// fix: an unbacked reward must now surface as `holds == false`, not be invisible.
// =============================================================================================

/// 200 fixed-seed iterations: build a normal, fully-conservative single-market tape (which
/// `check_conservation` correctly reports as `holds == true`), then append one
/// `RewardDistributed` event with an attacker-chosen `reward_coin` many orders of magnitude
/// larger than anything else on the tape and *zero* matching `slash_coin`/backing anywhere.
/// Asserts: (1) `check_conservation`'s report now changes after the reward is injected (no
/// longer byte-identical to baseline -- the audit is no longer blind); (2) the market now
/// reports `holds == false`, correctly flagging the unbacked Coin-creation.
#[test]
fn candidate2_reward_distributed_bypasses_conservation_audit() {
    let mut rng = Rng::new(0xC0A5_0002);

    for i in 0..200u64 {
        let market_id = format!("mkt_c2_{i}");
        let pool_y0 = rng.range(5, 200);
        let pool_n0 = rng.range(5, 200);
        let created =
            EconomyEvent::market_created(&market_id, &pool_y0.to_string(), &pool_n0.to_string())
                .expect("market created");
        let mint_amt = rng.range(1, 100);
        let mint = EconomyEvent::position_minted(&market_id, "trader", &mint_amt.to_string())
            .expect("mint");
        let settled =
            EconomyEvent::market_settled(&market_id, "YES", SETTLEMENT_ID).expect("settlement");

        let baseline_events = vec![created.clone(), mint.clone(), settled.clone()];
        let baseline_report = check_conservation(&baseline_events).expect("baseline audit runs");
        assert_eq!(baseline_report.len(), 1, "iteration {i}");
        assert!(baseline_report[0].holds, "iteration {i}: baseline should be healthy");

        // Attacker-chosen astronomically large reward, unbacked by any mint/subsidy anywhere,
        // built directly via the public struct literal (no constructor exists to validate it).
        let huge_reward = format!("{}000000000", rng.range(1_000_000, 9_000_000)); // ~1e15+ Coin
        let forged_reward = EconomyEvent::RewardDistributed(RewardDistributed {
            schema_id: "reward_distributed.v1".to_string(),
            market_id: market_id.clone(),
            agent_id: "attacker".to_string(),
            reward_coin: huge_reward.clone(),
            slash_coin: "0".to_string(),
            reason: "PREDICATE_SETTLEMENT".to_string(),
        });

        let mut with_reward = baseline_events.clone();
        with_reward.push(forged_reward);
        let report_with_reward = check_conservation(&with_reward).expect("audit with reward runs");

        assert_ne!(
            report_with_reward, baseline_report,
            "iteration {i}: FIX REGRESSION FAILED: check_conservation's report must change \
             after injecting an unbacked reward of {huge_reward} -- the audit must no longer be \
             blind to the RewardDistributed Coin-creation channel"
        );
        assert!(
            !report_with_reward[0].holds,
            "iteration {i}: FIX REGRESSION FAILED: report must show holds=false once \
             {huge_reward} unbacked reward Coin was injected into the tape -- the audit must \
             now catch this Coin-creation channel instead of being blind to it"
        );
    }
}

// =============================================================================================
// CANDIDATE 3 (NOW FIXED): `check_conservation` used to include a market in its returned report
// only if a `MarketCreated` event for that exact `market_id` appeared in the given slice
// (`order` was only pushed to inside the `MarketCreated` match arm). A market that was
// minted/swapped/settled without ever having its `MarketCreated` event present in the slice
// (e.g. a forged tape, a truncated/paginated read, or any upstream loader bug) was silently
// dropped from the report entirely -- not flagged as a violation, not even present as an entry.
// Fixed in PART D.1 via `ensure_tracked`: every market_id observed from *any* event variant is
// now tracked in `order`/`markets`, so a market missing its `MarketCreated` event still appears
// in the report (with `declared_subsidy = 0`, exactly as-observed) and its `holds` is computed
// honestly instead of the market vanishing from the audit.
// =============================================================================================

/// A market with NO `MarketCreated` event in the slice at all, but a mint of 10 and a forged
/// swap crediting the trader 10_000_000 YES (no economic basis whatsoever), settled YES.
/// `check_conservation` must now surface this market (previously: zero entries) and correctly
/// report `holds == false` for the obvious 10 vs 10_000_000 over-redemption.
#[test]
fn candidate3_market_missing_marketcreated_event_evades_conservation_audit_entirely() {
    let market_id = "ghost_market_no_creation_event";
    let mint = EconomyEvent::position_minted(market_id, "trader", "10").expect("mint");
    let forged = forged_swap(market_id, "trader", "10000000", "0");
    let settled = EconomyEvent::market_settled(market_id, "YES", SETTLEMENT_ID).expect("settlement");

    let events = vec![mint, forged, settled];
    let report = check_conservation(&events).expect("conservation check runs without erroring");

    eprintln!(
        "CANDIDATE 3 repro (post-fix): events=[PositionMinted(coin_in=10), \
         AmmSwapExecuted(get_y=10000000, forged), MarketSettled(YES)] with NO MarketCreated \
         event -- check_conservation returned {} report entries",
        report.len()
    );

    assert_eq!(
        report.len(),
        1,
        "FIX REGRESSION FAILED: a market missing its MarketCreated event must still surface in \
         the conservation report, not vanish: {report:?}"
    );
    assert!(
        !report[0].holds,
        "FIX REGRESSION FAILED: the ghost market's obvious 10 vs 10_000_000 over-redemption \
         must be flagged holds=false, not silently pass: {:?}",
        report[0]
    );
}

/// 300 fixed-seed iterations, randomizing the over-redemption magnitude and the mint amount,
/// confirming the blind-spot fix holds across a range of inputs, not just one hand-picked case
/// -- and additionally confirming the tape WITH a `MarketCreated` event prepended still
/// correctly surfaces `holds == false` for the same forged swap (both must now agree).
#[test]
fn candidate3_property_blind_spot_vs_control_with_creation_event() {
    let mut rng = Rng::new(0xC0A5_0003);

    for i in 0..300u64 {
        let market_id = format!("mkt_c3_{i}");
        let mint_amt = rng.range(1, 50);
        let forged_get_y = rng.range(1_000, 1_000_000);

        let mint = EconomyEvent::position_minted(&market_id, "trader", &mint_amt.to_string())
            .expect("mint");
        let forged = forged_swap(&market_id, "trader", &forged_get_y.to_string(), "0");
        let settled =
            EconomyEvent::market_settled(&market_id, "YES", SETTLEMENT_ID).expect("settlement");

        // Formerly-blind-spot tape: no MarketCreated. Must now surface, and agree with control.
        let attack_events = vec![mint.clone(), forged.clone(), settled.clone()];
        let attack_report = check_conservation(&attack_events).expect("attack audit runs");
        assert_eq!(
            attack_report.len(),
            1,
            "iteration {i}: FIX REGRESSION FAILED: missing-MarketCreated market must still \
             surface in the report, got {attack_report:?}"
        );
        assert!(
            !attack_report[0].holds,
            "iteration {i}: FIX REGRESSION FAILED: mint={mint_amt} vs forged \
             get_y={forged_get_y} must report holds=false even without MarketCreated, got {:?}",
            attack_report[0]
        );

        // Control tape: identical events, MarketCreated(1,1) prepended.
        let created =
            EconomyEvent::market_created(&market_id, "1", "1").expect("market created");
        let control_events = vec![created, mint, forged, settled];
        let control_report = check_conservation(&control_events).expect("control audit runs");
        assert_eq!(control_report.len(), 1, "iteration {i}: control should surface one entry");
        assert!(
            !control_report[0].holds,
            "iteration {i}: control (with MarketCreated) should correctly report holds=false \
             for mint={mint_amt} vs forged get_y={forged_get_y}, got {:?}",
            control_report[0]
        );
    }
}
