//! SG-13 — "Failure always appends" (`cargo nextest run -p turing-kernel --test failure_append`).
//!
//! Binds `pack/03_contracts/operation/append_algorithm_v5_3_1.md` STEP 2 (admission
//! A1–A8 → `reject_class`), STEP 4 (`build_failure_node` on FAIL; `finalize_trusted` on
//! NOT_RUN), STEP 5, and **INV-4 (failure-is-state)**: an admission rejection AND a
//! predicate FAIL ALWAYS land a `verified=false` node on `tape_tip`; the two sovereign
//! heads (`authorization_head`, `accepted_head`) are NEVER advanced by a failure.
//!
//! Two distinct failure taxonomies (do not conflate):
//!   1. admission **`RejectClass`** (structural / pre-predicate) carried by an
//!      `AdmissionRejected` failure node (`product = NOT_RUN`, `+ raw_input_digest`).
//!      "parse failure" lives HERE (`MALFORMED_BYTES`), not in the 17-set.
//!   2. **`FailureClass` v1** (the closed 17-set) for a predicate / observer FAIL,
//!      carried by a `failure_node_payload.v1` (`verified: const false`).
//!
//! The four SG-13 modes are exercised from a pre-state with NON-TRIVIAL, DISTINCT heads
//! (`authorization_head = Some(A)`, `accepted_head = Some(B)`), and for every mode the
//! produced final event is a `verified == false` failure node of the right kind/class AND
//! both sovereign heads are byte-unchanged (`head_moved == None`, A still A, B still B).
//! Dispositions are asserted against the REAL frozen map loaded from the pack (not a
//! hardcoded mirror). Public crate API only.

use turing_contracts::envelope::PredicateProduct;
use turing_contracts::failure::{Disposition, FailureClass, dispose};

use turing_kernel::failure::{self, RejectClass};
use turing_kernel::reducer::{HeadMoved, PreState};

// --- fixtures ----------------------------------------------------------------

/// `mu:` + 64 hex helper for a deterministic distinct head OID.
fn mu(byte: u8) -> String {
    format!("mu:{}", format!("{byte:02x}").repeat(32))
}

/// A pre-state with non-trivial, DISTINCT sovereign heads:
/// `tape_tip = T`, `authorization_head = A`, `accepted_head = B`, epoch 7, parent seq 41.
fn nontrivial_pre() -> PreState {
    PreState {
        tape_tip: Some(mu(0x11)),           // T
        authorization_head: Some(mu(0xaa)), // A
        accepted_head: Some(mu(0xbb)),      // B
        authority_epoch: 7,
        parent_sequence: Some(41),
    }
}

/// The minted OID Git would assign the FAILURE node commit (distinct from every head).
fn failure_node_oid() -> String {
    mu(0xcc)
}

/// `sha256:` + 64 hex helper for digests carried in payloads.
fn sha(byte: u8) -> String {
    format!("sha256:{}", format!("{byte:02x}").repeat(32))
}

/// Assert that a finalized failure carried BOTH sovereign heads forward byte-unchanged
/// and moved no head — only `tape_tip` advanced to the failure node OID.
fn assert_heads_preserved(fin: &failure::FailureFinalization, pre: &PreState, node_oid: &str) {
    let d = &fin.head_decision;
    assert_eq!(
        d.head_moved,
        HeadMoved::None,
        "a failure must move NO sovereign head"
    );
    assert_eq!(
        d.authorization_head, pre.authorization_head,
        "authorization_head must be carried forward byte-unchanged on failure"
    );
    assert_eq!(
        d.accepted_head, pre.accepted_head,
        "accepted_head must be carried forward byte-unchanged on failure"
    );
    assert_eq!(
        d.authority_epoch, pre.authority_epoch,
        "epoch carries forward on failure"
    );
    // tape_tip is the failure node's slot (it WOULD advance on append).
    assert_eq!(
        d.tape_tip, node_oid,
        "tape_tip advances to the failure node OID"
    );
    // The failure node itself is never a verified transition.
    assert!(!fin.verified, "a failure node is verified == false");
}

// --- MODE 1: parse failure → AdmissionRejected (MALFORMED_BYTES, NOT_RUN) -----

#[test]
fn parse_failure_appends_admission_rejected_and_preserves_both_heads() {
    let pre = nontrivial_pre();
    let node_oid = failure_node_oid();
    let raw_input_digest = sha(0x01);

    // STEP 2: admission rejected the raw bytes as unparseable JCS → MALFORMED_BYTES.
    let rejected = failure::build_admission_rejected(
        RejectClass::MalformedBytes,
        &raw_input_digest,
        &pre,
        &node_oid,
    );

    // It is an AdmissionRejected failure node: product NOT_RUN, verified=false, carries
    // the reject_class + the raw_input_digest (so the rejected input is rebuildable).
    assert_eq!(rejected.finalization.product, PredicateProduct::NotRun);
    assert!(!rejected.finalization.verified);
    assert_eq!(rejected.reject_class, RejectClass::MalformedBytes);
    assert_eq!(rejected.raw_input_digest, raw_input_digest);
    // It carries NO 17-set FailureClass payload (the AdmissionRejected discriminator is
    // distinct from the predicate-FAIL FailureNodePayload).
    assert!(
        rejected.failure_node_payload().is_none(),
        "AdmissionRejected carries reject_class + raw_input_digest, not a 17-set FailureClass payload"
    );

    // INV-4: both sovereign heads unchanged; only tape_tip advances.
    assert_heads_preserved(&rejected.finalization, &pre, &node_oid);

    // "parse failure" is NOT one of the 17 FailureClass values.
    assert!(
        !RejectClass::MalformedBytes.is_failure_class(),
        "MALFORMED_BYTES is a reject_class, not a FailureClass"
    );
}

// --- MODE 2: predicate-logic FAIL → FailureNode (SEMANTIC_FAILURE → REPLAN) ----

#[test]
fn predicate_logic_fail_appends_semantic_failure_node_and_preserves_heads() {
    let pre = nontrivial_pre();
    let node_oid = failure_node_oid();

    // A predicate-required candidate (e.g. CandidateAccepted, a SOVEREIGN_ACCEPT that
    // WOULD advance accepted_head on PASS) fails its candidate predicate on logic →
    // SEMANTIC_FAILURE. The FAIL outcome is a FailureNode (PRESERVE), so NO head moves.
    let fc = failure::classify(failure::FailureMode::PredicateLogic);
    assert_eq!(fc, FailureClass::SemanticFailure);

    let candidate_digest = sha(0x22);
    let observation_digest = sha(0x33);
    let fin = failure::build_failure_node(
        fc,
        &candidate_digest,
        &observation_digest,
        None,
        &pre,
        &node_oid,
    );

    let payload = fin
        .failure_node_payload()
        .expect("a predicate FAIL carries a failure_node_payload.v1");
    assert!(
        !payload.verified,
        "failure_node_payload.v1 verified is const false"
    );
    assert_eq!(payload.failure_class, FailureClass::SemanticFailure);
    assert_eq!(payload.candidate_digest, candidate_digest);
    assert_eq!(payload.observation_digest, observation_digest);
    assert_eq!(fin.finalization.product, PredicateProduct::Fail);

    assert_heads_preserved(&fin.finalization, &pre, &node_oid);

    // Disposition from the REAL frozen map (loaded from pack), not hardcoded.
    assert_eq!(dispose(FailureClass::SemanticFailure), Disposition::Replan);
}

// --- MODE 2b: schema-shape FAIL → OUTPUT_SCHEMA_VIOLATION → REPLAN -------------

#[test]
fn schema_shape_fail_appends_output_schema_violation_node_and_preserves_heads() {
    let pre = nontrivial_pre();
    let node_oid = failure_node_oid();

    let fc = failure::classify(failure::FailureMode::SchemaShape);
    assert_eq!(fc, FailureClass::OutputSchemaViolation);

    let fin = failure::build_failure_node(fc, &sha(0x44), &sha(0x55), None, &pre, &node_oid);
    let payload = fin
        .failure_node_payload()
        .expect("FailureNodePayload present");
    assert_eq!(payload.failure_class, FailureClass::OutputSchemaViolation);
    assert_eq!(fin.finalization.product, PredicateProduct::Fail);

    assert_heads_preserved(&fin.finalization, &pre, &node_oid);
    assert_eq!(
        dispose(FailureClass::OutputSchemaViolation),
        Disposition::Replan
    );
}

// --- MODE 3: timeout → FailureNode with a TIMEOUT_* class ---------------------

#[test]
fn timeout_failures_append_timeout_class_nodes_and_preserve_heads() {
    let pre = nontrivial_pre();
    let node_oid = failure_node_oid();

    // Soft timeout → TIMEOUT_SOFT → RETRY.
    let soft = failure::classify(failure::FailureMode::TimeoutSoft);
    assert_eq!(soft, FailureClass::TimeoutSoft);
    let fin_soft = failure::build_failure_node(soft, &sha(0x66), &sha(0x67), None, &pre, &node_oid);
    assert_eq!(
        fin_soft.failure_node_payload().unwrap().failure_class,
        FailureClass::TimeoutSoft
    );
    assert_eq!(fin_soft.finalization.product, PredicateProduct::Fail);
    assert_heads_preserved(&fin_soft.finalization, &pre, &node_oid);
    assert_eq!(dispose(FailureClass::TimeoutSoft), Disposition::Retry);

    // Hard timeout → TIMEOUT_HARD → TERMINATE.
    let hard = failure::classify(failure::FailureMode::TimeoutHard);
    assert_eq!(hard, FailureClass::TimeoutHard);
    let fin_hard = failure::build_failure_node(hard, &sha(0x68), &sha(0x69), None, &pre, &node_oid);
    assert_eq!(
        fin_hard.failure_node_payload().unwrap().failure_class,
        FailureClass::TimeoutHard
    );
    assert_heads_preserved(&fin_hard.finalization, &pre, &node_oid);
    assert_eq!(dispose(FailureClass::TimeoutHard), Disposition::Terminate);

    // Network-retry timeout → TIMEOUT_OR_NETWORK_RETRY → RETRY.
    let net = failure::classify(failure::FailureMode::TimeoutOrNetworkRetry);
    assert_eq!(net, FailureClass::TimeoutOrNetworkRetry);
    let fin_net = failure::build_failure_node(net, &sha(0x6a), &sha(0x6b), None, &pre, &node_oid);
    assert_eq!(
        fin_net.failure_node_payload().unwrap().failure_class,
        FailureClass::TimeoutOrNetworkRetry
    );
    assert_heads_preserved(&fin_net.finalization, &pre, &node_oid);
    assert_eq!(
        dispose(FailureClass::TimeoutOrNetworkRetry),
        Disposition::Retry
    );
}

// --- MODE 4: observer mismatch → OBSERVER_MISMATCH → SAFETY_HALT ---------------

#[test]
fn observer_mismatch_appends_observer_mismatch_node_and_preserves_heads() {
    let pre = nontrivial_pre();
    let node_oid = failure_node_oid();

    let fc = failure::classify(failure::FailureMode::ObserverMismatch);
    assert_eq!(fc, FailureClass::ObserverMismatch);

    // A detail string is optional on the payload; exercise the Some(..) path here.
    let fin = failure::build_failure_node(
        fc,
        &sha(0x77),
        &sha(0x88),
        Some("observed signal disagreed with the candidate's claimed effect"),
        &pre,
        &node_oid,
    );
    let payload = fin
        .failure_node_payload()
        .expect("FailureNodePayload present");
    assert_eq!(payload.failure_class, FailureClass::ObserverMismatch);
    assert!(
        !payload.verified,
        "failure_node_payload.v1 verified is const false"
    );
    assert!(payload.detail.is_some());
    assert_eq!(fin.finalization.product, PredicateProduct::Fail);

    assert_heads_preserved(&fin.finalization, &pre, &node_oid);

    // Observer mismatch is a safety-class failure.
    assert_eq!(
        dispose(FailureClass::ObserverMismatch),
        Disposition::SafetyHalt
    );
}

// --- cross-cutting: heads identical to the literal A / B from the pre-state ----

#[test]
fn every_failure_mode_keeps_the_exact_pre_state_head_oids() {
    let pre = nontrivial_pre();
    let node_oid = failure_node_oid();
    let a = mu(0xaa); // authorization_head
    let b = mu(0xbb); // accepted_head

    // Drive a representative of EACH taxonomy and assert the literal A / B survive.
    let adm =
        failure::build_admission_rejected(RejectClass::MalformedBytes, &sha(0x01), &pre, &node_oid);
    assert_eq!(
        adm.finalization.head_decision.authorization_head.as_deref(),
        Some(a.as_str())
    );
    assert_eq!(
        adm.finalization.head_decision.accepted_head.as_deref(),
        Some(b.as_str())
    );

    for mode in [
        failure::FailureMode::PredicateLogic,
        failure::FailureMode::SchemaShape,
        failure::FailureMode::TimeoutSoft,
        failure::FailureMode::TimeoutHard,
        failure::FailureMode::TimeoutOrNetworkRetry,
        failure::FailureMode::ObserverMismatch,
    ] {
        let fc = failure::classify(mode);
        let fin = failure::build_failure_node(fc, &sha(0x22), &sha(0x33), None, &pre, &node_oid);
        assert_eq!(
            fin.head_decision().authorization_head.as_deref(),
            Some(a.as_str()),
            "authorization_head A must survive mode {mode:?}"
        );
        assert_eq!(
            fin.head_decision().accepted_head.as_deref(),
            Some(b.as_str()),
            "accepted_head B must survive mode {mode:?}"
        );
        assert_eq!(fin.head_decision().head_moved, HeadMoved::None);
    }
}
