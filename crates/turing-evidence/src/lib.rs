//! Evidence descriptors and lifecycle gates.
//!
//! This crate models evidence as replayable descriptors. It does not own truth and
//! does not move Micro heads; consumers append these structures to Tape through the
//! sovereign append path.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use turing_contracts::jcs::{self, JcsError};

pub const EVIDENCE_DESCRIPTOR_SCHEMA_ID: &str = "evidence_descriptor.v2";
pub const EVIDENCE_TOMBSTONED_SCHEMA_ID: &str = "evidence_tombstoned.v1";
pub const RAW_BYTES_PROFILE: &str = "raw-bytes.v1";
pub const JCS_PROFILE: &str = "turingos.jcs.v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EvidenceKind {
    RawBytes,
    Receipt,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EvidenceState {
    Candidate,
    Stored,
    Required,
    Tombstoned,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateStamp {
    pub state: EvidenceState,
    pub reason: String,
    pub at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceDescriptor {
    pub schema_id: String,
    pub evidence_id: String,
    pub kind: EvidenceKind,
    pub canonicalization_profile: String,
    pub content_digest: String,
    pub storage_digest: String,
    pub state: EvidenceState,
    pub state_history: Vec<StateStamp>,
    pub required: bool,
}

impl EvidenceDescriptor {
    pub fn raw_bytes(
        evidence_id: impl Into<String>,
        bytes: &[u8],
        created_at: impl Into<String>,
    ) -> Result<Self, EvidenceError> {
        Self::new(
            evidence_id,
            EvidenceKind::RawBytes,
            RAW_BYTES_PROFILE,
            digest(bytes),
            digest(bytes),
            created_at,
        )
    }

    pub fn receipt_json(
        evidence_id: impl Into<String>,
        receipt: &Value,
        created_at: impl Into<String>,
    ) -> Result<Self, EvidenceError> {
        let canonical = jcs::canonicalize(receipt)?;
        Self::new(
            evidence_id,
            EvidenceKind::Receipt,
            JCS_PROFILE,
            digest(&canonical),
            digest(&canonical),
            created_at,
        )
    }

    fn new(
        evidence_id: impl Into<String>,
        kind: EvidenceKind,
        canonicalization_profile: &str,
        content_digest: String,
        storage_digest: String,
        created_at: impl Into<String>,
    ) -> Result<Self, EvidenceError> {
        let evidence_id = evidence_id.into();
        if evidence_id.trim().is_empty() {
            return Err(EvidenceError::MissingEvidenceId);
        }
        validate_digest(&content_digest)?;
        validate_digest(&storage_digest)?;
        let at = created_at.into();
        Ok(EvidenceDescriptor {
            schema_id: EVIDENCE_DESCRIPTOR_SCHEMA_ID.to_string(),
            evidence_id,
            kind,
            canonicalization_profile: canonicalization_profile.to_string(),
            content_digest,
            storage_digest,
            state: EvidenceState::Stored,
            state_history: vec![StateStamp {
                state: EvidenceState::Stored,
                reason: "stored".to_string(),
                at,
            }],
            required: false,
        })
    }

    pub fn transition(
        &self,
        state: EvidenceState,
        reason: impl Into<String>,
        at: impl Into<String>,
    ) -> Result<Self, EvidenceError> {
        validate_digest(&self.content_digest)?;
        validate_digest(&self.storage_digest)?;
        let mut next = self.clone();
        next.state = state;
        if state == EvidenceState::Required {
            next.required = true;
        }
        next.state_history.push(StateStamp {
            state,
            reason: reason.into(),
            at: at.into(),
        });
        Ok(next)
    }

    pub fn upgrade_if_consumed(
        &self,
        kind: ConsumptionKind,
        event_id: impl Into<String>,
        at: impl Into<String>,
    ) -> Result<Self, EvidenceError> {
        let event_id = event_id.into();
        if !is_micro_id(&event_id) {
            return Err(EvidenceError::InvalidMicroEventId(event_id));
        }
        let reason = format!("{} consumed by {event_id}", kind.reason_marker());
        self.transition(EvidenceState::Required, reason, at)
    }

    pub fn request_tombstone(
        &self,
        reason: impl Into<String>,
        amendment_event_id: Option<&str>,
        at: impl Into<String>,
    ) -> Result<EvidenceTombstonePlan, EvidenceError> {
        let reason = reason.into();
        if self.required && amendment_event_id.is_none() {
            return Err(EvidenceError::RequiredEvidenceDeletionDenied);
        }
        let amendment_event_id = amendment_event_id.map(str::to_string);
        if let Some(id) = amendment_event_id.as_deref()
            && !is_micro_id(id)
        {
            return Err(EvidenceError::InvalidMicroEventId(id.to_string()));
        }

        let previous_descriptor_digest = self.descriptor_digest()?;
        let permanent_descriptor =
            self.transition(EvidenceState::Tombstoned, reason.clone(), at)?;
        Ok(EvidenceTombstonePlan {
            event: EvidenceTombstoned {
                schema_id: EVIDENCE_TOMBSTONED_SCHEMA_ID.to_string(),
                evidence_id: self.evidence_id.clone(),
                previous_descriptor_digest,
                reason,
                amendment_event_id,
            },
            permanent_descriptor,
        })
    }

    pub fn descriptor_digest(&self) -> Result<String, EvidenceError> {
        let value =
            serde_json::to_value(self).expect("EvidenceDescriptor serializes to JSON infallibly");
        let bytes = jcs::canonicalize(&value)?;
        Ok(digest(&bytes))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsumptionKind {
    Predicate,
    ApprovalCard,
    AcceptedHeadSupport,
}

impl ConsumptionKind {
    #[must_use]
    pub fn reason_marker(self) -> &'static str {
        match self {
            ConsumptionKind::Predicate => "predicate",
            ConsumptionKind::ApprovalCard => "approval_card",
            ConsumptionKind::AcceptedHeadSupport => "accepted_head",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceTombstoned {
    pub schema_id: String,
    pub evidence_id: String,
    pub previous_descriptor_digest: String,
    pub reason: String,
    pub amendment_event_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvidenceTombstonePlan {
    pub event: EvidenceTombstoned,
    pub permanent_descriptor: EvidenceDescriptor,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EvidenceError {
    MissingEvidenceId,
    InvalidDigest(String),
    InvalidMicroEventId(String),
    RequiredEvidenceDeletionDenied,
    Canonicalization(String),
}

impl std::fmt::Display for EvidenceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EvidenceError::MissingEvidenceId => write!(f, "evidence_id is required"),
            EvidenceError::InvalidDigest(digest) => write!(f, "invalid digest {digest:?}"),
            EvidenceError::InvalidMicroEventId(id) => write!(f, "invalid Micro event id {id:?}"),
            EvidenceError::RequiredEvidenceDeletionDenied => {
                write!(f, "REQUIRED evidence cannot be deleted without amendment")
            }
            EvidenceError::Canonicalization(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for EvidenceError {}

impl From<JcsError> for EvidenceError {
    fn from(value: JcsError) -> Self {
        EvidenceError::Canonicalization(value.to_string())
    }
}

fn digest(bytes: &[u8]) -> String {
    format!("sha256:{}", jcs::sha256_hex(bytes))
}

fn validate_digest(value: &str) -> Result<(), EvidenceError> {
    let rest = value
        .strip_prefix("sha256:")
        .ok_or_else(|| EvidenceError::InvalidDigest(value.to_string()))?;
    if rest.len() != 64 || !rest.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(EvidenceError::InvalidDigest(value.to_string()));
    }
    Ok(())
}

fn is_micro_id(value: &str) -> bool {
    let Some(rest) = value.strip_prefix("mu:") else {
        return false;
    };
    rest.len() == 64 && rest.bytes().all(|b| b.is_ascii_hexdigit())
}
