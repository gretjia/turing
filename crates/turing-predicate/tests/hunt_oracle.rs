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
/// CONFIRMED CANDIDATE #1 (INV-11): G-MKT-06 performs ZERO capsule cross-check on the NO
/// (FailureNode) path. The exact same on-tape FailureNode event -- which per its closed
/// schema carries no `capsule_id` at all -- legitimizes a "NO" settlement for ANY market,
/// regardless of which capsule that FailureNode actually reports failure for.
///
/// Minimal repro (no randomness needed -- this is a direct, deterministic construction):
/// two markets bound to two different, unrelated capsules ("cap_A_needs_this_failure" and
/// "cap_B_totally_unrelated") both attempt to settle NO referencing the SAME FailureNode
/// event id. A capsule-bound oracle must accept at most one. Both are accepted.
/// -----------------------------------------------------------------------------------------
/// NEEDS OWNER (PART D.1, capsule bug #3 / candidate #1): see the `#[ignore]` rationale on
/// `inv11_no_settlement_should_require_failure_to_reference_the_markets_own_capsule` in
/// `hunt_defense.rs` -- closing this requires a `capsule_id` field on the closed/frozen
/// `FailureNodePayload` schema (hash/wire-format change + emission-site rewiring), an
/// architecture-level decision, not a local `market_settlement_gate_g_mkt_06` fix.
#[test]
#[ignore = "NEEDS OWNER: requires adding capsule_id to the closed/frozen FailureNodePayload \
            schema (content_digest/hash format change). See PART D.1 capsule bug #3 / \
            candidate #1 in PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md."]
fn inv11_failurenode_settles_unrelated_capsules_without_binding_check() {
    let hash = candidate_predicate_set_hash();
    let settlement_event_id = mu(0xAA);

    let market_a = MarketSettlementGateInput {
        result: "NO",
        settlement_event_id: &settlement_event_id,
        market_capsule_id: "cap_A_needs_this_failure",
        market_predicate_set_hash: &hash,
        current_predicate_set_hash: &hash,
        reference: SettlementReference::FailureNode,
        market_created_tape_index: Some(0),
        settlement_tape_index: Some(1),
    };
    let mut market_b = market_a;
    market_b.market_capsule_id = "cap_B_totally_unrelated_capsule";

    let result_a = market_settlement_gate_g_mkt_06(&market_a);
    let result_b = market_settlement_gate_g_mkt_06(&market_b);

    assert!(
        result_a.is_ok(),
        "sanity: a well-ordered NO settlement should be accepted, got {result_a:?}"
    );

    // If G-MKT-06 actually enforced "same capsule" for the NO path (as INV-11's own stated
    // invariant claims: "MarketSettled 合法 iff ... 引用同 capsule 的真实 ... FailureNode(NO)"),
    // reusing the identical FailureNode reference for an unrelated capsule's market MUST be
    // refused. Observed: it is not.
    assert!(
        result_b.is_err(),
        "CONFIRMED bug candidate (INV-11): the SAME FailureNode event {settlement_event_id:?} \
         authorized a \"NO\" settlement for market_capsule_id={:?} (result={:?}) even though it \
         was ALREADY used (and accepted, result={:?}) to settle an entirely unrelated \
         market_capsule_id={:?}. G-MKT-06 (crates/turing-predicate/src/lib.rs:324-371) does no \
         capsule cross-check at all on the NO path -- any FailureNode anywhere on the tape, for \
         any capsule, settles any open market as NO as long as it is tape-ordered after that \
         market's MarketCreated. Expected: Err(SettlementCapsuleMismatch)-equivalent. Observed: {:?}",
        market_b.market_capsule_id,
        market_b.result,
        market_a.result,
        market_a.market_capsule_id,
        result_b,
    );
}

/// -----------------------------------------------------------------------------------------
/// Randomized property search (fixed seed, 5000 iterations): for every randomly generated
/// combination of (result, reference variant, capsule match/mismatch, predicate_set_hash
/// match/mismatch, tape ordering), compute the EXPECTED verdict per INV-11's stated
/// invariant (capsule binding required on BOTH the YES *and* NO path) and compare against
/// the actual gate() verdict. Tallies every case where actual accepts but a capsule-bound
/// oracle should have refused.
/// -----------------------------------------------------------------------------------------
/// NEEDS OWNER (PART D.1, capsule bug #3 / candidate #1): same rationale as
/// `inv11_failurenode_settles_unrelated_capsules_without_binding_check` above.
#[test]
#[ignore = "NEEDS OWNER: requires adding capsule_id to the closed/frozen FailureNodePayload \
            schema (content_digest/hash format change). See PART D.1 capsule bug #3 / \
            candidate #1 in PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md."]
fn inv11_property_search_capsule_binding_gap_on_no_path() {
    let mut rng = Xorshift64::new(FIXED_SEED);
    let hash_current = candidate_predicate_set_hash();
    let hash_other = "sha256:deadbeef_weakened_predicate_set".to_string();

    let mut no_path_capsule_bypass_count = 0u32;
    let iterations = 5000;

    for i in 0..iterations {
        let capsules = ["cap_alpha", "cap_beta", "cap_gamma"];
        let market_capsule = capsules[rng.next_range(3) as usize];
        // The "true" capsule this FailureNode actually reports failure for -- unknowable to
        // the gate (schema has no field for it), but this is the ground truth we compare
        // against to detect cross-capsule reuse.
        let failure_true_capsule = capsules[rng.next_range(3) as usize];

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
            reference: SettlementReference::FailureNode,
            market_created_tape_index: Some(created_idx),
            settlement_tape_index: Some(settlement_idx),
        };

        let actual = market_settlement_gate_g_mkt_06(&input);
        let ordering_ok = settlement_idx > created_idx; // always true by construction here
        let expected_ok_if_capsule_bound = hash_matches && ordering_ok && market_capsule == failure_true_capsule;

        if actual.is_ok() && !expected_ok_if_capsule_bound && market_capsule != failure_true_capsule {
            no_path_capsule_bypass_count += 1;
        }
    }

    assert_eq!(
        no_path_capsule_bypass_count, 0,
        "CONFIRMED bug candidate (INV-11), property search over {iterations} random \
         (market_capsule, unrelated failure-true-capsule, hash, ordering) combinations \
         [seed=0x{FIXED_SEED:x}]: {no_path_capsule_bypass_count} cases where a FailureNode for \
         a DIFFERENT capsule than the market being settled was still accepted as a valid NO \
         settlement. Expected 0 (capsule-bound oracle). Observed: {no_path_capsule_bypass_count} \
         out of every hash-matching, correctly-ordered, cross-capsule case in this loop \
         (i.e. essentially all of them, since the gate never reads a capsule identity for \
         FailureNode at all)."
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
        reference: SettlementReference::FailureNode,
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
        reference: SettlementReference::FailureNode,
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
