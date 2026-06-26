//! Event payload models that carry load-bearing post-state inputs.
//!
//! Most registry events take an opaque `payload` object (kept as `serde_json::Value` on the
//! envelope). A few payloads, however, carry fields the **kernel** must read to derive the
//! post-state. The first of these is `project_law_amended.v1`, whose `new_authority_epoch`
//! drives the authority-epoch transition (`greenfield_spec_v5_3_1.md:215-217, 287`).
//!
//! **Provenance note.** The pack ratifies `ProjectLawAmended` as a `SOVEREIGN_ACCEPT` event
//! with `payload_schema_id == "project_law_amended.v1"` and `human_required: true`
//! (`event_registry_v5_3_1.json:46-54`), but ships **no** `project_law_amended.v1.schema.json`
//! file. This type is therefore modeled directly from the spec (an absent-but-derivable
//! payload shape, not a contradicted contract): per
//! `greenfield_spec_v5_3_1.md:215-217` the payload carries `new_authority_epoch`; per
//! `:216` the qualifying amendment is an `AUTHORITY_TRANSFER`; and per `:287` "only a
//! human-signed authority-transfer ProjectLawAmended may increment [the epoch] by one". Full
//! cryptographic signing arrives in M4; here `human_signed` is a typed marker, not a real
//! signature.

use serde::{Deserialize, Serialize};

use crate::jcs::{self, JcsError};

/// The kind of `ProjectLawAmended` amendment. Only an `AuthorityTransfer` may move the
/// authority epoch; any other lawful amendment leaves the epoch unchanged
/// (`greenfield_spec_v5_3_1.md:216`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AmendmentKind {
    /// An authority transfer — the only amendment that may increment `authority_epoch`.
    #[serde(rename = "AUTHORITY_TRANSFER")]
    AuthorityTransfer,
    /// Any other lawful project-law amendment; never touches the epoch.
    #[serde(rename = "OTHER")]
    Other,
}

/// The const `schema_id` for `project_law_amended.v1` consumers (the payload body itself has
/// no `schema_id` field; this is the registry identifier mirrored in the envelope's
/// `event_schema_id`).
pub const PROJECT_LAW_AMENDED_SCHEMA_ID: &str = "project_law_amended.v1";

/// `project_law_amended.v1` — the payload of a `ProjectLawAmended` SOVEREIGN_ACCEPT event.
///
/// `new_authority_epoch` is the epoch the amendment proposes. The kernel applies it **only**
/// when this is a `human_signed` `AUTHORITY_TRANSFER` that PASSed AND `new_authority_epoch ==
/// authority_epoch_before + 1`; otherwise the epoch is carried forward
/// (`greenfield_spec_v5_3_1.md:215-217, 287`). The qualification predicate is
/// [`Self::is_human_signed_authority_transfer`]; the kernel ([`crate`] consumers) owns the
/// `+ 1` arithmetic and the PASS gate.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProjectLawAmended {
    /// Which kind of amendment this is; only `AUTHORITY_TRANSFER` may move the epoch.
    pub amendment_kind: AmendmentKind,
    /// Whether this amendment carries a human authority signature (M4 will make this a real
    /// signature; here it is a typed marker). Only a human-signed transfer may bump the epoch.
    pub human_signed: bool,
    /// The authority epoch this amendment proposes. Applied only on a qualifying transfer
    /// (see the type docs); for `OTHER` amendments it is recorded but never read by the epoch
    /// transition.
    pub new_authority_epoch: u64,
}

impl ProjectLawAmended {
    /// A human-signed (or not, per `human_signed`) authority-transfer payload proposing
    /// `new_authority_epoch`.
    #[must_use]
    pub fn authority_transfer(new_authority_epoch: u64, human_signed: bool) -> Self {
        ProjectLawAmended {
            amendment_kind: AmendmentKind::AuthorityTransfer,
            human_signed,
            new_authority_epoch,
        }
    }

    /// A non-authority-transfer (`OTHER`) amendment. `new_authority_epoch` is recorded but is
    /// never applied by the epoch transition (only `AUTHORITY_TRANSFER` may bump the epoch);
    /// it defaults to `0` here since it is inert.
    #[must_use]
    pub fn non_authority_transfer(human_signed: bool) -> Self {
        ProjectLawAmended {
            amendment_kind: AmendmentKind::Other,
            human_signed,
            new_authority_epoch: 0,
        }
    }

    /// Whether this payload is a **human-signed authority transfer** — the necessary (not
    /// sufficient) condition for an epoch increment. The kernel additionally requires the
    /// event to be a PASSed `ProjectLawAmended` whose `new_authority_epoch == before + 1`.
    #[must_use]
    pub fn is_human_signed_authority_transfer(&self) -> bool {
        self.amendment_kind == AmendmentKind::AuthorityTransfer && self.human_signed
    }

    /// The canonical `turingos.jcs.v1` bytes of this payload — the committed payload body
    /// whose `sha256` is the envelope's `content_digest == payload_hash`.
    pub fn to_jcs_bytes(&self) -> Result<Vec<u8>, JcsError> {
        let value = serde_json::to_value(self)
            .expect("ProjectLawAmended serializes to a JSON object infallibly");
        jcs::canonicalize(&value)
    }

    /// Parse a `project_law_amended.v1` body from already-loaded JSON, enforcing the closed
    /// shape (`additionalProperties: false`): any extra key fails here rather than silently
    /// round-tripping.
    pub fn from_jcs_value(value: &serde_json::Value) -> Result<Self, JcsError> {
        serde_json::from_value(value.clone())
            .map_err(|e| JcsError::Malformed(format!("project_law_amended shape: {e}")))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn authority_transfer_is_a_human_signed_transfer_only_when_signed() {
        assert!(
            ProjectLawAmended::authority_transfer(8, true).is_human_signed_authority_transfer()
        );
        assert!(
            !ProjectLawAmended::authority_transfer(8, false).is_human_signed_authority_transfer()
        );
    }

    #[test]
    fn other_amendment_is_never_a_human_signed_transfer() {
        assert!(
            !ProjectLawAmended::non_authority_transfer(true).is_human_signed_authority_transfer()
        );
        assert!(
            !ProjectLawAmended::non_authority_transfer(false).is_human_signed_authority_transfer()
        );
    }

    #[test]
    fn round_trips_through_jcs() {
        let p = ProjectLawAmended::authority_transfer(8, true);
        let bytes = p.to_jcs_bytes().expect("canonicalizes");
        let value: serde_json::Value =
            serde_json::from_slice(&bytes).expect("canonical bytes parse");
        let back = ProjectLawAmended::from_jcs_value(&value).expect("parses back");
        assert_eq!(back, p);
    }

    #[test]
    fn rejects_unknown_field() {
        let value = serde_json::json!({
            "amendment_kind": "AUTHORITY_TRANSFER",
            "human_signed": true,
            "new_authority_epoch": 8,
            "phantom": 1
        });
        assert!(ProjectLawAmended::from_jcs_value(&value).is_err());
    }
}
