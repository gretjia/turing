//! The pure head-transition reducer — STEP 7 of the append algorithm, INV-3, and the
//! `greenfield_spec_v5_3_1.md` §5.3 post-state derivation.
//!
//! This is a **pure synchronous function over closed values**: no I/O, no clock, no
//! randomness. Given the observed pre-state (a [`PreState`]), the *registry-derived*
//! class + head effect, and the predicate product, it decides the post-state HeadSet and
//! which single sovereign head (if any) moved. The Git Tape append calls this to choose
//! the ref-transaction shape; replay calls it to fold a frozen Tape.
//!
//! Frozen laws encoded here (`event_registry_v5_3_1.json:44-51`, append algo INV-3,
//! spec §5.3):
//! - `tape_tip` ALWAYS advances to the new event OID.
//! - `accepted_head` advances **iff** `class == SOVEREIGN_ACCEPT ∧ head_effect == ADVANCE
//!   ∧ product == PASS`; else it carries forward.
//! - `authorization_head` advances **iff** `class == AUTHORIZATION ∧ head_effect ==
//!   ADVANCE ∧ product == PASS`; else it carries forward.
//! - At most one sovereign head moves per transition.
//! - On `FAIL`, `NOT_RUN`, any PRESERVE class, or AdmissionRejected: only `tape_tip`
//!   moves; both heads carry forward unchanged (failure-is-state / heads preserved).
//!
//! Authority-epoch handling (the `expected.authority_epoch` rule, spec:215-217) is provided
//! by [`apply_with_epoch`] (SG-17): [`apply`] still carries `authority_epoch` forward
//! unchanged (the head-only law SG-15/16 verify), while [`apply_with_epoch`] additionally
//! applies the authority-transfer increment. SG-13 extends the same decision with
//! failure-node construction.

use turing_contracts::envelope::{HeadEffect, PredicateProduct};
use turing_contracts::payload::ProjectLawAmended;
use turing_contracts::registry::EventClass;

/// The canonical event name whose `project_law_amended.v1` payload may move the authority
/// epoch (`greenfield_spec_v5_3_1.md:216, 287`). Only this SOVEREIGN_ACCEPT event qualifies;
/// every other event carries the epoch forward.
pub const AUTHORITY_TRANSFER_EVENT_TYPE: &str = "ProjectLawAmended";

/// The observed, coherent pre-state a candidate is appended against.
///
/// `tape_tip == None` means *genesis* (an empty Tape): the first event is a root commit
/// and there is no prior accepted/authorization head. Post-genesis, `tape_tip` and
/// `accepted_head` are always `Some`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PreState {
    /// Observed `tape_tip` (`mu:`…) or `None` at genesis.
    pub tape_tip: Option<String>,
    /// Observed `authorization_head` (`mu:`…) or `None`.
    pub authorization_head: Option<String>,
    /// Observed `accepted_head` (`mu:`…) or `None` at genesis.
    pub accepted_head: Option<String>,
    /// The pre-state fencing epoch.
    pub authority_epoch: u64,
    /// The sequence number of the parent event (`None` at genesis ⇒ this event is 0).
    pub parent_sequence: Option<u64>,
}

impl PreState {
    /// The empty pre-state of a fresh Tape (everything `None`, epoch 0).
    #[must_use]
    pub fn genesis() -> Self {
        PreState {
            tape_tip: None,
            authorization_head: None,
            accepted_head: None,
            authority_epoch: 0,
            parent_sequence: None,
        }
    }

    /// The `sequence` the next appended event must carry: `parent_sequence + 1`, or `0`
    /// at genesis.
    #[must_use]
    pub fn next_sequence(&self) -> u64 {
        self.parent_sequence.map_or(0, |s| s + 1)
    }
}

/// Which single sovereign head a transition moved (beyond `tape_tip`, which always moves).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HeadMoved {
    /// No sovereign head moved; only `tape_tip` advanced.
    None,
    /// `authorization_head` advanced (AUTHORIZATION + ADVANCE + PASS).
    AuthorizationHead,
    /// `accepted_head` advanced (SOVEREIGN_ACCEPT + ADVANCE + PASS).
    AcceptedHead,
}

/// The reducer's decision: the derived post-state heads + which one moved.
///
/// All head fields are the *post-state* values (`mu:`…). `tape_tip` is the new event OID;
/// the others are either the new OID (if they moved) or carried forward from the
/// pre-state.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeadDecision {
    /// Post-state `tape_tip` — always the new event OID.
    pub tape_tip: String,
    /// Post-state `authorization_head` (`mu:`…) or `None`.
    pub authorization_head: Option<String>,
    /// Post-state `accepted_head` (`mu:`…) or `None` — `Some` whenever the new event is a
    /// PASSed SOVEREIGN_ACCEPT, otherwise carries the pre-state forward.
    pub accepted_head: Option<String>,
    /// The post-state authority epoch (carried forward by this reducer; SG-17 extends).
    pub authority_epoch: u64,
    /// Which sovereign head (if any) moved.
    pub head_moved: HeadMoved,
}

/// Apply the frozen head-transition law.
///
/// `new_event_oid` is the `mu:`-prefixed OID Git just minted for the final event. `class`
/// and `registry_head_effect` are **registry-derived** (never taken from the writer's
/// envelope); `product` is the predicate product for the final event.
///
/// Returns the derived post-state + the single head that moved. This function is the
/// sole authority for "did a sovereign head advance?" — the Tape append must move exactly
/// the ref this decision names and no other.
#[must_use]
pub fn apply(
    pre: &PreState,
    class: EventClass,
    registry_head_effect: HeadEffect,
    product: PredicateProduct,
    new_event_oid: &str,
) -> HeadDecision {
    // A sovereign head may advance only on an ADVANCE-class event that PASSed.
    let advancing =
        registry_head_effect == HeadEffect::Advance && product == PredicateProduct::Pass;

    let mut authorization_head = pre.authorization_head.clone();
    let mut accepted_head = pre.accepted_head.clone();
    let mut head_moved = HeadMoved::None;

    if advancing {
        match class {
            EventClass::SovereignAccept => {
                accepted_head = Some(new_event_oid.to_string());
                head_moved = HeadMoved::AcceptedHead;
            }
            EventClass::Authorization => {
                authorization_head = Some(new_event_oid.to_string());
                head_moved = HeadMoved::AuthorizationHead;
            }
            // ADVANCE is registry-exclusive to SOVEREIGN_ACCEPT / AUTHORIZATION; any other
            // class with an ADVANCE effect is a registry contradiction the admission layer
            // rejects before reaching here. Defensively, move no head.
            EventClass::Proposal
            | EventClass::Observation
            | EventClass::Receipt
            | EventClass::Failure
            | EventClass::Economy => {}
        }
    }

    HeadDecision {
        tape_tip: new_event_oid.to_string(),
        authorization_head,
        accepted_head,
        authority_epoch: pre.authority_epoch,
        head_moved,
    }
}

/// Whether a candidate qualifies to **increment** the authority epoch, per the frozen rule
/// (`greenfield_spec_v5_3_1.md:215-217, 287`): a *valid PASSed human-signed authority-transfer
/// `ProjectLawAmended`* whose `new_authority_epoch == authority_epoch_before + 1`.
///
/// ALL of the following must hold (any miss ⇒ no increment, epoch carried forward):
/// - `event_type == "ProjectLawAmended"` (only this event may bump the epoch);
/// - `product == PASS` (an unverified/failed amendment never bumps it);
/// - a `project_law_amended.v1` payload is present and is a **human-signed AUTHORITY_TRANSFER**;
/// - `payload.new_authority_epoch == authority_epoch_before + 1` (increment by EXACTLY ONE).
///
/// Returns the post-state epoch: `before + 1` on the qualifying case, else `before`. The
/// `+ 1` arithmetic and the "exactly one" check live here so the carried `new_authority_epoch`
/// is never trusted to make a larger (or backward) jump.
#[must_use]
fn authority_epoch_after(
    authority_epoch_before: u64,
    event_type: &str,
    product: PredicateProduct,
    payload: Option<&ProjectLawAmended>,
) -> u64 {
    // Gate 1: only a PASSed ProjectLawAmended may even be considered.
    if event_type != AUTHORITY_TRANSFER_EVENT_TYPE || product != PredicateProduct::Pass {
        return authority_epoch_before;
    }
    // Gate 2: a human-signed AUTHORITY_TRANSFER payload must be present.
    let Some(payload) = payload else {
        return authority_epoch_before;
    };
    if !payload.is_human_signed_authority_transfer() {
        return authority_epoch_before;
    }
    // Gate 3: the proposed epoch must be EXACTLY before + 1 (no larger jump, no decrement, no
    // no-op). `checked_add` keeps the arithmetic total; an overflow simply does not qualify.
    match authority_epoch_before.checked_add(1) {
        Some(next) if payload.new_authority_epoch == next => next,
        _ => authority_epoch_before,
    }
}

/// Apply the frozen head-transition law **and** the authority-epoch transition.
///
/// This is [`apply`] plus the `expected.authority_epoch` rule (`greenfield_spec_v5_3_1.md:
/// 215-217, 287`): the post-state epoch equals `payload.new_authority_epoch` **iff** the event
/// is a valid PASSed human-signed authority-transfer `ProjectLawAmended` whose
/// `new_authority_epoch == authority_epoch_before + 1`; otherwise the epoch carries forward.
/// See [`authority_epoch_after`] for the exact qualification.
///
/// `event_type`, `class` and `registry_head_effect` are all **registry-derived** (the carried
/// `head_effect` must have already passed admission A4 — see [`crate::admission`] — so a forged
/// effect never reaches here). `payload` is the parsed `project_law_amended.v1` when the event
/// carries one, else `None`.
///
/// The head movement is identical to [`apply`]; only `authority_epoch` may differ. On the
/// single qualifying case both the epoch increments by one *and* `accepted_head` advances
/// (ProjectLawAmended is SOVEREIGN_ACCEPT + ADVANCE), coupled by the same PASS.
#[must_use]
pub fn apply_with_epoch(
    pre: &PreState,
    event_type: &str,
    class: EventClass,
    registry_head_effect: HeadEffect,
    product: PredicateProduct,
    payload: Option<&ProjectLawAmended>,
    new_event_oid: &str,
) -> HeadDecision {
    let mut decision = apply(pre, class, registry_head_effect, product, new_event_oid);
    decision.authority_epoch =
        authority_epoch_after(pre.authority_epoch, event_type, product, payload);
    decision
}
