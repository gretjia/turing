//! `MicroEventEnvelope.v1` — the committed Git body — and `HeadSet.v1`.
//!
//! These are the closed Rust types for `pack/05_schemas/micro_event_envelope.v1.schema.json`
//! and `pack/05_schemas/head_set.v1.schema.json`. They serialize to the **exact**
//! committed body via the `turingos.jcs.v1` codec: the canonical bytes of an
//! [`MicroEventEnvelope`] are what a Git commit stores, and `content_digest ==
//! payload_hash == sha256:` + `sha256(JCS(payload))`.
//!
//! Two frozen invariants are encoded in the type itself:
//! - **`event_id` is forbidden in the committed body** — a Git commit cannot embed its
//!   own OID; the external read identity is paired with the body through
//!   `micro_event_record.v1` and the append receipt. There is therefore no `event_id`
//!   field anywhere on [`MicroEventEnvelope`].
//! - **`head_set_after` is forbidden** — the post-state is self-reference-free and is
//!   *derived* (see [`crate::registry`] + the kernel reducer), never carried.
//!
//! `head_effect` is carried for audit only; an admitting kernel accepts it solely when
//! it equals the registry row (`pack/04_registries/event_registry_v5_3_1.json`). This
//! module does not trust it.

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::jcs::{self, JcsError};

/// The frozen `head_effect` discriminator: whether an event *may* advance its registry
/// head. The actual movement also requires `predicate_product == PASS` and is decided
/// by the kernel reducer; this is the registry-declared intent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HeadEffect {
    /// The event's registry head advances iff `predicate_product == PASS`.
    #[serde(rename = "ADVANCE")]
    Advance,
    /// The event never advances any sovereign head; only `tape_tip` moves.
    #[serde(rename = "PRESERVE")]
    Preserve,
}

/// The frozen predicate product: the deterministic boolean (or "not applicable") result
/// of the Candidate Predicate over frozen Tape bytes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PredicateProduct {
    /// The transition is verified; a registry head may advance.
    #[serde(rename = "PASS")]
    Pass,
    /// The transition failed; only a failure node lands on `tape_tip`.
    #[serde(rename = "FAIL")]
    Fail,
    /// The event is predicate-free (`predicate_required == false`); no head advances.
    #[serde(rename = "NOT_RUN")]
    NotRun,
}

/// `MicroEventEnvelope.v1` — the 16-field committed Git body.
///
/// Field order in this struct mirrors the schema's `required` array for readability; the
/// committed bytes are produced by the `turingos.jcs.v1` codec which sorts keys bytewise,
/// so the struct field order is not load-bearing. `serde` field names are the exact
/// schema keys and there is **no** `event_id` / `head_set_after` field
/// (`additionalProperties:false` parity is enforced at parse by [`Self::from_jcs_value`]).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MicroEventEnvelope {
    /// Always the const `"micro_event_envelope.v1"`.
    pub schema_id: String,
    /// The canonical registry event name (e.g. `"SystemConstitutionAccepted"`).
    pub event_type: String,
    /// The opaque writer identity that minted this candidate.
    pub writer_id: String,
    /// The pre-state fencing epoch (`>= 0`).
    pub authority_epoch: u64,
    /// The monotone per-Tape sequence number (`>= 0`).
    pub sequence: u64,
    /// The observed `tape_tip` this event is a child of (`mu:`…), or `null` at genesis.
    pub prev_tape_tip: Option<String>,
    /// The `authorization_head` observed pre-append (`mu:`…), or `null`.
    pub authorization_head_before: Option<String>,
    /// The `accepted_head` observed pre-append (`mu:`…), or `null` at genesis.
    pub accepted_head_before: Option<String>,
    /// Carried-for-audit head effect; accepted only if equal to the registry row.
    pub head_effect: HeadEffect,
    /// The payload's schema id (e.g. `"system_constitution_accepted.v1"`).
    pub event_schema_id: String,
    /// The predicate product for this final event.
    pub predicate_product: PredicateProduct,
    /// `sha256:` + 64hex over the sorted predicate reasons (`sha256(JCS([]))` when none).
    pub reason_digest: String,
    /// Whether this event is a verified transition (`true` only on PASS finalization).
    pub verified: bool,
    /// `sha256:` + `sha256(JCS(payload))`; must equal `payload_hash`.
    pub content_digest: String,
    /// Append-API name for `content_digest`; byte-equal to it.
    pub payload_hash: String,
    /// The event payload object (schema is `event_schema_id`).
    pub payload: Value,
}

/// The const `schema_id` for the committed envelope body.
pub const ENVELOPE_SCHEMA_ID: &str = "micro_event_envelope.v1";

const ENVELOPE_REQUIRED_FIELDS: &[&str] = &[
    "schema_id",
    "event_type",
    "writer_id",
    "authority_epoch",
    "sequence",
    "prev_tape_tip",
    "authorization_head_before",
    "accepted_head_before",
    "head_effect",
    "event_schema_id",
    "predicate_product",
    "reason_digest",
    "verified",
    "content_digest",
    "payload_hash",
    "payload",
];

impl MicroEventEnvelope {
    /// The canonical `turingos.jcs.v1` bytes of this envelope — exactly what a Git
    /// commit stores as the event body. Sorted keys, no whitespace, integers only.
    pub fn to_jcs_bytes(&self) -> Result<Vec<u8>, JcsError> {
        let value = serde_json::to_value(self)
            .expect("MicroEventEnvelope serializes to a JSON object infallibly");
        jcs::canonicalize(&value)
    }

    /// Parse a committed body from already-loaded JSON, enforcing the schema's closed
    /// shape: the const `schema_id`, exactly the 16 fields, and the absence of
    /// `event_id` / `head_set_after`. `serde(deny_unknown_fields)` rejects any extra key
    /// (including those two), so a torn or tampered body fails here rather than silently
    /// round-tripping.
    pub fn from_jcs_value(value: &Value) -> Result<Self, JcsError> {
        let obj = value
            .as_object()
            .ok_or_else(|| JcsError::Malformed("envelope body is not a JSON object".into()))?;
        if obj.contains_key("event_id") {
            return Err(JcsError::ForbiddenPayloadField("event_id".into()));
        }
        if obj.contains_key("head_set_after") {
            return Err(JcsError::ForbiddenPayloadField("head_set_after".into()));
        }
        for field in ENVELOPE_REQUIRED_FIELDS {
            if !obj.contains_key(*field) {
                return Err(JcsError::Malformed(format!(
                    "envelope shape: missing required field {field:?}"
                )));
            }
        }
        if obj.len() != ENVELOPE_REQUIRED_FIELDS.len() {
            return Err(JcsError::Malformed(format!(
                "envelope shape: expected exactly {} fields, got {}",
                ENVELOPE_REQUIRED_FIELDS.len(),
                obj.len()
            )));
        }
        let env: MicroEventEnvelope = serde_json::from_value(value.clone())
            .map_err(|e| JcsError::Malformed(format!("envelope shape: {e}")))?;
        if env.schema_id != ENVELOPE_SCHEMA_ID {
            return Err(JcsError::Malformed(format!(
                "schema_id must be {ENVELOPE_SCHEMA_ID:?}, got {:?}",
                env.schema_id
            )));
        }
        Ok(env)
    }
}

/// `HeadSet.v1` — the coherent three-ref sovereign state.
///
/// `tape_tip` and `accepted_head` are always non-null once genesis exists;
/// `authorization_head` is nullable (no AUTHORIZATION event has been accepted yet). This
/// type carries **no** epoch/sequence field — those are reconciled from the envelope
/// pre-state (schema parity: `additionalProperties:false`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HeadSet {
    /// The tip of the Tape (`mu:`…); advances on every valid append.
    pub tape_tip: String,
    /// The latest accepted AUTHORIZATION event (`mu:`…), or `null`.
    pub authorization_head: Option<String>,
    /// The latest accepted SOVEREIGN_ACCEPT event (`mu:`…); non-null post-genesis.
    pub accepted_head: String,
}

/// The const `schema_id` value for `head_set.v1` consumers (the schema itself has no
/// `schema_id` field; this is the registry identifier used in prose/receipts).
pub const HEAD_SET_SCHEMA_ID: &str = "head_set.v1";
