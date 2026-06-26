//! Structural admission checks — the pre-predicate gate of the append algorithm
//! (`pack/03_contracts/operation/append_algorithm_v5_3_1.md` §1.1, A1–A8).
//!
//! These are pure functions over closed values (NO I/O). They answer *"is this a
//! well-formed, in-epoch, on-tip, schema-known append?"* — never *"should the world
//! advance?"*. A rejection is a [`RejectClass`] (the structural taxonomy, distinct from the
//! 17-value `FailureClass`); the append facade turns it into an `AdmissionRejected`
//! `FailureNode` (see [`crate::failure`]).
//!
//! This module currently provides **A4 — head-effect agreement**, the SG-17 admission law:
//! the carried `head_effect` is *registry-derived, never writer-trusted*, so a candidate
//! whose carried `head_effect` differs from `registry[event_type].head_effect` is rejected
//! with `HEAD_EFFECT_DISAGREEMENT` **before** the reducer runs. A forged effect therefore
//! never reaches [`crate::reducer`] and can never move a sovereign head or bump the epoch.

use turing_contracts::envelope::HeadEffect;
use turing_contracts::registry;

pub use crate::failure::RejectClass;

/// **A4 — head-effect agreement** (`append_algorithm_v5_3_1.md` A4;
/// `event_registry_v5_3_1.json:53,190`).
///
/// The single source of truth for an event's `head_effect` is its **registry row**; the
/// value carried in the writer's envelope is accepted *only if it equals that row*. Given a
/// candidate's `event_type` and its **carried** `head_effect`, this returns:
///
/// - `Err(RejectClass::UnknownEventType)` if `event_type` is outside the closed 46-event
///   registry — a closed-world reject (the registry has no row to validate against), never a
///   silent admit. (A2 also covers unknown types; A4 fails closed the same way rather than
///   trusting a writer-supplied effect for an unknown event.)
/// - `Err(RejectClass::HeadEffectDisagreement)` if `carried_head_effect !=
///   registry[event_type].head_effect` — the writer forged the effect.
/// - `Ok(())` iff `carried_head_effect == registry[event_type].head_effect`.
///
/// This is the *only* admitted path by which `head_effect` reaches the reducer, so the
/// reducer can treat the registry-derived effect as authoritative.
///
/// The returned `Result` is itself `#[must_use]`; a dropped admission verdict is a bug.
pub fn admit_head_effect(
    event_type: &str,
    carried_head_effect: HeadEffect,
) -> Result<(), RejectClass> {
    let Some(row) = registry::registry(event_type) else {
        // No registry row → cannot validate the carried effect; fail closed (closed-world).
        return Err(RejectClass::UnknownEventType);
    };
    if carried_head_effect == row.head_effect {
        Ok(())
    } else {
        Err(RejectClass::HeadEffectDisagreement)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a4_admits_only_the_registry_head_effect() {
        // ProjectLawAmended is ADVANCE in the real registry.
        assert_eq!(
            admit_head_effect("ProjectLawAmended", HeadEffect::Advance),
            Ok(())
        );
        assert_eq!(
            admit_head_effect("ProjectLawAmended", HeadEffect::Preserve),
            Err(RejectClass::HeadEffectDisagreement)
        );
    }

    #[test]
    fn a4_fails_closed_on_unknown_event() {
        assert_eq!(
            admit_head_effect("NopeNotReal", HeadEffect::Advance),
            Err(RejectClass::UnknownEventType)
        );
    }
}
