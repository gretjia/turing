//! turing-predicate — deterministic predicate-facing registry admission.
//!
//! This crate intentionally does not own a second event registry. It exposes a
//! predicate-side closed-world API over the single embedded registry owned by
//! `turing-contracts`.

use turing_contracts::identity::MicroOid;
use turing_contracts::registry::{self, EventClass, RegistryRow, TargetRef};
use turing_contracts::{envelope::PredicateProduct, jcs};

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

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct PredicateKernel;

impl PredicateKernel {
    pub fn run(
        &self,
        event_type: &str,
        checks: Vec<PredicateCheck>,
    ) -> Result<PredicateReport, PredicateError> {
        event_registry_closed_world(event_type)?;

        let mut checks = checks;
        checks.sort_by(|a, b| a.check_id.cmp(&b.check_id));

        let mut passed_predicates = Vec::new();
        let mut failed_predicates = Vec::new();
        let mut reject_class = None;

        for check in checks {
            if check.passed {
                passed_predicates.push(check.check_id);
            } else {
                if reject_class.is_none() {
                    reject_class = check.reject_class.clone();
                }
                failed_predicates.push(check.check_id);
            }
        }

        let product = if failed_predicates.is_empty() {
            PredicateProduct::Pass
        } else {
            PredicateProduct::Fail
        };
        let report_hash = report_hash(
            event_type,
            product,
            &passed_predicates,
            &failed_predicates,
            reject_class.as_deref(),
        );

        Ok(PredicateReport {
            event_type: event_type.to_string(),
            product,
            passed_predicates,
            failed_predicates,
            reject_class,
            report_hash,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PredicateCheck {
    pub check_id: String,
    pub passed: bool,
    pub reject_class: Option<String>,
}

impl PredicateCheck {
    #[must_use]
    pub fn pass(check_id: impl Into<String>) -> Self {
        PredicateCheck {
            check_id: check_id.into(),
            passed: true,
            reject_class: None,
        }
    }

    #[must_use]
    pub fn fail(check_id: impl Into<String>, reject_class: impl Into<String>) -> Self {
        PredicateCheck {
            check_id: check_id.into(),
            passed: false,
            reject_class: Some(reject_class.into()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PredicateReport {
    pub event_type: String,
    pub product: PredicateProduct,
    pub passed_predicates: Vec<String>,
    pub failed_predicates: Vec<String>,
    pub reject_class: Option<String>,
    pub report_hash: String,
}

fn report_hash(
    event_type: &str,
    product: PredicateProduct,
    passed_predicates: &[String],
    failed_predicates: &[String],
    reject_class: Option<&str>,
) -> String {
    let product = match product {
        PredicateProduct::Pass => "PASS",
        PredicateProduct::Fail => "FAIL",
        PredicateProduct::NotRun => "NOT_RUN",
    };
    let value = serde_json::json!({
        "schema_id": "predicate_report.v1",
        "event_type": event_type,
        "product": product,
        "passed_predicates": passed_predicates,
        "failed_predicates": failed_predicates,
        "reject_class": reject_class,
    });
    let bytes = jcs::canonicalize(&value).expect("predicate report hash uses valid JCS values");
    format!("sha256:{}", jcs::sha256_hex(&bytes))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MarketPputPredicateError {
    UnknownEventType(String),
    NotEconomyEvent(String),
    EconomyEventCanMoveTruth(String),
    InvalidSettlementEventId(String),
    PputLeakage(String),
}

impl std::fmt::Display for MarketPputPredicateError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MarketPputPredicateError::UnknownEventType(event_type) => {
                write!(f, "unknown event_type {event_type:?}")
            }
            MarketPputPredicateError::NotEconomyEvent(event_type) => {
                write!(f, "event {event_type:?} is not an economy event")
            }
            MarketPputPredicateError::EconomyEventCanMoveTruth(event_type) => {
                write!(f, "economy event {event_type:?} can move truth")
            }
            MarketPputPredicateError::InvalidSettlementEventId(id) => {
                write!(f, "market settlement id {id:?} is not a Micro mu: id")
            }
            MarketPputPredicateError::PputLeakage(marker) => {
                write!(f, "worker prompt leaks hidden PPUT marker {marker:?}")
            }
        }
    }
}

impl std::error::Error for MarketPputPredicateError {}

pub fn market_event_preserves_truth(event_type: &str) -> Result<(), MarketPputPredicateError> {
    let row = registry::registry(event_type)
        .ok_or_else(|| MarketPputPredicateError::UnknownEventType(event_type.to_string()))?;
    if row.class != EventClass::Economy {
        return Err(MarketPputPredicateError::NotEconomyEvent(
            event_type.to_string(),
        ));
    }
    if row.target_ref != TargetRef::TapeTip
        || row.head_effect != turing_contracts::envelope::HeadEffect::Preserve
    {
        return Err(MarketPputPredicateError::EconomyEventCanMoveTruth(
            event_type.to_string(),
        ));
    }
    Ok(())
}

pub fn market_settlement_event_is_micro(
    settlement_event_id: &str,
) -> Result<(), MarketPputPredicateError> {
    MicroOid::parse(settlement_event_id)
        .map(|_| ())
        .map_err(|_| {
            MarketPputPredicateError::InvalidSettlementEventId(settlement_event_id.to_string())
        })
}

pub fn no_pput_in_worker_prompt(prompt: &str) -> Result<(), MarketPputPredicateError> {
    let lower = prompt.to_ascii_lowercase();
    for (canonical, needle) in [
        ("VPPUT", "vpput"),
        ("PPUT", "pput"),
        ("heldout", "heldout"),
        ("hidden evaluator", "hidden evaluator"),
        ("progress / (tokens", "progress / (tokens"),
    ] {
        if lower.contains(needle) {
            return Err(MarketPputPredicateError::PputLeakage(canonical.to_string()));
        }
    }
    Ok(())
}
