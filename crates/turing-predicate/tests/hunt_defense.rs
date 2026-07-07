//! PART C.1 defense lens (镜头4), predicate half — "FAIL 归属 griefing" attack vector
//! (`FailureNode` has no `capsule_id`, per the crate's own module doc, so the NO settlement
//! path of G-MKT-06 cannot cross-check that the referenced failure actually pertains to the
//! market's own capsule). Written into the scratch dir first, then copied into
//! `crates/turing-predicate/tests/` as `hunt_defense.rs` (does not overwrite
//! event_registry.rs/predicate_kernel.rs).
//!
//! Methodology: asserts the STATED invariant (INV-11's intent, extended here to the
//! anti-griefing reading implied by C.1 lens 4: "a market may only be settled NO by a failure
//! that actually pertains to that market's own capsule/work"), not the exploit. A RED test =
//! confirmed candidate bug.
//!
//! Attack vector tried: an attacker with tape-write access (no special authorization is
//! required to call `market.settle` -- confirmed by reading `market_settle_response` in
//! `turing-daemons/src/lib.rs`, which never checks `writer_id` against the market's
//! `proposer_id`) settles a rival proposer's OPEN market as `NO` by referencing a
//! `FailureNode` for a COMPLETELY UNRELATED capsule that happens to already be on-tape (e.g.
//! the attacker's own trivially-failing capsule, submitted purely as settlement-fuel), forcing
//! a real, un-failed piece of work to be recorded as `MarketSettled(NO)` and destroying the
//! proposer's YES-holders' economic position / reputation signal for work that never actually
//! failed.

use turing_predicate::{
    MarketPputPredicateError, MarketSettlementGateInput, SettlementReference,
    market_settlement_gate_g_mkt_06,
};

/// CANDIDATE BUG 4 (INV-11 anti-griefing extension): `market_settlement_gate_g_mkt_06` accepts
/// ANY on-tape `FailureNode` as sufficient to settle a market `NO`, regardless of whether that
/// `FailureNode` has anything to do with the market's own `capsule_id`. The gate only checks
/// (a) well-formed event id, (b) predicate-set hash unchanged, (c) event type is `FailureNode`,
/// (d) tape ordering after `MarketCreated`. There is NO capsule cross-check on the NO path at
/// all (the YES path *does* check `capsule_id` via `SettlementCapsuleMismatch`).
/// NEEDS OWNER (PART D.1, capsule bug #3 / candidate #1): closing this gap requires adding a
/// `capsule_id` to `FailureNodePayload`, a *closed* type pinned 1:1 to the frozen
/// `pack/05_schemas/failure_node_payload.v1.schema.json` (`#[serde(deny_unknown_fields)]`,
/// `additionalProperties: false`). That schema change would: (a) alter the committed payload
/// bytes whose `sha256` is the envelope `content_digest` for every future FailureNode (a
/// wire/hash-format change, not a local bugfix), (b) require every FailureNode emission site
/// (turing-kernel, turing-daemons) to know and thread through the correct capsule_id at
/// failure time, and (c) needs a decision on backward-compat for already-committed FailureNode
/// events with no capsule_id. This is the same class of decision as the INV-13 Sybil-registry
/// GAP called out in the capsule (architecture-level, not a local fix) -- left un-forced here.
/// Left failing and `#[ignore]`d rather than silently hidden: `cargo test -- --include-ignored`
/// still surfaces it for an owner to triage.
#[test]
#[ignore = "NEEDS OWNER: closing INV-11's NO-path capsule-binding gap requires adding capsule_id \
            to FailureNodePayload, a closed/frozen-schema payload type (content_digest/hash \
            format change + emission-site rewiring), not a local predicate-gate fix. See PART D.1 \
            capsule bug #3 / candidate #1 in PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md."]
fn inv11_no_settlement_should_require_failure_to_reference_the_markets_own_capsule() {
    // Market M was created for capsule "capsule-VICTIM" (the proposer's real, unrelated work).
    let market_capsule_id = "capsule-VICTIM";
    let predicate_hash = "sha256:deadbeef";

    // The referenced on-tape event is a FailureNode -- but FailureNodePayload (per this crate's
    // own doc comment on SettlementReference::FailureNode) has NO capsule_id field, so there is
    // no way, even in principle from this data shape, to confirm it is capsule-VICTIM's own
    // failure rather than some attacker-submitted, wholly unrelated capsule's failure (e.g.
    // "capsule-ATTACKER-TRIVIAL-FAIL", deliberately produced as cheap settlement-fuel).
    let input = MarketSettlementGateInput {
        result: "NO",
        settlement_event_id: &format!("mu:{}", "b".repeat(64)),
        market_capsule_id,
        market_predicate_set_hash: predicate_hash,
        current_predicate_set_hash: predicate_hash,
        reference: SettlementReference::FailureNode,
        market_created_tape_index: Some(0),
        settlement_tape_index: Some(1), // strictly after MarketCreated: ordering check passes
    };

    let result = market_settlement_gate_g_mkt_06(&input);

    // STATED INVARIANT (anti-griefing reading): a market bound to capsule-VICTIM must not be
    // settleable NO by a FailureNode that cannot be shown to pertain to capsule-VICTIM at all.
    // Since the data shape here provides zero capsule linkage on the NO path, the honest
    // behavior would be to refuse (e.g. SettlementCapsuleMismatch-equivalent) rather than
    // silently accept any FailureNode whatsoever.
    assert!(
        result.is_err(),
        "INV-11 (anti-griefing) VIOLATED: market_settlement_gate_g_mkt_06 returned Ok(()) for a \
         NO settlement referencing a bare FailureNode with NO capsule linkage to the market's \
         own capsule_id ({market_capsule_id:?}). Any writer_id (no proposer-authorization check \
         exists in market_settle_response) can therefore force ANY open market to settle NO \
         using an unrelated capsule's genuine failure elsewhere on the same tape -- a 'FAIL \
         attribution griefing' attack that destroys a proposer's reputation/position for work \
         that never actually failed. Observed: {result:?}, expected: Err(_)."
    );
}

/// Companion confirmation: the YES path is NOT vulnerable to the equivalent attack, because it
/// DOES cross-check `capsule_id`. This asymmetry is itself evidence the NO-path gap is a real
/// oversight rather than an intentional design choice (the mechanism to close it -- a
/// capsule_id field/check -- already exists and is exercised on the YES side).
#[test]
fn inv11_yes_settlement_correctly_refuses_mismatched_capsule_control() {
    let input = MarketSettlementGateInput {
        result: "YES",
        settlement_event_id: &format!("mu:{}", "c".repeat(64)),
        market_capsule_id: "capsule-VICTIM",
        market_predicate_set_hash: "sha256:deadbeef",
        current_predicate_set_hash: "sha256:deadbeef",
        reference: SettlementReference::CandidateAccepted {
            capsule_id: Some("capsule-ATTACKER-UNRELATED"),
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
        "control case (YES settlement referencing a mismatched capsule_id) must still be \
         refused via SettlementCapsuleMismatch, got: {result:?}"
    );
}
