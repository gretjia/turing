//! Approval cards and signing backend contracts.
//!
//! Approval bytes are sovereignty-bearing, so every consumer must sign, display-hash,
//! gate, and replay the same canonical payload bytes. Localized display copy is
//! deliberately outside that signed payload.

use serde::{Deserialize, Serialize};
use turing_contracts::jcs::{self, JcsError};

pub const APPROVAL_PAYLOAD_SCHEMA_ID: &str = "approval_payload.v2";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SignatureRoute {
    None,
    OsKeyring,
    HardwareFuture,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovalPayload {
    pub schema_id: String,
    pub approval_id: String,
    pub authority_epoch: u64,
    pub action: String,
    pub subject_id: String,
    pub evidence_digests: Vec<String>,
    pub risk_class: String,
    pub signature_route: SignatureRoute,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisplayCopy {
    pub title_zh: String,
    pub body_en: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApprovalCard {
    payload: ApprovalPayload,
    display_copy: DisplayCopy,
}

impl ApprovalCard {
    #[must_use]
    pub fn new(payload: ApprovalPayload, display_copy: DisplayCopy) -> Self {
        ApprovalCard {
            payload,
            display_copy,
        }
    }

    #[must_use]
    pub fn payload(&self) -> &ApprovalPayload {
        &self.payload
    }

    #[must_use]
    pub fn display_copy(&self) -> &DisplayCopy {
        &self.display_copy
    }

    #[must_use]
    pub fn with_display_copy(&self, display_copy: DisplayCopy) -> Self {
        ApprovalCard {
            payload: self.payload.clone(),
            display_copy,
        }
    }

    pub fn canonical_bytes(&self) -> Result<Vec<u8>, ApprovalError> {
        if self.payload.schema_id != APPROVAL_PAYLOAD_SCHEMA_ID {
            return Err(ApprovalError::InvalidSchemaId(
                self.payload.schema_id.clone(),
            ));
        }
        for digest in &self.payload.evidence_digests {
            validate_digest(digest)?;
        }
        let value = serde_json::to_value(&self.payload)
            .expect("ApprovalPayload serializes to JSON infallibly");
        Ok(jcs::canonicalize(&value)?)
    }

    pub fn byte_surfaces(&self) -> Result<ApprovalByteSurfaces, ApprovalError> {
        let canonical_bytes = self.canonical_bytes()?;
        let visible_card_hash = digest(&canonical_bytes);
        Ok(ApprovalByteSurfaces {
            visible_card_hash,
            visible_card_hash_bytes: canonical_bytes.clone(),
            signed_bytes: canonical_bytes.clone(),
            gate_replay_bytes: canonical_bytes.clone(),
            canonical_bytes,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApprovalByteSurfaces {
    pub canonical_bytes: Vec<u8>,
    pub visible_card_hash_bytes: Vec<u8>,
    pub signed_bytes: Vec<u8>,
    pub gate_replay_bytes: Vec<u8>,
    pub visible_card_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignatureEnvelope {
    pub schema_id: String,
    pub key_id: String,
    pub authority_epoch: u64,
    pub signature_route: SignatureRoute,
    pub signed_payload_hash: String,
    pub signature: String,
}

pub trait SigningBackend {
    fn key_id(&self) -> &str;
    fn route(&self) -> SignatureRoute;

    fn exports_plaintext_key(&self) -> bool {
        false
    }

    fn sign(&self, card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OsKeyringSigningBackend {
    key_id: String,
}

impl OsKeyringSigningBackend {
    #[must_use]
    pub fn new(key_id: impl Into<String>) -> Self {
        OsKeyringSigningBackend {
            key_id: key_id.into(),
        }
    }
}

impl SigningBackend for OsKeyringSigningBackend {
    fn key_id(&self) -> &str {
        &self.key_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::OsKeyring
    }

    fn sign(&self, card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        if card.payload.signature_route != SignatureRoute::OsKeyring {
            return Err(SigningError::RouteMismatch {
                expected: card.payload.signature_route,
                observed: SignatureRoute::OsKeyring,
            });
        }
        let bytes = card.canonical_bytes()?;
        let mut signature_preimage = bytes.clone();
        signature_preimage.extend_from_slice(self.key_id.as_bytes());
        Ok(SignatureEnvelope {
            schema_id: "approval_signature.v1".to_string(),
            key_id: self.key_id.clone(),
            authority_epoch: card.payload.authority_epoch,
            signature_route: SignatureRoute::OsKeyring,
            signed_payload_hash: digest(&bytes),
            signature: digest(&signature_preimage),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HardwareSigningBackend {
    slot_id: String,
}

impl HardwareSigningBackend {
    #[must_use]
    pub fn slot(slot_id: impl Into<String>) -> Self {
        HardwareSigningBackend {
            slot_id: slot_id.into(),
        }
    }
}

impl SigningBackend for HardwareSigningBackend {
    fn key_id(&self) -> &str {
        &self.slot_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::HardwareFuture
    }

    fn sign(&self, _card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApprovalError {
    InvalidSchemaId(String),
    InvalidDigest(String),
    Canonicalization(String),
}

impl std::fmt::Display for ApprovalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ApprovalError::InvalidSchemaId(schema_id) => {
                write!(
                    f,
                    "approval payload schema_id must be {APPROVAL_PAYLOAD_SCHEMA_ID:?}, got {schema_id:?}"
                )
            }
            ApprovalError::InvalidDigest(digest) => write!(f, "invalid digest {digest:?}"),
            ApprovalError::Canonicalization(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for ApprovalError {}

impl From<JcsError> for ApprovalError {
    fn from(value: JcsError) -> Self {
        ApprovalError::Canonicalization(value.to_string())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SigningError {
    Approval(ApprovalError),
    RouteMismatch {
        expected: SignatureRoute,
        observed: SignatureRoute,
    },
    HardwareBackendUnavailable {
        slot_id: String,
    },
}

impl std::fmt::Display for SigningError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SigningError::Approval(error) => write!(f, "{error}"),
            SigningError::RouteMismatch { expected, observed } => {
                write!(
                    f,
                    "signature route mismatch: expected {expected:?}, observed {observed:?}"
                )
            }
            SigningError::HardwareBackendUnavailable { slot_id } => {
                write!(
                    f,
                    "hardware signing backend slot {slot_id:?} is reserved but unavailable"
                )
            }
        }
    }
}

impl std::error::Error for SigningError {}

impl From<ApprovalError> for SigningError {
    fn from(value: ApprovalError) -> Self {
        SigningError::Approval(value)
    }
}

fn digest(bytes: &[u8]) -> String {
    format!("sha256:{}", jcs::sha256_hex(bytes))
}

fn validate_digest(value: &str) -> Result<(), ApprovalError> {
    let rest = value
        .strip_prefix("sha256:")
        .ok_or_else(|| ApprovalError::InvalidDigest(value.to_string()))?;
    if rest.len() != 64 || !rest.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(ApprovalError::InvalidDigest(value.to_string()));
    }
    Ok(())
}
