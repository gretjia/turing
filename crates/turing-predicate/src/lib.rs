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
    /// G-MKT-06: the market's frozen `predicate_set_hash` no longer matches the current
    /// predicate-check-id set -- the predicate set was weakened (or code drifted) between
    /// market creation and settlement.
    PredicateSetWeakened(String),
    /// G-MKT-06: the referenced `CandidateAccepted`'s `capsule_id` does not match the
    /// market's frozen `capsule_id` (or the market has no `capsule_id` bound at all).
    SettlementCapsuleMismatch(String),
    /// G-MKT-06: `settlement_event_id` is missing from the tape, or resolves to an event
    /// type other than the one required for this settlement `result` (`CandidateAccepted`
    /// for YES, `FailureNode` for NO).
    SettlementWrongReferenceType(String),
    /// G-MKT-06: the referenced settlement event is not strictly after the market's own
    /// `MarketCreated` in tape order.
    SettlementOrderingViolated(String),
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
            MarketPputPredicateError::PredicateSetWeakened(detail) => {
                write!(f, "G-MKT-06 predicate set weakened: {detail}")
            }
            MarketPputPredicateError::SettlementCapsuleMismatch(detail) => {
                write!(f, "G-MKT-06 capsule mismatch: {detail}")
            }
            MarketPputPredicateError::SettlementWrongReferenceType(detail) => {
                write!(f, "G-MKT-06 settlement reference invalid: {detail}")
            }
            MarketPputPredicateError::SettlementOrderingViolated(detail) => {
                write!(f, "G-MKT-06 ordering violated: {detail}")
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

// --- G-MKT-06 (D4): market_settlement_requires_predicate --------------------------------

/// The candidate predicate-check-id set as of this build, sorted for stable hashing --
/// mirrors the check_ids `derive_candidate_predicate_checks` in `turing-daemons` evaluates
/// for every `CandidateAccepted`/`FailureNode` decision. `MarketCreated.predicate_set_hash`
/// pins a hash of this list at market-creation time; G-MKT-06 recomputes it at settlement
/// time and refuses the settlement if the two disagree, i.e. if the predicate set changed
/// out from under a market that was already open (D4's "no post-hoc predicate weakening").
pub const CANDIDATE_PREDICATE_CHECK_IDS: &[&str] = &[
    "budget.within_limit",
    "capsule_contract",
    "macro_anchor",
    "official_evaluator_evidence",
    "provenance.checked",
    "replay.ready",
    "scope.allowed",
    "worker_receipt",
];

/// `sha256:` + hex over the current [`CANDIDATE_PREDICATE_CHECK_IDS`], JCS-canonicalized.
#[must_use]
pub fn candidate_predicate_set_hash() -> String {
    let value = serde_json::json!({
        "schema_id": "candidate_predicate_set.v1",
        "check_ids": CANDIDATE_PREDICATE_CHECK_IDS,
    });
    let bytes =
        jcs::canonicalize(&value).expect("candidate predicate set hash uses valid JCS values");
    format!("sha256:{}", jcs::sha256_hex(&bytes))
}

/// What `MarketSettled.settlement_event_id` resolved to on-tape, as gathered by the caller
/// (`turing-daemons`, which owns tape access) before calling [`market_settlement_gate_g_mkt_06`].
/// This crate stays tape-access-free by design (see the module doc), so all tape facts are
/// passed in as plain data.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SettlementReference<'a> {
    /// The referenced event is an on-tape `CandidateAccepted` carrying this `capsule_id`
    /// (`None` if the `CandidateAccepted` payload has no `capsule_id` field).
    CandidateAccepted { capsule_id: Option<&'a str> },
    /// The referenced event is an on-tape `FailureNode`. `FailureNodePayload` (per its closed
    /// schema) has no `capsule_id` field, so a direct capsule cross-check is not recoverable
    /// from the tape event alone -- a known, documented limitation of this gate's NO path
    /// (existence, type, and ordering are still enforced).
    FailureNode,
    /// `settlement_event_id` does not resolve to any event on the tape.
    Missing,
    /// `settlement_event_id` resolves to an on-tape event of a type other than
    /// `CandidateAccepted`/`FailureNode`.
    OtherType(&'a str),
}

/// All facts G-MKT-06 needs, gathered by the caller from the real tape.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MarketSettlementGateInput<'a> {
    pub result: &'a str,
    pub settlement_event_id: &'a str,
    pub market_capsule_id: &'a str,
    pub market_predicate_set_hash: &'a str,
    pub current_predicate_set_hash: &'a str,
    pub reference: SettlementReference<'a>,
    /// Tape position (lower = earlier) of this market's `MarketCreated` event.
    pub market_created_tape_index: Option<usize>,
    /// Tape position of the event `settlement_event_id` resolves to.
    pub settlement_tape_index: Option<usize>,
}

/// G-MKT-06 `market_settlement_requires_predicate` (D4): a `MarketSettled` is gate-valid only
/// if (1) `settlement_event_id` is a well-formed Micro event id, (2) it references an on-tape
/// `CandidateAccepted` (for `result == "YES"`) or `FailureNode` (for `result == "NO"`) --
/// wrong type or missing reference refuses the settlement, (3) for the `YES` path, that
/// `CandidateAccepted`'s `capsule_id` matches the market's frozen `capsule_id`, (4) the
/// market's frozen `predicate_set_hash` still matches the current predicate-check-id set (no
/// post-hoc weakening), and (5) the referenced event's tape position is strictly after the
/// market's own `MarketCreated` (deadline/causal ordering: a market cannot be settled by an
/// event that predates its own creation).
pub fn market_settlement_gate_g_mkt_06(
    input: &MarketSettlementGateInput,
) -> Result<(), MarketPputPredicateError> {
    market_settlement_event_is_micro(input.settlement_event_id)?;

    if input.market_predicate_set_hash != input.current_predicate_set_hash {
        return Err(MarketPputPredicateError::PredicateSetWeakened(format!(
            "market predicate_set_hash {:?} != current {:?}",
            input.market_predicate_set_hash, input.current_predicate_set_hash
        )));
    }

    match (input.result, input.reference) {
        ("YES", SettlementReference::CandidateAccepted { capsule_id }) => {
            if capsule_id != Some(input.market_capsule_id) || input.market_capsule_id.is_empty() {
                return Err(MarketPputPredicateError::SettlementCapsuleMismatch(
                    format!(
                        "CandidateAccepted capsule_id {capsule_id:?} != market capsule_id {:?}",
                        input.market_capsule_id
                    ),
                ));
            }
        }
        ("NO", SettlementReference::FailureNode) => {
            // Capsule cross-check is not recoverable here -- see SettlementReference::FailureNode.
        }
        ("YES" | "NO", other) => {
            return Err(MarketPputPredicateError::SettlementWrongReferenceType(
                format!("result {:?} referenced {other:?}", input.result),
            ));
        }
        (other, _) => {
            return Err(MarketPputPredicateError::SettlementWrongReferenceType(
                format!("unsupported settlement result {other:?} for G-MKT-06"),
            ));
        }
    }

    match (input.market_created_tape_index, input.settlement_tape_index) {
        (Some(created), Some(settled)) if settled > created => Ok(()),
        _ => Err(MarketPputPredicateError::SettlementOrderingViolated(
            format!(
                "settlement reference tape_index {:?} is not strictly after MarketCreated tape_index {:?}",
                input.settlement_tape_index, input.market_created_tape_index
            ),
        )),
    }
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
