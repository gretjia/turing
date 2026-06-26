//! SG-13 — failure-node construction with head preservation (INV-4, "failure-is-state").
//!
//! Pure synchronous functions over closed values (NO I/O). They build the **exactly one
//! final event** the append algorithm lands on `tape_tip` for a non-PASS outcome, and they
//! reuse [`crate::reducer::apply`] to derive the post-state HeadSet — proving that **no
//! sovereign head advances on a failure** (`pack/03_contracts/operation/append_algorithm_v5_3_1.md`
//! STEP 2/4/5, INV-4; `failure_class_registry_v5_3_1.json`).
//!
//! Two distinct failure taxonomies (kept separate, never conflated):
//!
//! 1. **Admission `reject_class`** ([`RejectClass`]) — the structural / pre-predicate gate
//!    A1–A8. On a reject, [`build_admission_rejected`] produces an [`AdmissionRejected`]:
//!    a `FailureNode`-class final event with `predicate_product = NOT_RUN`,
//!    `verified = false`, carrying the `reject_class` + the `raw_input_digest` (so the
//!    rejected raw bytes are rebuildable from the Tape). **"parse failure" lives HERE**
//!    (`MALFORMED_BYTES`), NOT in the 17-set.
//!
//! 2. **`FailureClass` v1** (the closed 17-set, in [`turing_contracts::failure`]) — for a
//!    predicate / observer FAIL. [`build_failure_node`] produces a [`FailureNode`]: a
//!    `FailureNode`-class final event with `predicate_product = FAIL`, `verified = false`,
//!    carrying a `failure_node_payload.v1`. [`classify`] maps each SG-13 [`FailureMode`] to
//!    its FailureClass; [`turing_contracts::failure::dispose`] then maps that to the frozen
//!    recovery disposition.
//!
//! Both kinds of final event are the registry event `FailureNode` (class `FAILURE`,
//! `head_effect = PRESERVE`, `predicate_required = false`), so feeding them through the
//! reducer carries BOTH sovereign heads forward byte-unchanged and moves only `tape_tip`.

use turing_contracts::envelope::{HeadEffect, PredicateProduct};
use turing_contracts::failure::{FailureClass, FailureNodePayload};
use turing_contracts::registry::EventClass;

use crate::reducer::{self, HeadDecision, PreState};

/// The structural admission `reject_class` (A1–A8 of the append algorithm, plus the
/// pre-parse `MALFORMED_BYTES`). This is a **distinct** taxonomy from the 17-value
/// [`FailureClass`]; an `AdmissionRejected` carries one of these, never a FailureClass.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum RejectClass {
    /// A1 — the raw bytes are not one parseable `turingos.jcs.v1` object ("parse failure").
    MalformedBytes,
    /// A2 — `event_type` / `event_schema_id` is outside the closed 46-event registry.
    UnknownEventType,
    /// A3 — a required `MicroEventEnvelope.v1` field is missing, or `event_id` /
    /// `head_set_after` is present.
    EnvelopeShapeViolation,
    /// A4 — the carried `head_effect` differs from the registry row.
    HeadEffectDisagreement,
    /// A5 — `sha256(JCS(payload)) != content_digest == payload_hash`.
    PayloadHashMismatch,
    /// A6 — `prev_tape_tip != observed tape_tip` (a non-fast-forward parent).
    NonFfParent,
    /// A7 — `writer_id` is not the accept-authority of the current `authority_epoch`.
    WriterOrEpochViolation,
    /// A8 — `accepted_head_before` is not an ancestor of the observed `tape_tip`.
    AncestryViolation,
    /// An otherwise-admissible envelope whose declared transition is illegal.
    IllegalTransition,
}

impl RejectClass {
    /// The stable discriminator string for this admission reject class.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            RejectClass::MalformedBytes => "MALFORMED_BYTES",
            RejectClass::UnknownEventType => "UNKNOWN_EVENT_TYPE",
            RejectClass::EnvelopeShapeViolation => "ENVELOPE_SHAPE_VIOLATION",
            RejectClass::HeadEffectDisagreement => "HEAD_EFFECT_DISAGREEMENT",
            RejectClass::PayloadHashMismatch => "PAYLOAD_HASH_MISMATCH",
            RejectClass::NonFfParent => "NON_FF_PARENT",
            RejectClass::WriterOrEpochViolation => "WRITER_OR_EPOCH_VIOLATION",
            RejectClass::AncestryViolation => "ANCESTRY_VIOLATION",
            RejectClass::IllegalTransition => "ILLEGAL_TRANSITION",
        }
    }

    /// A `reject_class` is NEVER one of the 17 `FailureClass` values — the two taxonomies
    /// are disjoint by construction. Always `false`; encodes the invariant explicitly so a
    /// caller (and the SG-13 test) can bind it.
    #[must_use]
    pub fn is_failure_class(self) -> bool {
        false
    }
}

/// The four SG-13 failure modes (plus the schema-shape variant of a predicate FAIL),
/// mapped to a [`FailureClass`] by [`classify`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum FailureMode {
    /// The candidate predicate failed on logic / semantics → `SEMANTIC_FAILURE`.
    PredicateLogic,
    /// The candidate's output violated its declared schema shape → `OUTPUT_SCHEMA_VIOLATION`.
    SchemaShape,
    /// A soft (recoverable) timeout elapsed → `TIMEOUT_SOFT`.
    TimeoutSoft,
    /// A hard (terminal) timeout elapsed → `TIMEOUT_HARD`.
    TimeoutHard,
    /// A retryable network-condition timeout → `TIMEOUT_OR_NETWORK_RETRY`.
    TimeoutOrNetworkRetry,
    /// An observer disagreed with the candidate's claimed effect → `OBSERVER_MISMATCH`.
    ObserverMismatch,
}

/// Map a SG-13 [`FailureMode`] to its frozen [`FailureClass`].
///
/// `pack`-bound mapping (append algorithm STEP 4 `classify`; CONTEXT.md SG-13):
/// predicate-logic FAIL → `SEMANTIC_FAILURE`; schema-shape FAIL → `OUTPUT_SCHEMA_VIOLATION`;
/// timeouts → `TIMEOUT_SOFT` / `TIMEOUT_HARD` / `TIMEOUT_OR_NETWORK_RETRY`;
/// observer mismatch → `OBSERVER_MISMATCH`.
#[must_use]
pub fn classify(mode: FailureMode) -> FailureClass {
    match mode {
        FailureMode::PredicateLogic => FailureClass::SemanticFailure,
        FailureMode::SchemaShape => FailureClass::OutputSchemaViolation,
        FailureMode::TimeoutSoft => FailureClass::TimeoutSoft,
        FailureMode::TimeoutHard => FailureClass::TimeoutHard,
        FailureMode::TimeoutOrNetworkRetry => FailureClass::TimeoutOrNetworkRetry,
        FailureMode::ObserverMismatch => FailureClass::ObserverMismatch,
    }
}

/// The canonical registry event name a failure node carries (`event_type`). Both an
/// `AdmissionRejected` and a predicate-FAIL `FailureNode` are this one frozen event — no
/// 47th event is introduced (append algorithm §5 frozen-resolution).
pub const FAILURE_NODE_EVENT_TYPE: &str = "FailureNode";

/// The derived facts about the single final failure event: its predicate product, that it
/// is `verified == false`, and the head decision from the reducer (which MUST preserve both
/// sovereign heads). This is the common core of both failure constructors.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureFinalization {
    /// The registry event name (`FailureNode`).
    pub event_type: &'static str,
    /// `NOT_RUN` for an `AdmissionRejected`, `FAIL` for a predicate-FAIL failure node.
    pub product: PredicateProduct,
    /// Always `false` — a failure node is never a verified transition.
    pub verified: bool,
    /// The reducer's post-state head decision: `tape_tip` advanced to the failure node
    /// OID, both sovereign heads carried forward, `head_moved == None`.
    pub head_decision: HeadDecision,
}

/// An `AdmissionRejected` final event: a `FailureNode`-class event carrying the structural
/// `reject_class` + the `raw_input_digest` (append algorithm STEP 2; §5 frozen-resolution).
/// `predicate_product = NOT_RUN`, `verified = false`. It does NOT carry a 17-set
/// `FailureClass` payload.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdmissionRejected {
    /// The common failure finalization (product NOT_RUN, verified=false, heads preserved).
    pub finalization: FailureFinalization,
    /// The structural admission reject class (A1–A8 / `MALFORMED_BYTES`).
    pub reject_class: RejectClass,
    /// `sha256:` + 64hex over the literal raw input bytes (pre-parse) — makes the rejected
    /// input rebuildable from the Tape (append algorithm STEP 1 `raw_input_digest`).
    pub raw_input_digest: String,
}

impl AdmissionRejected {
    /// An `AdmissionRejected` never carries a `failure_node_payload.v1` (the 17-set payload)
    /// — its discriminator is `reject_class` + `raw_input_digest`. Always `None`.
    #[must_use]
    pub fn failure_node_payload(&self) -> Option<&FailureNodePayload> {
        None
    }

    /// The reducer's post-state head decision (heads preserved).
    #[must_use]
    pub fn head_decision(&self) -> &HeadDecision {
        &self.finalization.head_decision
    }
}

/// A predicate-FAIL `FailureNode` final event: a `FailureNode`-class event carrying a
/// `failure_node_payload.v1` (one of the 17 [`FailureClass`] values). `predicate_product =
/// FAIL`, `verified = false`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureNode {
    /// The common failure finalization (product FAIL, verified=false, heads preserved).
    pub finalization: FailureFinalization,
    /// The `failure_node_payload.v1` carried on the event (verified=false const).
    pub payload: FailureNodePayload,
}

impl FailureNode {
    /// The `failure_node_payload.v1` carried on this failure node.
    #[must_use]
    pub fn failure_node_payload(&self) -> Option<&FailureNodePayload> {
        Some(&self.payload)
    }

    /// The reducer's post-state head decision (heads preserved).
    #[must_use]
    pub fn head_decision(&self) -> &HeadDecision {
        &self.finalization.head_decision
    }
}

/// Run the reducer for a failure node and assert (in debug) that it preserved both
/// sovereign heads. A failure node is the registry event `FailureNode` — class `FAILURE`,
/// `head_effect = PRESERVE` — so for ANY non-PASS product the reducer moves no head.
fn finalize_failure(
    pre: &PreState,
    product: PredicateProduct,
    failure_node_oid: &str,
) -> FailureFinalization {
    // A FailureNode is class FAILURE with registry head_effect PRESERVE: no head can move.
    let decision = reducer::apply(
        pre,
        EventClass::Failure,
        HeadEffect::Preserve,
        product,
        failure_node_oid,
    );

    // INV-4 invariant (encoded, not assumed): heads carried forward, none moved.
    debug_assert_eq!(decision.head_moved, reducer::HeadMoved::None);
    debug_assert_eq!(decision.authorization_head, pre.authorization_head);
    debug_assert_eq!(decision.accepted_head, pre.accepted_head);

    FailureFinalization {
        event_type: FAILURE_NODE_EVENT_TYPE,
        product,
        verified: false,
        head_decision: decision,
    }
}

/// STEP 2 — build the `AdmissionRejected` final event for a structural admission failure.
///
/// `reject_class` is the A1–A8 / `MALFORMED_BYTES` cause; `raw_input_digest` is
/// `sha256:` + 64hex over the literal raw bytes (computed pre-parse). `pre` is the observed
/// coherent pre-state; `failure_node_oid` is the `mu:`-prefixed OID the Git mint would
/// assign the failure node commit. The result has `product = NOT_RUN`, `verified = false`,
/// and a head decision that preserves both sovereign heads (only `tape_tip` advances).
#[must_use]
pub fn build_admission_rejected(
    reject_class: RejectClass,
    raw_input_digest: &str,
    pre: &PreState,
    failure_node_oid: &str,
) -> AdmissionRejected {
    let finalization = finalize_failure(pre, PredicateProduct::NotRun, failure_node_oid);
    AdmissionRejected {
        finalization,
        reject_class,
        raw_input_digest: raw_input_digest.to_string(),
    }
}

/// STEP 4 — build the predicate-FAIL `FailureNode` final event.
///
/// `failure_class` is one of the 17 (from [`classify`]); `candidate_digest` /
/// `observation_digest` are `sha256:` + 64hex; `detail` is optional free text. `pre` is the
/// observed coherent pre-state; `failure_node_oid` is the `mu:`-prefixed minted OID. The
/// result has `product = FAIL`, `verified = false`, a `failure_node_payload.v1`, and a head
/// decision that preserves both sovereign heads (only `tape_tip` advances).
#[must_use]
pub fn build_failure_node(
    failure_class: FailureClass,
    candidate_digest: &str,
    observation_digest: &str,
    detail: Option<&str>,
    pre: &PreState,
    failure_node_oid: &str,
) -> FailureNode {
    let finalization = finalize_failure(pre, PredicateProduct::Fail, failure_node_oid);
    let payload = FailureNodePayload::new(
        failure_class,
        candidate_digest,
        observation_digest,
        detail.map(str::to_string),
    );
    FailureNode {
        finalization,
        payload,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use turing_contracts::failure::{Disposition, dispose};

    fn pre() -> PreState {
        PreState {
            tape_tip: Some(format!("mu:{}", "11".repeat(32))),
            authorization_head: Some(format!("mu:{}", "aa".repeat(32))),
            accepted_head: Some(format!("mu:{}", "bb".repeat(32))),
            authority_epoch: 3,
            parent_sequence: Some(9),
        }
    }

    #[test]
    fn classify_covers_every_mode_to_the_contract_class() {
        assert_eq!(
            classify(FailureMode::PredicateLogic),
            FailureClass::SemanticFailure
        );
        assert_eq!(
            classify(FailureMode::SchemaShape),
            FailureClass::OutputSchemaViolation
        );
        assert_eq!(
            classify(FailureMode::TimeoutSoft),
            FailureClass::TimeoutSoft
        );
        assert_eq!(
            classify(FailureMode::TimeoutHard),
            FailureClass::TimeoutHard
        );
        assert_eq!(
            classify(FailureMode::TimeoutOrNetworkRetry),
            FailureClass::TimeoutOrNetworkRetry
        );
        assert_eq!(
            classify(FailureMode::ObserverMismatch),
            FailureClass::ObserverMismatch
        );
    }

    #[test]
    fn admission_rejected_is_not_run_and_preserves_heads() {
        let p = pre();
        let oid = format!("mu:{}", "cc".repeat(32));
        let r = build_admission_rejected(RejectClass::MalformedBytes, "sha256:00", &p, &oid);
        assert_eq!(r.finalization.product, PredicateProduct::NotRun);
        assert!(!r.finalization.verified);
        assert_eq!(r.head_decision().head_moved, reducer::HeadMoved::None);
        assert_eq!(r.head_decision().authorization_head, p.authorization_head);
        assert_eq!(r.head_decision().accepted_head, p.accepted_head);
        assert_eq!(r.head_decision().tape_tip, oid);
        assert!(r.failure_node_payload().is_none());
    }

    #[test]
    fn failure_node_is_fail_and_preserves_heads_and_disposes() {
        let p = pre();
        let oid = format!("mu:{}", "cc".repeat(32));
        let fc = classify(FailureMode::ObserverMismatch);
        let n = build_failure_node(fc, "sha256:01", "sha256:02", Some("x"), &p, &oid);
        assert_eq!(n.finalization.product, PredicateProduct::Fail);
        assert!(!n.finalization.verified);
        assert_eq!(n.payload.failure_class, FailureClass::ObserverMismatch);
        assert!(!n.payload.verified);
        assert_eq!(n.head_decision().head_moved, reducer::HeadMoved::None);
        assert_eq!(n.head_decision().authorization_head, p.authorization_head);
        assert_eq!(n.head_decision().accepted_head, p.accepted_head);
        assert_eq!(dispose(fc), Disposition::SafetyHalt);
    }
}
