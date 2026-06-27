//! Embedded event registry — the closed Phase-0 table plus additive Agent Economy events.
//!
//! The ratified registry JSON (`pack/04_registries/event_registry_v5_3_1.json`) is
//! compiled into the binary with [`include_str!`] and parsed a single time behind a
//! [`std::sync::OnceLock`]. Every consumer derives `class` / `head_effect` / `target_ref`
//! / `predicate_required` from this table — they are **registry-derived, never
//! writer-trusted** (constitution Art. 0.4; `event_registry_v5_3_1.json:53`).
//!
//! The `unknown_event_policy` is `REJECT`: a lookup for an event name outside the closed
//! registry returns `None`, and the append admission turns that into an
//! `UNKNOWN_EVENT_TYPE` rejection.

use std::collections::BTreeMap;
use std::sync::OnceLock;

use serde::Deserialize;

use crate::envelope::HeadEffect;

/// The six frozen event classes. `head_effect`/head movement are a function of the
/// class plus the predicate product; the class is what selects *which* sovereign head a
/// PASS may advance.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EventClass {
    /// Advances `accepted_head` on PASS (the 12 SOVEREIGN_ACCEPT events).
    SovereignAccept,
    /// Advances `authorization_head` on PASS (the 8 AUTHORIZATION events).
    Authorization,
    /// PRESERVE; only `tape_tip` moves (the 6 PROPOSAL events).
    Proposal,
    /// PRESERVE; only `tape_tip` moves (the 9 OBSERVATION events).
    Observation,
    /// PRESERVE; only `tape_tip` moves (the 6 RECEIPT events).
    Receipt,
    /// PRESERVE; only `tape_tip` moves (the 5 FAILURE events).
    Failure,
    /// PRESERVE; only `tape_tip` moves (additive market / wallet / PPUT events).
    Economy,
}

impl EventClass {
    fn from_str(s: &str) -> Option<Self> {
        Some(match s {
            "SOVEREIGN_ACCEPT" => EventClass::SovereignAccept,
            "AUTHORIZATION" => EventClass::Authorization,
            "PROPOSAL" => EventClass::Proposal,
            "OBSERVATION" => EventClass::Observation,
            "RECEIPT" => EventClass::Receipt,
            "FAILURE" => EventClass::Failure,
            "ECONOMY" => EventClass::Economy,
            _ => return None,
        })
    }
}

/// Original Phase-0 Greenfield registry cardinality.
pub const BASELINE_EVENT_COUNT: usize = 46;

/// Additive Agent Economy events introduced by the Greenfield v1.0 upgrade.
pub const ECONOMY_EVENT_COUNT: usize = 15;

/// Total closed registry cardinality after additive economy events.
pub const TOTAL_EVENT_COUNT: usize = BASELINE_EVENT_COUNT + ECONOMY_EVENT_COUNT;

/// Which sovereign ref a class targets (the registry `target_ref` column).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TargetRef {
    /// `refs/turingos/tape_tip` — every PRESERVE class.
    TapeTip,
    /// `refs/turingos/authorization_head` — AUTHORIZATION.
    AuthorizationHead,
    /// `refs/turingos/accepted_head` — SOVEREIGN_ACCEPT.
    AcceptedHead,
}

impl TargetRef {
    fn from_str(s: &str) -> Option<Self> {
        Some(match s {
            "tape_tip" => TargetRef::TapeTip,
            "authorization_head" => TargetRef::AuthorizationHead,
            "accepted_head" => TargetRef::AcceptedHead,
            _ => return None,
        })
    }
}

/// A resolved, registry-derived row for one event type.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RegistryRow {
    /// The event's frozen class.
    pub class: EventClass,
    /// The registry-declared head effect (`ADVANCE` for SOVEREIGN_ACCEPT/AUTHORIZATION,
    /// `PRESERVE` for everything else). An admitting kernel rejects a carried
    /// `head_effect` that differs from this.
    pub head_effect: HeadEffect,
    /// The sovereign ref this class targets.
    pub target_ref: TargetRef,
    /// Whether the Candidate Predicate runs (`false` ⇒ `predicate_product = NOT_RUN`).
    pub predicate_required: bool,
    /// The payload schema id declared for this event (`event_schema_id`).
    pub payload_schema_id: &'static str,
}

// --- raw deserialization of the embedded JSON --------------------------------

#[derive(Deserialize)]
struct RawRegistry {
    events: Vec<RawEvent>,
}

#[derive(Deserialize)]
struct RawEvent {
    canonical_name: String,
    event_class: String,
    head_effect: String,
    target_ref: String,
    predicate_required: bool,
    payload_schema_id: String,
}

/// The ratified registry JSON, compiled in. The relative path is resolved at compile
/// time against this source file, so it is robust to the process CWD.
const REGISTRY_JSON: &str = include_str!("../../../pack/04_registries/event_registry_v5_3_1.json");

/// Parsed-once table: canonical event name → resolved row (with a leaked `&'static str`
/// for the payload schema id, so [`RegistryRow`] stays `Copy`).
fn table() -> &'static BTreeMap<String, RegistryRow> {
    static TABLE: OnceLock<BTreeMap<String, RegistryRow>> = OnceLock::new();
    TABLE.get_or_init(|| {
        let raw: RawRegistry = serde_json::from_str(REGISTRY_JSON)
            .expect("embedded event_registry_v5_3_1.json parses");
        let mut map = BTreeMap::new();
        for e in raw.events {
            let class = EventClass::from_str(&e.event_class)
                .unwrap_or_else(|| panic!("unknown event_class {:?}", e.event_class));
            let head_effect = match e.head_effect.as_str() {
                "ADVANCE" => HeadEffect::Advance,
                "PRESERVE" => HeadEffect::Preserve,
                other => panic!("unknown head_effect {other:?}"),
            };
            let target_ref = TargetRef::from_str(&e.target_ref)
                .unwrap_or_else(|| panic!("unknown target_ref {:?}", e.target_ref));
            // Leak the schema id once at first init so the row is `Copy`. The table is a
            // process-lifetime singleton, so this is a bounded, one-time allocation.
            let payload_schema_id: &'static str = Box::leak(e.payload_schema_id.into_boxed_str());
            map.insert(
                e.canonical_name,
                RegistryRow {
                    class,
                    head_effect,
                    target_ref,
                    predicate_required: e.predicate_required,
                    payload_schema_id,
                },
            );
        }
        map
    })
}

/// Look up the registry-derived row for `event_type`.
///
/// Returns `None` for any name outside the closed 46-event set (the `unknown_event_policy
/// = REJECT` discipline); callers turn that into an `UNKNOWN_EVENT_TYPE` admission
/// rejection rather than trusting the writer.
#[must_use]
pub fn registry(event_type: &str) -> Option<RegistryRow> {
    table().get(event_type).copied()
}

/// The total number of registered events.
#[must_use]
pub fn registered_event_count() -> usize {
    table().len()
}

/// Enumerate every canonical event name in the closed registry, in a stable bytewise order
/// (the table is a `BTreeMap` keyed by `canonical_name`).
///
/// This is the registry-derived enumeration consumers fold over when a law must hold for
/// all closed events (the head-effect ref laws SG-15/SG-16 and additive economy laws): it
/// yields exactly the names parsed from the registry JSON, so a sweep over it can never be
/// a hand-maintained subset that drifts from the pack. Pair each name with [`registry`] to
/// read its registry-derived row.
pub fn event_names() -> impl Iterator<Item = &'static str> {
    table().keys().map(String::as_str)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::envelope::HeadEffect;

    #[test]
    fn the_full_closed_event_set_is_loaded_from_the_pack() {
        // Proves the embedded `include_str!` of the ratified registry is fully parsed —
        // not a hand-maintained subset that mirrors a test's expectations.
        assert_eq!(
            registered_event_count(),
            TOTAL_EVENT_COUNT,
            "the closed registry has baseline plus additive economy events"
        );
    }

    #[test]
    fn classes_and_head_effects_are_registry_derived() {
        // ADVANCE is exclusive to SOVEREIGN_ACCEPT (accepted_head) and AUTHORIZATION
        // (authorization_head); every other class is PRESERVE (tape_tip).
        let accept = registry("SystemConstitutionAccepted").unwrap();
        assert_eq!(accept.class, EventClass::SovereignAccept);
        assert_eq!(accept.head_effect, HeadEffect::Advance);
        assert_eq!(accept.target_ref, TargetRef::AcceptedHead);
        assert!(accept.predicate_required);

        let auth = registry("AtomAuthorized").unwrap();
        assert_eq!(auth.class, EventClass::Authorization);
        assert_eq!(auth.head_effect, HeadEffect::Advance);
        assert_eq!(auth.target_ref, TargetRef::AuthorizationHead);

        let proposal = registry("GoalStateProposed").unwrap();
        assert_eq!(proposal.class, EventClass::Proposal);
        assert_eq!(proposal.head_effect, HeadEffect::Preserve);
        assert_eq!(proposal.target_ref, TargetRef::TapeTip);

        // The single predicate-free event records NOT_RUN downstream.
        let predicate_free = registry("PredicateEvaluated").unwrap();
        assert!(!predicate_free.predicate_required);
        assert_eq!(predicate_free.head_effect, HeadEffect::Preserve);
    }

    #[test]
    fn unknown_event_type_is_rejected_closed_world() {
        assert!(registry("NotARealEvent").is_none());
        assert!(registry("").is_none());
    }

    #[test]
    fn event_names_enumerates_exactly_the_registered_set() {
        // The registry-derived enumeration yields every registered name (count parity) and
        // each yielded name resolves back to a row — so a fold over `event_names()` cannot
        // miss an event or include a phantom one.
        let names: Vec<&str> = event_names().collect();
        assert_eq!(names.len(), registered_event_count());
        assert_eq!(names.len(), TOTAL_EVENT_COUNT);
        for n in &names {
            assert!(registry(n).is_some(), "enumerated name {n:?} must resolve");
        }
        // The 8 AUTHORIZATION events are present in the enumeration (sanity for SG-15).
        let auth = names
            .iter()
            .filter(|n| registry(n).unwrap().class == EventClass::Authorization)
            .count();
        assert_eq!(auth, 8);
        let economy = names
            .iter()
            .filter(|n| registry(n).unwrap().class == EventClass::Economy)
            .count();
        assert_eq!(economy, ECONOMY_EVENT_COUNT);
    }
}
