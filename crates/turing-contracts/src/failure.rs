//! Failure taxonomy — the closed 17-value [`FailureClass`], the 5-value [`Disposition`],
//! the embedded `17 → 5` disposition map (parsed once), and the `failure_node_payload.v1`
//! closed type [`FailureNodePayload`].
//!
//! These are **ratified-source** closed values, exactly like the event registry in
//! [`crate::registry`]: the names/ordinals come from
//! `pack/04_registries/failure_class_registry_v5_3_1.json` (append-only, 17 values) and
//! the recovery policy from `pack/04_registries/failure_disposition_map_v5_3_1.json`
//! (`17 → 5`). The disposition map JSON is compiled in with [`include_str!`] and parsed a
//! single time, so [`dispose`] is registry-derived and can never silently diverge from the
//! frozen pack file.
//!
//! `FailureClass` is the predicate / observer FAIL taxonomy (the 17-set). The *structural*
//! admission `reject_class` ("parse failure" = `MALFORMED_BYTES`, …) is a **distinct**
//! taxonomy modelled in `turing-kernel` (`turing_kernel::failure::RejectClass`) and is NOT
//! one of these 17.

use std::collections::BTreeMap;
use std::sync::OnceLock;

use serde::{Deserialize, Serialize};

/// The frozen 17-value FailureClass (`failure_class_registry_v5_3_1.json`, append-only).
///
/// `serde` names are the exact registry / `failure_node_payload.v1` enum strings, so this
/// type round-trips through the canonical codec byte-identically with the schema.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum FailureClass {
    /// Ordinal 1 — human authorization is required before proceeding.
    #[serde(rename = "AUTH_REQUIRED")]
    AuthRequired,
    /// Ordinal 2 — a soft (recoverable) timeout elapsed.
    #[serde(rename = "TIMEOUT_SOFT")]
    TimeoutSoft,
    /// Ordinal 3 — a hard (terminal) timeout elapsed.
    #[serde(rename = "TIMEOUT_HARD")]
    TimeoutHard,
    /// Ordinal 4 — a timeout that is retryable as a transient network condition.
    #[serde(rename = "TIMEOUT_OR_NETWORK_RETRY")]
    TimeoutOrNetworkRetry,
    /// Ordinal 5 — the output violated its declared schema shape.
    #[serde(rename = "OUTPUT_SCHEMA_VIOLATION")]
    OutputSchemaViolation,
    /// Ordinal 6 — the candidate produced no diff where one was required.
    #[serde(rename = "NO_DIFF")]
    NoDiff,
    /// Ordinal 7 — the candidate produced the wrong diff.
    #[serde(rename = "WRONG_DIFF")]
    WrongDiff,
    /// Ordinal 8 — the worktree was dirty when a clean one was required.
    #[serde(rename = "DIRTY_WORKTREE")]
    DirtyWorktree,
    /// Ordinal 9 — an ambiguous mutation was observed (safety-class).
    #[serde(rename = "AMBIGUOUS_MUTATION")]
    AmbiguousMutation,
    /// Ordinal 10 — a resume point was unavailable.
    #[serde(rename = "RESUME_UNAVAILABLE")]
    ResumeUnavailable,
    /// Ordinal 11 — a human steer was rejected.
    #[serde(rename = "STEER_REJECTED")]
    SteerRejected,
    /// Ordinal 12 — an unknown non-zero exit (fail-closed).
    #[serde(rename = "UNKNOWN_NONZERO")]
    UnknownNonzero,
    /// Ordinal 13 — the candidate predicate failed on logic / semantics.
    #[serde(rename = "SEMANTIC_FAILURE")]
    SemanticFailure,
    /// Ordinal 14 — the effect exceeded the authorized scope (safety-class).
    #[serde(rename = "OVER_SCOPE")]
    OverScope,
    /// Ordinal 15 — a credential boundary was violated (safety-class).
    #[serde(rename = "CREDENTIAL_VIOLATION")]
    CredentialViolation,
    /// Ordinal 16 — a sandbox boundary was violated (safety-class).
    #[serde(rename = "SANDBOX_VIOLATION")]
    SandboxViolation,
    /// Ordinal 17 — the observer disagreed with the claimed transition (safety-class).
    #[serde(rename = "OBSERVER_MISMATCH")]
    ObserverMismatch,
}

impl FailureClass {
    /// All 17 FailureClass values in registry ordinal order (1..=17).
    pub const ALL: [FailureClass; 17] = [
        FailureClass::AuthRequired,
        FailureClass::TimeoutSoft,
        FailureClass::TimeoutHard,
        FailureClass::TimeoutOrNetworkRetry,
        FailureClass::OutputSchemaViolation,
        FailureClass::NoDiff,
        FailureClass::WrongDiff,
        FailureClass::DirtyWorktree,
        FailureClass::AmbiguousMutation,
        FailureClass::ResumeUnavailable,
        FailureClass::SteerRejected,
        FailureClass::UnknownNonzero,
        FailureClass::SemanticFailure,
        FailureClass::OverScope,
        FailureClass::CredentialViolation,
        FailureClass::SandboxViolation,
        FailureClass::ObserverMismatch,
    ];

    /// The exact registry / schema enum string for this class (e.g. `"OBSERVER_MISMATCH"`).
    #[must_use]
    pub fn as_registry_str(self) -> &'static str {
        match self {
            FailureClass::AuthRequired => "AUTH_REQUIRED",
            FailureClass::TimeoutSoft => "TIMEOUT_SOFT",
            FailureClass::TimeoutHard => "TIMEOUT_HARD",
            FailureClass::TimeoutOrNetworkRetry => "TIMEOUT_OR_NETWORK_RETRY",
            FailureClass::OutputSchemaViolation => "OUTPUT_SCHEMA_VIOLATION",
            FailureClass::NoDiff => "NO_DIFF",
            FailureClass::WrongDiff => "WRONG_DIFF",
            FailureClass::DirtyWorktree => "DIRTY_WORKTREE",
            FailureClass::AmbiguousMutation => "AMBIGUOUS_MUTATION",
            FailureClass::ResumeUnavailable => "RESUME_UNAVAILABLE",
            FailureClass::SteerRejected => "STEER_REJECTED",
            FailureClass::UnknownNonzero => "UNKNOWN_NONZERO",
            FailureClass::SemanticFailure => "SEMANTIC_FAILURE",
            FailureClass::OverScope => "OVER_SCOPE",
            FailureClass::CredentialViolation => "CREDENTIAL_VIOLATION",
            FailureClass::SandboxViolation => "SANDBOX_VIOLATION",
            FailureClass::ObserverMismatch => "OBSERVER_MISMATCH",
        }
    }
}

/// The frozen 5-value recovery disposition (`failure_disposition_map_v5_3_1.json`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Disposition {
    /// Same frozen capsule may be re-dispatched after a fresh RetryAuthorized + grant.
    #[serde(rename = "RETRY")]
    Retry,
    /// A new WorkCapsule must be built; the failed capsule is never re-dispatched.
    #[serde(rename = "REPLAN")]
    Replan,
    /// The operation waits for a human; Worker/tool/token budgets do not burn.
    #[serde(rename = "WAIT_FOR_HUMAN")]
    WaitForHuman,
    /// A terminal safety failure is appended and the affected sovereign loop stops.
    #[serde(rename = "SAFETY_HALT")]
    SafetyHalt,
    /// The operation ends as an ordinary terminal failure (no system-wide safety breach).
    #[serde(rename = "TERMINATE")]
    Terminate,
}

// --- embedded disposition map (parsed once) ----------------------------------

/// The ratified disposition-map JSON, compiled in. The relative path is resolved at
/// compile time against this source file, so it is robust to the process CWD.
const DISPOSITION_MAP_JSON: &str =
    include_str!("../../../pack/04_registries/failure_disposition_map_v5_3_1.json");

#[derive(Deserialize)]
struct RawDispositionMap {
    mapping: Vec<RawDispositionEntry>,
}

#[derive(Deserialize)]
struct RawDispositionEntry {
    failure_class: FailureClass,
    disposition: Disposition,
}

/// Parsed-once `FailureClass → Disposition` table from the frozen pack registry.
fn disposition_table() -> &'static BTreeMap<FailureClass, Disposition> {
    static TABLE: OnceLock<BTreeMap<FailureClass, Disposition>> = OnceLock::new();
    TABLE.get_or_init(|| {
        let raw: RawDispositionMap = serde_json::from_str(DISPOSITION_MAP_JSON)
            .expect("embedded failure_disposition_map_v5_3_1.json parses");
        let mut map = BTreeMap::new();
        for e in raw.mapping {
            if map.insert(e.failure_class, e.disposition).is_some() {
                panic!(
                    "duplicate FailureClass in disposition map: {e:?}",
                    e = e.failure_class
                );
            }
        }
        assert_eq!(
            map.len(),
            FailureClass::ALL.len(),
            "the frozen disposition map must cover all 17 FailureClass values"
        );
        map
    })
}

/// The frozen recovery disposition for a [`FailureClass`], registry-derived from
/// `failure_disposition_map_v5_3_1.json` (the `17 → 5` map). Total over all 17 values.
#[must_use]
pub fn dispose(class: FailureClass) -> Disposition {
    *disposition_table()
        .get(&class)
        .expect("the frozen disposition map is total over the 17 FailureClass values")
}

// --- failure_node_payload.v1 -------------------------------------------------

/// `failure_node_payload.v1` — the predicate-FAIL FailureNode payload.
///
/// Closed type for `pack/05_schemas/failure_node_payload.v1.schema.json`:
/// `verified` is the const `false`, `failure_class` is one of the 17, `candidate_digest`
/// and `observation_digest` are `sha256:` + 64hex, and `detail` is optional. It serializes
/// to the exact schema body via the `turingos.jcs.v1` codec.
///
/// `verified` is kept as a real field (not elided) so the committed payload bytes carry the
/// const `false` exactly as the schema requires; [`Self::new`] is the only constructor and
/// always sets it to `false`, and [`Self::from_jcs_value`] rejects any other value.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FailureNodePayload {
    /// Always the const `false` — a failure node is never a verified transition.
    pub verified: bool,
    /// One of the 17 frozen FailureClass values.
    pub failure_class: FailureClass,
    /// `sha256:` + 64hex over the candidate that failed.
    pub candidate_digest: String,
    /// `sha256:` + 64hex over the observation that produced the FAIL.
    pub observation_digest: String,
    /// Optional free-text detail (non-load-bearing; excluded from semantic digests).
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub detail: Option<String>,
}

/// The const `schema_id` for `failure_node_payload.v1` consumers (the schema body itself
/// has no `schema_id` field; this is the registry identifier used in the envelope's
/// `event_schema_id` and in receipts).
pub const FAILURE_NODE_PAYLOAD_SCHEMA_ID: &str = "failure_node_payload.v1";

impl FailureNodePayload {
    /// Build a `failure_node_payload.v1` with `verified == false` (the only legal value).
    #[must_use]
    pub fn new(
        failure_class: FailureClass,
        candidate_digest: impl Into<String>,
        observation_digest: impl Into<String>,
        detail: Option<String>,
    ) -> Self {
        FailureNodePayload {
            verified: false,
            failure_class,
            candidate_digest: candidate_digest.into(),
            observation_digest: observation_digest.into(),
            detail,
        }
    }

    /// The canonical `turingos.jcs.v1` bytes of this payload — the committed payload body
    /// whose `sha256` is the envelope's `content_digest == payload_hash`.
    pub fn to_jcs_bytes(&self) -> Result<Vec<u8>, crate::jcs::JcsError> {
        let value = serde_json::to_value(self)
            .expect("FailureNodePayload serializes to a JSON object infallibly");
        crate::jcs::canonicalize(&value)
    }

    /// Parse a `failure_node_payload.v1` body from already-loaded JSON, enforcing the
    /// schema's closed shape: the const `verified == false`, exactly the known fields, and
    /// `additionalProperties: false` (any extra key fails here rather than round-tripping).
    pub fn from_jcs_value(value: &serde_json::Value) -> Result<Self, crate::jcs::JcsError> {
        use crate::jcs::JcsError;
        let payload: FailureNodePayload = serde_json::from_value(value.clone())
            .map_err(|e| JcsError::Malformed(format!("failure_node_payload shape: {e}")))?;
        if payload.verified {
            return Err(JcsError::Malformed(
                "failure_node_payload.v1 requires verified == false".into(),
            ));
        }
        Ok(payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_17_failure_classes_map_to_a_disposition() {
        // Anti-Goodhart: the map is loaded from the embedded pack registry (include_str!),
        // not a hand-maintained mirror — every one of the 17 must resolve.
        for fc in FailureClass::ALL {
            let _ = dispose(fc); // total; panics if any class is unmapped.
        }
        assert_eq!(
            disposition_table().len(),
            17,
            "the frozen map covers all 17 classes"
        );
    }

    #[test]
    fn disposition_tally_matches_the_frozen_2_6_3_5_1_split() {
        // RETRY×2, REPLAN×6, WAIT_FOR_HUMAN×3, SAFETY_HALT×5, TERMINATE×1 = 17
        // (failure_disposition_map_v5_3_1.json — SAFETY_HALT covers AMBIGUOUS_MUTATION,
        // OVER_SCOPE, CREDENTIAL_VIOLATION, SANDBOX_VIOLATION, OBSERVER_MISMATCH).
        let mut retry = 0;
        let mut replan = 0;
        let mut wait = 0;
        let mut halt = 0;
        let mut terminate = 0;
        for fc in FailureClass::ALL {
            match dispose(fc) {
                Disposition::Retry => retry += 1,
                Disposition::Replan => replan += 1,
                Disposition::WaitForHuman => wait += 1,
                Disposition::SafetyHalt => halt += 1,
                Disposition::Terminate => terminate += 1,
            }
        }
        assert_eq!((retry, replan, wait, halt, terminate), (2, 6, 3, 5, 1));
    }

    #[test]
    fn specific_contract_dispositions() {
        assert_eq!(dispose(FailureClass::SemanticFailure), Disposition::Replan);
        assert_eq!(
            dispose(FailureClass::OutputSchemaViolation),
            Disposition::Replan
        );
        assert_eq!(dispose(FailureClass::TimeoutSoft), Disposition::Retry);
        assert_eq!(
            dispose(FailureClass::TimeoutOrNetworkRetry),
            Disposition::Retry
        );
        assert_eq!(dispose(FailureClass::TimeoutHard), Disposition::Terminate);
        assert_eq!(
            dispose(FailureClass::ObserverMismatch),
            Disposition::SafetyHalt
        );
        assert_eq!(
            dispose(FailureClass::AuthRequired),
            Disposition::WaitForHuman
        );
    }

    #[test]
    fn failure_node_payload_roundtrips_with_const_false_verified() {
        let p = FailureNodePayload::new(
            FailureClass::ObserverMismatch,
            "sha256:".to_string() + &"00".repeat(32),
            "sha256:".to_string() + &"11".repeat(32),
            Some("detail".to_string()),
        );
        assert!(!p.verified);
        let bytes = p.to_jcs_bytes().expect("canonical bytes");
        let value: serde_json::Value = serde_json::from_slice(&bytes).expect("parse back");
        let parsed = FailureNodePayload::from_jcs_value(&value).expect("closed-shape parse");
        assert_eq!(parsed, p);
    }

    #[test]
    fn failure_node_payload_rejects_verified_true_and_unknown_fields() {
        // verified must be the const false.
        let bad_verified = serde_json::json!({
            "verified": true,
            "failure_class": "SEMANTIC_FAILURE",
            "candidate_digest": "sha256:".to_string() + &"00".repeat(32),
            "observation_digest": "sha256:".to_string() + &"11".repeat(32),
        });
        assert!(FailureNodePayload::from_jcs_value(&bad_verified).is_err());

        // additionalProperties: false.
        let extra_key = serde_json::json!({
            "verified": false,
            "failure_class": "SEMANTIC_FAILURE",
            "candidate_digest": "sha256:".to_string() + &"00".repeat(32),
            "observation_digest": "sha256:".to_string() + &"11".repeat(32),
            "head_set_after": "mu:".to_string() + &"22".repeat(32),
        });
        assert!(FailureNodePayload::from_jcs_value(&extra_key).is_err());
    }
}
