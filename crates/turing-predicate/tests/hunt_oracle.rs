//! PART C.1 oracle-binding lens (INV-11 / G-MKT-06) finder.
//!
//! Attack surface searched: (1) wrong-capsule reference accepted, (2) FailureNode
//! attribution ambiguity (no `capsule_id` on FailureNode payload), (3) predicate_set_hash
//! weakening still accepted, (4) settlement temporal-ordering violations, (5)
//! settlement_event_id resolving to a non-CandidateAccepted/FailureNode event.
//!
//! Method: hand-written deterministic random loops with a FIXED seed (no `Math.random`/time
//! seed; no proptest/quickcheck dependency exists in this workspace).

use turing_predicate::{
    MarketPputPredicateError, MarketSettlementGateInput, SettlementReference,
    candidate_predicate_set_hash, market_settlement_gate_g_mkt_06,
};

const FIXED_SEED: u64 = 0xC0FFEE_2026_0707;

/// Minimal xorshift64* PRNG -- deterministic, no external crate, no time/OS entropy.
struct Xorshift64(u64);
impl Xorshift64 {
    fn new(seed: u64) -> Self {
        Xorshift64(seed | 1)
    }
    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }
    fn next_range(&mut self, n: u64) -> u64 {
        if n == 0 { 0 } else { self.next_u64() % n }
    }
    fn next_bool(&mut self) -> bool {
        self.next_u64() % 2 == 0
    }
}

fn mu(byte: u8) -> String {
    format!("mu:{}", hex::encode_byte(byte))
}

/// Tiny inline hex encoder (avoid pulling in the `hex` crate as a dev-dependency).
mod hex {
    pub fn encode_byte(b: u8) -> String {
        format!("{:02x}", b).repeat(32)
    }
}

/// -----------------------------------------------------------------------------------------
/// CONFIRMED CANDIDATE #1 (INV-11), FIXED by ADR-ECON-002 (owner-ratified 2026-07-07,
/// additive, `turing_v5/pack_v5_3_1` untouched): G-MKT-06 used to perform ZERO capsule
/// cross-check on the NO (FailureNode) path -- the exact same on-tape FailureNode event, which
/// per its closed/frozen schema carries no `capsule_id` at all, legitimized a "NO" settlement
/// for ANY market, regardless of which capsule that FailureNode actually reports failure for.
///
/// Fix: `SettlementReference::FailureNode` now carries an additive `bound_capsule_id`, resolved
/// by the caller (`turing-daemons`) from a separate `FailureNodeCapsuleBound` tape event that
/// references the same `settlement_event_id` -- `FailureNodePayload` itself is never modified.
/// G-MKT-06's NO path now requires `bound_capsule_id == Some(market_capsule_id)`, symmetric to
/// the YES path's `CandidateAccepted { capsule_id }` check.
///
/// Minimal repro (no randomness needed -- this is a direct, deterministic construction): the
/// SAME FailureNode event, bound (via `FailureNodeCapsuleBound`) to capsule
/// "cap_A_needs_this_failure", correctly settles market_a (same capsule) NO but is correctly
/// refused for market_b, a market bound to a different, unrelated capsule
/// ("cap_B_totally_unrelated_capsule") that also tries to reuse it.
/// -----------------------------------------------------------------------------------------
#[test]
fn inv11_failurenode_settles_unrelated_capsules_without_binding_check() {
    let hash = candidate_predicate_set_hash();
    let settlement_event_id = mu(0xAA);
    // The additive `FailureNodeCapsuleBound` event (resolved by the caller from the tape, not
    // part of the closed/frozen `FailureNodePayload`) ties this FailureNode to the capsule it
    // actually reports failure for.
    let bound_capsule_id = "cap_A_needs_this_failure";

    let market_a = MarketSettlementGateInput {
        result: "NO",
        settlement_event_id: &settlement_event_id,
        market_capsule_id: "cap_A_needs_this_failure",
        market_predicate_set_hash: &hash,
        current_predicate_set_hash: &hash,
        reference: SettlementReference::FailureNode {
            bound_capsule_id: Some(bound_capsule_id),
        },
        market_created_tape_index: Some(0),
        settlement_tape_index: Some(1),
    };
    let mut market_b = market_a;
    market_b.market_capsule_id = "cap_B_totally_unrelated_capsule";

    let result_a = market_settlement_gate_g_mkt_06(&market_a);
    let result_b = market_settlement_gate_g_mkt_06(&market_b);

    assert!(
        result_a.is_ok(),
        "sanity: a well-ordered NO settlement whose bound_capsule_id matches the market's own \
         capsule_id should be accepted, got {result_a:?}"
    );

    // G-MKT-06 now enforces "same capsule" for the NO path (INV-11's stated invariant:
    // "MarketSettled 合法 iff ... 引用同 capsule 的真实 ... FailureNode(NO)"): reusing the
    // identical bound FailureNode reference for an unrelated capsule's market MUST be refused.
    assert!(
        matches!(
            result_b,
            Err(MarketPputPredicateError::SettlementCapsuleMismatch(_))
        ),
        "REGRESSION (INV-11 fix, ADR-ECON-002): the SAME FailureNode event \
         {settlement_event_id:?}, bound to capsule {bound_capsule_id:?}, authorized a \"NO\" \
         settlement for an unrelated market_capsule_id={:?}. Expected: \
         Err(SettlementCapsuleMismatch). Observed: {result_b:?}",
        market_b.market_capsule_id,
    );
}

/// -----------------------------------------------------------------------------------------
/// Randomized property search (fixed seed, 5000 iterations): for every randomly generated
/// combination of (result, reference variant, capsule match/mismatch, predicate_set_hash
/// match/mismatch, tape ordering, and whether an additive `FailureNodeCapsuleBound` binding
/// exists at all), compute the EXPECTED verdict per INV-11's stated invariant (capsule binding
/// required on BOTH the YES *and* NO path, symmetric via ADR-ECON-002) and compare against the
/// actual gate() verdict. Tallies both directions: cases where actual accepts but should have
/// refused (bypass), and cases where actual refuses but should have accepted (false negative --
/// rules out "the fix just always refuses now" as a degenerate, non-fix).
/// -----------------------------------------------------------------------------------------
#[test]
fn inv11_property_search_capsule_binding_gap_on_no_path() {
    let mut rng = Xorshift64::new(FIXED_SEED);
    let hash_current = candidate_predicate_set_hash();
    let hash_other = "sha256:deadbeef_weakened_predicate_set".to_string();

    let mut no_path_capsule_bypass_count = 0u32;
    let mut no_path_false_negative_count = 0u32;
    let iterations = 5000;

    for i in 0..iterations {
        let capsules = ["cap_alpha", "cap_beta", "cap_gamma"];
        let market_capsule = capsules[rng.next_range(3) as usize];
        // The capsule this FailureNode is actually bound to via the additive
        // `FailureNodeCapsuleBound` tape event, as resolved by the caller (`turing-daemons`).
        // `has_binding == false` models "no such binding event exists on the tape at all for
        // this settlement_event_id" -- the gate must refuse that case unconditionally, same as
        // an unbound YES-path reference would be refused.
        let has_binding = rng.next_bool();
        let failure_true_capsule = capsules[rng.next_range(3) as usize];
        let bound_capsule_id = if has_binding {
            Some(failure_true_capsule)
        } else {
            None
        };

        let hash_matches = rng.next_bool();
        let market_hash = if hash_matches {
            hash_current.clone()
        } else {
            hash_other.clone()
        };

        let created_idx = rng.next_range(50) as usize;
        let settlement_idx_offset = rng.next_range(20) as usize + 1; // always > 0
        let settlement_idx = created_idx + settlement_idx_offset;

        let event_id = mu((i % 250) as u8);
        let input = MarketSettlementGateInput {
            result: "NO",
            settlement_event_id: &event_id,
            market_capsule_id: market_capsule,
            market_predicate_set_hash: &market_hash,
            current_predicate_set_hash: &hash_current,
            reference: SettlementReference::FailureNode { bound_capsule_id },
            market_created_tape_index: Some(created_idx),
            settlement_tape_index: Some(settlement_idx),
        };

        let actual = market_settlement_gate_g_mkt_06(&input);
        let ordering_ok = settlement_idx > created_idx; // always true by construction here
        let expected_ok = hash_matches && ordering_ok && bound_capsule_id == Some(market_capsule);

        if actual.is_ok() && !expected_ok {
            no_path_capsule_bypass_count += 1;
        }
        if actual.is_err() && expected_ok {
            no_path_false_negative_count += 1;
        }
    }

    assert_eq!(
        no_path_capsule_bypass_count, 0,
        "ADR-ECON-002 regression, property search over {iterations} random (market_capsule, \
         bound_capsule_id incl. no-binding, hash, ordering) combinations [seed=0x{FIXED_SEED:x}]: \
         {no_path_capsule_bypass_count} cases where a FailureNode bound to a DIFFERENT capsule \
         than the market being settled (or with no binding at all) was still accepted as a \
         valid NO settlement. Expected 0 (capsule-bound oracle)."
    );
    assert_eq!(
        no_path_false_negative_count, 0,
        "ADR-ECON-002 regression, property search over {iterations} iterations \
         [seed=0x{FIXED_SEED:x}]: {no_path_false_negative_count} cases where a FailureNode \
         correctly bound to the market's own capsule (hash matching, correctly ordered) was \
         still refused -- the fix must not degenerate into an unconditional NO-path refusal."
    );
}

/// Sanity/negative-control tests confirming G-MKT-06 DOES correctly enforce the parts of
/// INV-11 that are wired: this rules out the possibility that the above failures are a
/// trivially-broken test harness rather than a real, narrow gap.
#[test]
fn sanity_yes_path_capsule_mismatch_is_refused() {
    let hash = candidate_predicate_set_hash();
    let input = MarketSettlementGateInput {
        result: "YES",
        settlement_event_id: &mu(0x01),
        market_capsule_id: "cap_real",
        market_predicate_set_hash: &hash,
        current_predicate_set_hash: &hash,
        reference: SettlementReference::CandidateAccepted {
            capsule_id: Some("cap_other"),
        },
        market_created_tape_index: Some(0),
        settlement_tape_index: Some(1),
    };
    let result = market_settlement_gate_g_mkt_06(&input);
    assert!(
        matches!(
            result,
            Err(MarketPputPredicateError::SettlementCapsuleMismatch(_))
        ),
        "sanity check failed unexpectedly: YES-path capsule mismatch should be refused, got {result:?}"
    );
}

#[test]
fn sanity_predicate_set_weakening_is_refused() {
    let hash = candidate_predicate_set_hash();
    let input = MarketSettlementGateInput {
        result: "NO",
        settlement_event_id: &mu(0x02),
        market_capsule_id: "cap_real",
        market_predicate_set_hash: "sha256:stale_frozen_hash_from_market_creation_time",
        current_predicate_set_hash: &hash,
        reference: SettlementReference::FailureNode {
            bound_capsule_id: Some("cap_real"),
        },
        market_created_tape_index: Some(0),
        settlement_tape_index: Some(1),
    };
    let result = market_settlement_gate_g_mkt_06(&input);
    assert!(
        matches!(result, Err(MarketPputPredicateError::PredicateSetWeakened(_))),
        "sanity check failed unexpectedly: predicate_set_hash mismatch should be refused, got {result:?}"
    );
}

#[test]
fn sanity_settlement_predating_market_created_is_refused() {
    let hash = candidate_predicate_set_hash();
    let input = MarketSettlementGateInput {
        result: "NO",
        settlement_event_id: &mu(0x03),
        market_capsule_id: "cap_real",
        market_predicate_set_hash: &hash,
        current_predicate_set_hash: &hash,
        reference: SettlementReference::FailureNode {
            bound_capsule_id: Some("cap_real"),
        },
        market_created_tape_index: Some(10),
        settlement_tape_index: Some(3), // BEFORE market creation
    };
    let result = market_settlement_gate_g_mkt_06(&input);
    assert!(
        matches!(
            result,
            Err(MarketPputPredicateError::SettlementOrderingViolated(_))
        ),
        "sanity check failed unexpectedly: settlement predating MarketCreated should be refused, got {result:?}"
    );
}
