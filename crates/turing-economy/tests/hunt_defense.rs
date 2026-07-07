//! PART C.1 defense lens (镜头4) — hand-written, fixed-seed attack/property tests aimed at
//! INV-12 (self-trade), INV-13 (principal position cap), INV-14 (proposer conflict), INV-15
//! (difficulty-priced reputation farming). Written into the scratch dir first, then copied
//! into the crate's `tests/` as `hunt_defense.rs` (does not overwrite economy_market.rs /
//! market_router.rs / spec_evals.rs / hunt_arith.rs / hunt_conserv.rs).
//!
//! Methodology: each test asserts the STATED invariant (per SPEC_ECONOMY.md), not the exploit.
//! A test going RED (assertion failure) = one confirmed candidate bug, with the observed vs.
//! expected values printed in the panic message. A green `..._control` test is a sanity check
//! that the harness itself is not broken.
//!
//! Attack vectors tried:
//!  1. INV-12 self-trade: does a single, arbitrarily-cheap ("dust") interposing swap from a
//!     SECOND agent_id (which may be the very same real economic actor / colluding partner)
//!     fully reset `check_self_trade`'s "last trader" tracker, letting the original trader
//!     take the opposite side immediately afterward with zero friction?
//!  2. INV-14 proposer conflict: does routing the SAME real proposer's NO bet through a
//!     second `trader_id` (any string other than the literal `proposer_id`) fully bypass
//!     `check_proposer_conflict`'s de-minimis cap?
//!  3. INV-13 principal cap, ring-collusion variant: do N puppet identities, each individually
//!     within cap, let the aggregate real-actor exposure scale unboundedly with N?
//!
//! Fixed seeds only (xorshift64*, no time/Math.random), per capsule rule.

use turing_economy::{
    AmmPool, EconomyError, EconomyEvent, check_principal_position_cap, check_proposer_conflict,
    check_self_trade,
};

// --- deterministic PRNG (fixed seed, same algorithm as the other lens files) ----------------

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

const FIXED_SEED_1: u64 = 0x5EED_1234_C0FF_EE01;
const FIXED_SEED_2: u64 = 0x5EED_1234_C0FF_EE02;
const FIXED_SEED_3: u64 = 0x5EED_1234_C0FF_EE03;

/// CANDIDATE BUG 1 (INV-12 stated as: "同 principal 对侧同轮 → refused"). A single dust
/// interposing swap from ANY other agent_id resets `check_self_trade`'s tracker, so the
/// *original* trader can flip sides immediately after, with zero capital committed by the
/// "interposing" identity beyond dust. `check_self_trade` tracks only the single
/// most-recently-seen swap on the market (any trader), not "the last swap by a genuinely
/// distinct, unrelated principal" -- so a colluding pair (or two accounts controlled by the
/// same attacker) can wash-trade at will for the cost of one dust trade.
/// NEEDS OWNER (out of scope for PART D.1's 4 assigned CONFIRMED bugs; this is a separate
/// 镜头4/defense-lens finding, not one of the 4 bugs dispatched for this capsule run).
/// `check_self_trade` tracks only the single most-recently-seen swap on the market by literal
/// `trader_id`/`agent_id` string; there is no Sybil-resistant "real principal" identity in this
/// codebase to aggregate across (the same architectural gap as INV-13's documented
/// `principal_id == agent_id` limitation). Closing this requires a principal registry
/// (`principal_id != agent_id`, capsule PART D.2's own explicit GAP), an owner-level
/// architecture decision -- not a local fix to `check_self_trade`.
#[test]
#[ignore = "NEEDS OWNER: requires a Sybil-resistant principal registry (principal_id != \
            agent_id), the same architecture-level GAP as INV-13 (capsule PART D.2). Not one \
            of PART D.1's 4 assigned CONFIRMED bugs."]
fn inv12_self_trade_should_still_refuse_after_dust_puppet_interposition_property() {
    let mut rng = Rng::new(FIXED_SEED_1);
    let mut violations = 0usize;
    let mut trials = 0usize;
    let mut first_repro: Option<(u64, u64, u64)> = None;
    for i in 0..1000u64 {
        let pool_y = rng.range(1_000, 1_000_000_000);
        let pool_n = rng.range(1_000, 1_000_000_000);
        let attacker_pay = rng.range(1, pool_y.min(pool_n));
        let dust_pay = 1u64; // smallest representable micro-Coin unit

        let pool = AmmPool::new(
            format!("m-self-trade-{i}"),
            &pool_y.to_string(),
            &pool_n.to_string(),
        )
        .expect("pool construction with positive reserves must succeed");

        let Ok(attacker_first) = pool.buy_yes("attacker", &attacker_pay.to_string()) else {
            continue; // extreme ratio rejected by pool math; not this bug's path
        };
        let pool_after_first = AmmPool::new(
            format!("m-self-trade-{i}"),
            &attacker_first.pool_y_after,
            &attacker_first.pool_n_after,
        )
        .expect("post-swap pool state is always a valid pool");

        // Sybil/colluding puppet trades dust (does not even need to trade opposite -- any swap
        // by a different agent_id resets the tracker).
        let Ok(puppet_dust) = pool_after_first.buy_yes("attacker-puppet", &dust_pay.to_string())
        else {
            continue;
        };

        let events = vec![
            EconomyEvent::AmmSwapExecuted(attacker_first),
            EconomyEvent::AmmSwapExecuted(puppet_dust),
        ];

        trials += 1;
        // STATED INVARIANT: attacker flipping to the opposite side right after their own YES,
        // with no genuinely distinct third party having cleared the round, must still be
        // refused (same principal, same round).
        let result = check_self_trade(&events, &format!("m-self-trade-{i}"), "attacker", "BUY_NO");
        if result.is_ok() {
            violations += 1;
            if first_repro.is_none() {
                first_repro = Some((i, pool_y, pool_n));
            }
        }
    }
    assert_eq!(
        violations, 0,
        "INV-12 VIOLATED in {violations}/{trials} fixed-seed trials (seed {FIXED_SEED_1:#x}): \
         check_self_trade returned Ok(()) (attacker's opposite-side flip was ALLOWED) after a \
         single 1-micro-Coin dust interposing swap from a puppet agent_id, even though the same \
         real principal ('attacker') still controls both swaps. Expected: Err(SelfTradeRejected). \
         First minimal repro at fixture index {first_repro:?} (i, pool_y, pool_n)."
    );
}

/// Minimal, hand-verified repro of CANDIDATE BUG 1 with concrete fixed numbers (no RNG).
/// NEEDS OWNER: see the rationale on the property test above.
#[test]
#[ignore = "NEEDS OWNER: requires a Sybil-resistant principal registry (principal_id != \
            agent_id), the same architecture-level GAP as INV-13 (capsule PART D.2). Not one \
            of PART D.1's 4 assigned CONFIRMED bugs."]
fn inv12_self_trade_dust_interposition_minimal_repro() {
    let pool = AmmPool::new("m-repro", "1000000000", "1000000000").expect("pool");
    let attacker_first = pool.buy_yes("attacker", "100000000").expect("first swap");
    let pool_after_first = AmmPool::new(
        "m-repro",
        &attacker_first.pool_y_after,
        &attacker_first.pool_n_after,
    )
    .expect("post-swap pool");
    let puppet_dust = pool_after_first
        .buy_yes("attacker-puppet", "1")
        .expect("dust swap");

    let events = vec![
        EconomyEvent::AmmSwapExecuted(attacker_first),
        EconomyEvent::AmmSwapExecuted(puppet_dust),
    ];

    let result = check_self_trade(&events, "m-repro", "attacker", "BUY_NO");
    assert!(
        matches!(result, Err(EconomyError::SelfTradeRejected(_))),
        "INV-12 VIOLATED: expected Err(SelfTradeRejected(_)) but got {result:?}. Observed: \
         Ok(()) -- attacker holds YES (first swap, pay=100000000) AND is allowed to immediately \
         take NO, with the only 'clearing' event being their own 1-micro-Coin puppet trade."
    );
}

/// Sanity/negative control: confirm `check_self_trade` DOES correctly refuse the straightforward
/// case (no interposing trade at all). Guards against the property test above being a false
/// positive from a broken harness rather than a real gap.
#[test]
fn inv12_self_trade_direct_flip_is_still_refused_control() {
    let pool = AmmPool::new("m-control", "1000000000", "1000000000").expect("pool");
    let first = pool.buy_yes("attacker", "100000000").expect("first swap");
    let events = vec![EconomyEvent::AmmSwapExecuted(first)];
    let result = check_self_trade(&events, "m-control", "attacker", "BUY_NO");
    assert!(
        matches!(result, Err(EconomyError::SelfTradeRejected(_))),
        "control case (no interposing trade) must still be refused, got: {result:?}"
    );
}

/// CANDIDATE BUG 2 (INV-14 stated as: "proposer 不得在自己市场持 NO 超 de-minimis").
/// `check_proposer_conflict` is a strict no-op (`Ok(())`) whenever `trader_id != proposer_id`,
/// with NO aggregation across any other identity. A proposer who routes their NO bet through
/// literally any other string as `trader_id` (a puppet/second agent_id under the same
/// real-world control) faces zero de-minimis enforcement -- the check does not even attempt to
/// look at the puppet's position.
/// NEEDS OWNER (out of scope for PART D.1's 4 assigned CONFIRMED bugs; a separate 镜头4
/// defense-lens finding). `check_proposer_conflict` compares `trader_id` to the literal
/// `proposer_id` string with zero cross-identity aggregation -- the same missing
/// Sybil-resistant principal registry as INV-13/INV-12 above. Architecture-level, not a local
/// fix.
#[test]
#[ignore = "NEEDS OWNER: requires a Sybil-resistant principal registry (principal_id != \
            agent_id), the same architecture-level GAP as INV-13 (capsule PART D.2). Not one \
            of PART D.1's 4 assigned CONFIRMED bugs."]
fn inv14_proposer_conflict_should_still_cap_puppet_account_net_no_property() {
    let mut rng = Rng::new(FIXED_SEED_2);
    let mut violations = 0usize;
    let mut trials = 0usize;
    let mut first_repro: Option<(u64, u64, u64, u64)> = None;
    let de_minimis_cap = 1u64; // essentially zero tolerance

    for i in 0..1000u64 {
        let pool_y = rng.range(1_000, 1_000_000_000);
        let pool_n = rng.range(1_000, 1_000_000_000);
        let huge_no_pay = rng.range(pool_y.min(pool_n) / 4, pool_y.min(pool_n) / 2).max(1);

        let pool = AmmPool::new(
            format!("m-proposer-{i}"),
            &pool_y.to_string(),
            &pool_n.to_string(),
        )
        .expect("pool construction with positive reserves must succeed");

        // The proposer's puppet identity buys a huge NO position directly.
        let Ok(puppet_swap) = pool.buy_no("proposer-puppet", &huge_no_pay.to_string()) else {
            continue;
        };
        let events = vec![EconomyEvent::AmmSwapExecuted(puppet_swap)];

        trials += 1;
        // STATED INVARIANT: the real proposer ("proposer"), acting through puppet identity
        // "proposer-puppet", must still be capped at de_minimis_cap net NO on their own market.
        let result = check_proposer_conflict(
            &events,
            &format!("m-proposer-{i}"),
            "proposer",
            "proposer-puppet",
            "0",
            &huge_no_pay.to_string(),
            &de_minimis_cap.to_string(),
        );
        if result.is_ok() {
            violations += 1;
            if first_repro.is_none() {
                first_repro = Some((i, pool_y, pool_n, huge_no_pay));
            }
        }
    }
    assert_eq!(
        violations, 0,
        "INV-14 VIOLATED in {violations}/{trials} fixed-seed trials (seed {FIXED_SEED_2:#x}): \
         check_proposer_conflict returned Ok(()) even though the proposer's puppet identity \
         holds a net-NO position vastly exceeding de_minimis_cap={de_minimis_cap} on the \
         proposer's own market. Expected: Err(ProposerConflictRejected). First minimal repro at \
         fixture index {first_repro:?} (i, pool_y, pool_n, huge_no_pay)."
    );
}

/// Minimal, hand-verified repro of CANDIDATE BUG 2 with concrete fixed numbers.
/// NEEDS OWNER: see the rationale on the property test above.
#[test]
#[ignore = "NEEDS OWNER: requires a Sybil-resistant principal registry (principal_id != \
            agent_id), the same architecture-level GAP as INV-13 (capsule PART D.2). Not one \
            of PART D.1's 4 assigned CONFIRMED bugs."]
fn inv14_proposer_conflict_puppet_account_minimal_repro() {
    let pool = AmmPool::new("m-repro2", "1000000000", "1000000000").expect("pool");
    let puppet_swap = pool.buy_no("proposer-puppet", "400000000").expect("swap");
    let events = vec![EconomyEvent::AmmSwapExecuted(puppet_swap)];

    let result = check_proposer_conflict(
        &events,
        "m-repro2",
        "proposer",
        "proposer-puppet",
        "0",
        "400000000",
        "1",
    );
    assert!(
        matches!(result, Err(EconomyError::ProposerConflictRejected(_))),
        "INV-14 VIOLATED: expected Err(ProposerConflictRejected(_)) but got {result:?}. Observed: \
         Ok(()) even though the 'proposer' economic actor (via puppet identity \
         'proposer-puppet') holds net_no from a 400000000-pay swap on their own market, far \
         above de_minimis_cap=1. Unlike check_principal_position_cap, this function's doc \
         comment does not flag this Sybil/puppet limitation at all -- it is a *total* bypass \
         (zero aggregation attempted), not merely a partial one."
    );
}

/// Sanity/negative control: confirm `check_proposer_conflict` DOES correctly refuse the
/// straightforward case (trader_id literally equals proposer_id).
#[test]
fn inv14_proposer_conflict_direct_case_is_still_refused_control() {
    let pool = AmmPool::new("m-control2", "1000000000", "1000000000").expect("pool");
    let swap = pool.buy_no("proposer", "400000000").expect("swap");
    let events = vec![EconomyEvent::AmmSwapExecuted(swap)];
    let result = check_proposer_conflict(
        &events,
        "m-control2",
        "proposer",
        "proposer",
        "0",
        "400000000",
        "1",
    );
    assert!(
        matches!(result, Err(EconomyError::ProposerConflictRejected(_))),
        "control case (trader_id == proposer_id) must still be refused, got: {result:?}"
    );
}

/// CANDIDATE BUG 3 (INV-13 magnitude confirmation). The documented principal-cap Sybil gap
/// ("Sybil-splitting formally defeats per-account caps") is not merely imperfect -- it is
/// UNBOUNDED: N puppet identities, each individually satisfying `cap`, let the same real
/// economic actor accumulate `N * cap` aggregate exposure with no upper bound as N grows.
/// STATED INVARIANT under test here (a strengthened reading of INV-13, "principal 级仓位上限":
///跨账户按 principal 聚合封顶): the real aggregate exposure of one economic actor spread over
/// puppets should stay bounded by `cap`, not scale linearly with puppet count.
/// NEEDS OWNER (out of scope for PART D.1's 4 assigned CONFIRMED bugs). This is exactly the
/// INV-13 Sybil-registry GAP the capsule itself names as the canonical "needs owner, not a
/// local fix" example (PART D.2: "principal registry (principal_id != agent_id)"). Left
/// failing and `#[ignore]`d rather than hidden.
#[test]
#[ignore = "NEEDS OWNER: this IS the capsule's own canonical INV-13 Sybil-registry example \
            (PART D.2: principal registry, principal_id != agent_id). Not one of PART D.1's 4 \
            assigned CONFIRMED bugs."]
fn inv13_principal_cap_should_bound_ring_collusion_aggregate_property() {
    let mut rng = Rng::new(FIXED_SEED_3);
    let cap: u64 = 1_000;
    let mut violations = 0usize;
    for i in 0..50u64 {
        let puppet_count = rng.range(2, 20);
        let mut aggregate_yes: u128 = 0;
        for p in 0..puppet_count {
            let principal_id = format!("real-actor-{i}-puppet-{p}");
            let events: Vec<EconomyEvent> = Vec::new(); // each puppet starts fresh (no shared history)
            let pending_yes = cap.to_string(); // exactly at the cap, individually compliant
            let result = check_principal_position_cap(
                &events,
                &format!("m-ring-{i}"),
                &principal_id,
                &pending_yes,
                "0",
                &cap.to_string(),
            );
            assert!(
                result.is_ok(),
                "each individual puppet must pass its own isolated cap check: {result:?}"
            );
            aggregate_yes += cap as u128;
        }
        // STATED INVARIANT check: the true aggregate exposure of the single underlying economic
        // actor must not exceed `cap`.
        if aggregate_yes > cap as u128 {
            violations += 1;
        }
    }
    assert_eq!(
        violations, 0,
        "INV-13 VIOLATED in {violations}/50 fixed-seed trials (seed {FIXED_SEED_3:#x}): a single \
         real economic actor split across 2-19 puppet identities accumulated aggregate exposure \
         strictly exceeding cap={cap} (each puppet individually 'compliant' at exactly cap), \
         confirming the documented Sybil gap scales UNBOUNDED with puppet count rather than \
         being bounded or degrading gracefully."
    );
}
