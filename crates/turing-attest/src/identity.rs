//! `device_identity.v1` — HW-SW-008. WHO this device is: public identity and
//! key-slot *references* only. Never carries private key material.

use serde::Deserialize;
use turing_contracts::jcs::{self, JcsError};

pub const IDENTITY_SCHEMA_ID: &str = "device_identity.v1";

/// Closed world of recognized `identity_route` values (06_boot_gate.md §5.d).
/// `puf_research` is P2-research only and never a sovereign signing route,
/// but it is still a *known* route name here; that policy constraint is
/// enforced elsewhere, not by this schema-layer validator.
const KNOWN_IDENTITY_ROUTES: &[&str] = &["os_keyring", "tpm_ak", "yubikey", "puf_research"];

/// Errors raised by [`DeviceIdentity::parse`] / [`DeviceIdentity::validate`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IdentityError {
    /// `schema_id` did not match [`IDENTITY_SCHEMA_ID`].
    BadSchemaId { found: String },
    /// `identity_route` was outside [`KNOWN_IDENTITY_ROUTES`].
    UnknownIdentityRoute { found: String },
    /// A non-ASCII object key was found anywhere in the document.
    NonAsciiKey(String),
    /// The document was not valid JSON at all.
    Parse(String),
}

impl std::fmt::Display for IdentityError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IdentityError::BadSchemaId { found } => write!(
                f,
                "unknown schema_id {found:?}, expected {IDENTITY_SCHEMA_ID:?}"
            ),
            IdentityError::UnknownIdentityRoute { found } => {
                write!(f, "unknown identity_route {found:?}")
            }
            IdentityError::NonAsciiKey(k) => write!(f, "non-ASCII load-bearing key: {k}"),
            IdentityError::Parse(m) => write!(f, "device_identity.json parse: {m}"),
        }
    }
}

impl std::error::Error for IdentityError {}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PublicKeyRef {
    pub key_id: String,
    pub algorithm: String,
    pub route: String,
    pub attestation_ref: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Lineage {
    pub parent_device: Option<String>,
    pub enrollment_receipt: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DeviceIdentity {
    pub schema_id: String,
    pub device_id: String,
    pub created_at: String,
    pub identity_route: String,
    pub public_keys: Vec<PublicKeyRef>,
    pub lineage: Lineage,
}

impl DeviceIdentity {
    /// Parse raw JSON, rejecting non-ASCII / duplicate object keys anywhere
    /// via the workspace's `turingos.jcs.v1` strict grammar (reused from
    /// `turing-contracts`, not reimplemented here) before the typed decode.
    pub fn parse(text: &str) -> Result<Self, IdentityError> {
        jcs::parse_strict(text).map_err(|e| match e {
            JcsError::NonAsciiKey(k) => IdentityError::NonAsciiKey(k),
            other => IdentityError::Parse(other.to_string()),
        })?;
        serde_json::from_str(text).map_err(|e| IdentityError::Parse(e.to_string()))
    }

    /// `schema_id` recognized and `identity_route` in the closed world.
    pub fn validate(&self) -> Result<(), IdentityError> {
        if self.schema_id != IDENTITY_SCHEMA_ID {
            return Err(IdentityError::BadSchemaId {
                found: self.schema_id.clone(),
            });
        }
        if !KNOWN_IDENTITY_ROUTES.contains(&self.identity_route.as_str()) {
            return Err(IdentityError::UnknownIdentityRoute {
                found: self.identity_route.clone(),
            });
        }
        Ok(())
    }
}
