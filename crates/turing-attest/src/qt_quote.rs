//! `q_t_quote.v1` — HW-SW-009 / HW-SW-032. Schema layer only: serde struct +
//! validation + the JCS qualifying-digest binding rule
//! (`docs/roadmap/secure_os_18_month/06_boot_gate.md` §5.e). The real
//! TPM/TEE wiring that PRODUCES a live quote lands in Phase 11; this module
//! only defines the shape and lets any verifier recompute the digest.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use turing_contracts::jcs::{self, JcsError};

pub const QT_QUOTE_SCHEMA_ID: &str = "q_t_quote.v1";

/// Errors raised by [`QtQuote::parse`] / [`QtQuote::validate`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum QtQuoteError {
    /// `schema_id` did not match [`QT_QUOTE_SCHEMA_ID`].
    BadSchemaId { found: String },
    /// `quote.pcr_digest` did not equal the recomputed qualifying digest of
    /// `quoted` (the binding rule from 06_boot_gate.md §5.e).
    DigestMismatch { expected: String, found: String },
    /// A non-ASCII object key was found anywhere in the document.
    NonAsciiKey(String),
    /// The document was not valid JSON, or `quoted` could not canonicalize.
    Parse(String),
}

impl std::fmt::Display for QtQuoteError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            QtQuoteError::BadSchemaId { found } => write!(
                f,
                "unknown schema_id {found:?}, expected {QT_QUOTE_SCHEMA_ID:?}"
            ),
            QtQuoteError::DigestMismatch { expected, found } => write!(
                f,
                "quote.pcr_digest {found:?} does not equal recomputed qualifying digest {expected:?}"
            ),
            QtQuoteError::NonAsciiKey(k) => write!(f, "non-ASCII load-bearing key: {k}"),
            QtQuoteError::Parse(m) => write!(f, "q_t_quote parse: {m}"),
        }
    }
}

impl std::error::Error for QtQuoteError {}

/// The complete root-state binding: substrate + all three heads + policy
/// context. `SHA-256(JCS(quoted))` is the qualifying digest presented to the
/// TPM/TEE (and recomputed here by any verifier).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Quoted {
    pub constitution_hash: String,
    pub schema_pack_hash: String,
    pub predicate_pack_hash: String,
    pub runtime_binary_hash: String,
    pub tape_tip: String,
    pub authorization_head: String,
    pub accepted_head: String,
    pub signer_route: String,
    pub policy_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Quote {
    /// `tpm2_quote` | `tee_report` | `simulated`.
    pub kind: String,
    pub pcr_digest: String,
    pub signature: String,
    pub ak_pub_ref: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct QtQuote {
    pub schema_id: String,
    pub quoted: Quoted,
    pub nonce: String,
    pub quote: Quote,
    pub produced_at: String,
    pub verifier_hint: String,
}

impl QtQuote {
    /// Parse raw JSON, rejecting non-ASCII / duplicate object keys anywhere
    /// via the workspace's `turingos.jcs.v1` strict grammar before the typed
    /// decode.
    pub fn parse(text: &str) -> Result<Self, QtQuoteError> {
        jcs::parse_strict(text).map_err(|e| match e {
            JcsError::NonAsciiKey(k) => QtQuoteError::NonAsciiKey(k),
            other => QtQuoteError::Parse(other.to_string()),
        })?;
        serde_json::from_str(text).map_err(|e| QtQuoteError::Parse(e.to_string()))
    }

    /// `SHA-256(JCS(quoted))` — reuses `turing_contracts::jcs` (canonical
    /// bytes) and its `sha256_hex` helper, the workspace's existing digest
    /// path (no new hash dependency added here).
    pub fn qualifying_digest(&self) -> Result<String, QtQuoteError> {
        let value: Value =
            serde_json::to_value(&self.quoted).map_err(|e| QtQuoteError::Parse(e.to_string()))?;
        let bytes = jcs::canonicalize(&value).map_err(|e| QtQuoteError::Parse(e.to_string()))?;
        Ok(jcs::sha256_hex(&bytes))
    }

    /// `schema_id` recognized and `quote.pcr_digest` equals the recomputed
    /// qualifying digest of `quoted`.
    pub fn validate(&self) -> Result<(), QtQuoteError> {
        if self.schema_id != QT_QUOTE_SCHEMA_ID {
            return Err(QtQuoteError::BadSchemaId {
                found: self.schema_id.clone(),
            });
        }
        let expected = self.qualifying_digest()?;
        if expected != self.quote.pcr_digest {
            return Err(QtQuoteError::DigestMismatch {
                expected,
                found: self.quote.pcr_digest.clone(),
            });
        }
        Ok(())
    }
}
