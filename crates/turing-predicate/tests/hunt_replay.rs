//! PART C.1 lens 5 (replay determinism, INV-4/INV-9/INV-17) for
//! `PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md`.
//!
//! Scope: only replay-class bugs -- non-deterministic ordering, or any path where the same
//! logical predicate/gate input can fold to two different reports/decisions depending on
//! incidental caller-side construction order. Fixed-seed hand-written PRNG only (no
//! `proptest`, no time/`Math.random` seeding).
//!
//! Attack vectors tried:
//! 1. Large-N shuffle-order invariance of `PredicateKernel::run` (extends the existing
//!    2-check `predicate_product_deterministic` test in `predicate_kernel.rs` to N checks,
//!    many shuffles, fixed seed).
//! 2. Duplicate `check_id` with conflicting `reject_class` -- CONFIRMED divergence, see
//!    below.
//! 3. `market_settlement_gate_g_mkt_06` repeated-call determinism on identical input.

use turing_predicate::{MarketSettlementGateInput, PredicateCheck, PredicateKernel, SettlementReference, market_settlement_gate_g_mkt_06};

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

    /// Fisher-Yates shuffle, fixed-seed.
    fn shuffle<T>(&mut self, items: &mut [T]) {
        for i in (1..items.len()).rev() {
            let j = self.range(0, (i + 1) as u64) as usize;
            items.swap(i, j);
        }
    }
}

// --- attack vector 1: large-N shuffle-order invariance -------------------------------------

/// 500 fixed-seed iterations: build 8-16 checks with unique `check_id`s, a fixed-seed random
/// subset failing (each with a distinct `reject_class`), shuffle the vector many times, and
/// assert `PredicateKernel::run` produces byte-identical `PredicateReport`s (including
/// `report_hash`) across every shuffle -- the property `predicate_product_deterministic`
/// already covers with a hand-picked 2-check example, extended here to a randomized,
/// larger-N, many-shuffles sweep.
#[test]
fn predicate_kernel_shuffle_order_invariance_property() {
    let mut rng = Rng::new(0x5EA2_0001);

    for i in 0..500u64 {
        let check_count = rng.range(8, 17);
        let mut base_checks = Vec::new();
        for c in 0..check_count {
            let check_id = format!("check_{i}_{c:02}");
            if rng.range(0, 2) == 0 {
                base_checks.push(PredicateCheck::pass(check_id));
            } else {
                let reject_class = format!("REJECT_{i}_{c:02}");
                base_checks.push(PredicateCheck::fail(check_id, reject_class));
            }
        }

        let kernel = PredicateKernel;
        let baseline = kernel
            .run("CandidateAccepted", base_checks.clone())
            .expect("baseline report");

        for shuffle_round in 0..5u64 {
            let mut shuffled = base_checks.clone();
            rng.shuffle(&mut shuffled);
            let report = kernel
                .run("CandidateAccepted", shuffled)
                .expect("shuffled report");
            assert_eq!(
                report, baseline,
                "iteration {i} shuffle {shuffle_round}: PredicateKernel::run is order-dependent \
                 for a unique-check_id input set"
            );
        }
    }
}

// --- attack vector 2: duplicate check_id with conflicting reject_class (CONFIRMED) --------

/// **CONFIRMED candidate bug (INV-4 class -- "same logical input, different derived
/// view"):** `PredicateKernel::run` sorts checks by `check_id` (`check_id.cmp`) specifically
/// to make the report order-independent of however the caller happened to construct the
/// `Vec<PredicateCheck>` (`predicate_kernel.rs`'s own `predicate_product_deterministic` test
/// exercises exactly this guarantee). But `Vec::sort_by` is a **stable** sort: when two
/// checks share the same `check_id`, their relative order is preserved from the *input*
/// order, not re-derived from any other field. `reject_class` is set to the first FAILED
/// check encountered during the post-sort iteration whose `reject_class` is still `None`
/// (`crates/turing-predicate/src/lib.rs:69-71`) -- so if two checks share a `check_id` and
/// both fail with *different* `reject_class` values, whichever one the caller happened to
/// list first survives the stable sort's tie-break and wins the report's `reject_class`
/// (and therefore its `report_hash`, since `reject_class` feeds the JCS-canonicalized hash
/// input). The exact same **multiset** of checks -- same `event_type`, same check contents,
/// only the caller's construction order differs -- folds to two different reports.
///
/// This does not fire through this workspace's only real caller
/// (`derive_candidate_predicate_checks` in `turing-daemons`, which always builds a fixed
/// literal list of unique `check_id`s), so it is not known to be reachable in production
/// today. It is still a genuine gap in `PredicateKernel::run`'s own advertised
/// order-independence contract for a public API with no documented uniqueness precondition
/// on `check_id`, so it is reported here rather than silently assumed safe.
#[test]
fn duplicate_check_id_conflicting_reject_class_diverges_by_input_order() {
    let kernel = PredicateKernel;

    let order_1 = vec![
        PredicateCheck::fail("dup_check", "REASON_A"),
        PredicateCheck::fail("dup_check", "REASON_B"),
    ];
    let order_2 = vec![
        PredicateCheck::fail("dup_check", "REASON_B"),
        PredicateCheck::fail("dup_check", "REASON_A"),
    ];

    let report_1 = kernel.run("CandidateAccepted", order_1).expect("report 1");
    let report_2 = kernel.run("CandidateAccepted", order_2).expect("report 2");

    assert_eq!(
        report_1.reject_class,
        report_2.reject_class,
        "CONFIRMED BUG: identical multiset of checks {{fail(dup_check,REASON_A), \
         fail(dup_check,REASON_B)}}, differing only in caller-supplied construction order, \
         yields reject_class={:?} vs reject_class={:?} -- PredicateKernel::run's stable sort \
         on check_id does not make the report order-independent when check_id is not unique",
        report_1.reject_class, report_2.reject_class
    );
    assert_eq!(
        report_1.report_hash, report_2.report_hash,
        "CONFIRMED BUG: same divergence propagates into report_hash (order-dependent hash \
         for an order-claimed-independent report): {:?} vs {:?}",
        report_1.report_hash, report_2.report_hash
    );
}

// --- attack vector 3: G-MKT-06 gate repeated-call determinism ------------------------------

/// 500 fixed-seed iterations of random (valid and invalid) `MarketSettlementGateInput`
/// combinations, asserting `market_settlement_gate_g_mkt_06` returns the identical `Result`
/// (`Ok`/specific `Err` variant) on two repeated calls with the identical input -- a pure
/// function over plain data should never be able to disagree with itself.
#[test]
fn g_mkt_06_repeated_call_determinism_property() {
    let mut rng = Rng::new(0x5EA2_0003);

    for i in 0..500u64 {
        let result = ["YES", "NO", "INVALID"][rng.range(0, 3) as usize];
        let settlement_event_id = if rng.range(0, 2) == 0 {
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        } else {
            "not-a-micro-id"
        };
        let market_capsule_id = if rng.range(0, 2) == 0 { "capsule_1" } else { "" };
        let hashes_match = rng.range(0, 2) == 0;
        let market_predicate_set_hash = "sha256:hash_a";
        let current_predicate_set_hash = if hashes_match { "sha256:hash_a" } else { "sha256:hash_b" };
        let reference = match rng.range(0, 4) {
            0 => SettlementReference::CandidateAccepted { capsule_id: Some("capsule_1") },
            1 => SettlementReference::FailureNode {
                bound_capsule_id: if rng.range(0, 2) == 0 { Some("capsule_1") } else { None },
            },
            2 => SettlementReference::Missing,
            _ => SettlementReference::OtherType("MarketCreated"),
        };
        let market_created_tape_index = if rng.range(0, 2) == 0 { Some(rng.range(0, 100) as usize) } else { None };
        let settlement_tape_index = if rng.range(0, 2) == 0 { Some(rng.range(0, 100) as usize) } else { None };

        let input = MarketSettlementGateInput {
            result,
            settlement_event_id,
            market_capsule_id,
            market_predicate_set_hash,
            current_predicate_set_hash,
            reference,
            market_created_tape_index,
            settlement_tape_index,
        };

        let first = market_settlement_gate_g_mkt_06(&input);
        let second = market_settlement_gate_g_mkt_06(&input);
        assert_eq!(
            first, second,
            "iteration {i}: market_settlement_gate_g_mkt_06 disagreed with itself on identical input"
        );
    }
}
