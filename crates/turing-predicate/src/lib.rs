//! turing-predicate — deterministic predicate-facing registry admission.
//!
//! This crate intentionally does not own a second event registry. It exposes a
//! predicate-side closed-world API over the single embedded registry owned by
//! `turing-contracts`.

use turing_contracts::registry::{self, RegistryRow};

/// Predicate admission errors.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PredicateError {
    /// The event type is not in the closed event registry.
    UnknownEventType(String),
}

impl std::fmt::Display for PredicateError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PredicateError::UnknownEventType(event_type) => {
                write!(f, "unknown event_type {event_type:?}")
            }
        }
    }
}

impl std::error::Error for PredicateError {}

/// Resolve an event type through the single closed registry.
pub fn event_registry_closed_world(event_type: &str) -> Result<RegistryRow, PredicateError> {
    registry::registry(event_type)
        .ok_or_else(|| PredicateError::UnknownEventType(event_type.to_string()))
}

/// Stable iterator over every closed registry event name.
pub fn registered_event_names() -> impl Iterator<Item = &'static str> {
    registry::event_names()
}

/// Closed registry cardinality.
#[must_use]
pub fn registered_event_count() -> usize {
    registry::registered_event_count()
}
