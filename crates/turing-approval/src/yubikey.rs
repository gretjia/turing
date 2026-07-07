//! Feature-gated YubiKey PIV signing skeleton (HW-SW-006).
//!
//! Behind `--features yubikey`. There is NO device here and NO new dependency:
//! this is the reserved seam, not an implementation. Every operation returns
//! `SigningError::HardwareBackendUnavailable` and NEVER panics, mirroring
//! `HardwareSigningBackend`. It reports `route() = HardwareFuture` today; a
//! concrete `YubiKeyPiv` route variant is deferred to real device integration
//! (documented in docs/security/key_hierarchy.md) to avoid churning the
//! signed-byte wire vocabulary.

use crate::{
    ApprovalCard, AuthorityKeyRecord, AuthorityKeySet, SignatureAlgorithm, SignatureEnvelope,
    SignatureRoute, SigningBackend, SigningError,
};

/// Reserved YubiKey PIV signing backend; no device is wired.
///
/// Constraint: with no device present every signing/verification operation is
/// `Err(HardwareBackendUnavailable)` and never panics; it never fabricates a
/// signature or silently falls back to a software key.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct YubiKeySigningBackend {
    slot_id: String,
}

impl YubiKeySigningBackend {
    /// Names the (currently absent) PIV slot this backend would drive.
    ///
    /// Constraint: construction is infallible and touches no device; failure is
    /// surfaced only when an operation is attempted.
    #[must_use]
    pub fn slot(slot_id: impl Into<String>) -> Self {
        YubiKeySigningBackend {
            slot_id: slot_id.into(),
        }
    }
}

impl SigningBackend for YubiKeySigningBackend {
    fn key_id(&self) -> &str {
        &self.slot_id
    }

    fn route(&self) -> SignatureRoute {
        SignatureRoute::HardwareFuture
    }

    /// A real YubiKey PIV slot could offer either algorithm; the concrete
    /// device negotiation is deferred, but the offered set is declared here so
    /// `negotiate` has an explicit hardware fallback to accept.
    fn supported_algorithms(&self) -> &'static [SignatureAlgorithm] {
        &[SignatureAlgorithm::Ed25519, SignatureAlgorithm::EcdsaP256]
    }

    fn sign(&self, _card: &ApprovalCard) -> Result<SignatureEnvelope, SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }

    fn authority_key_record(
        &self,
        _authority_epoch: u64,
    ) -> Result<AuthorityKeyRecord, SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }

    fn verify(
        &self,
        _card: &ApprovalCard,
        _signature: &SignatureEnvelope,
        _trusted_keys: &AuthorityKeySet,
    ) -> Result<(), SigningError> {
        Err(SigningError::HardwareBackendUnavailable {
            slot_id: self.slot_id.clone(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        negotiate, ApprovalCard, ApprovalPayload, AuthorityKeySet, DisplayCopy,
        InMemoryTestSigningBackend, NegotiatedRoute,
    };

    fn card() -> ApprovalCard {
        ApprovalCard::new(
            ApprovalPayload {
                schema_id: "approval_payload.v2".to_string(),
                approval_id: "ap_yubikey".to_string(),
                authority_epoch: 7,
                action: "macro_merge_authorization".to_string(),
                subject_id: "macro:branch:turingos/wc_demo".to_string(),
                evidence_digests: vec![],
                risk_class: "P1".to_string(),
                signature_route: SignatureRoute::HardwareFuture,
            },
            DisplayCopy {
                title_zh: "批准".to_string(),
                body_en: "Approve.".to_string(),
            },
        )
    }

    #[test]
    fn every_operation_is_unavailable_and_never_panics() {
        let backend = YubiKeySigningBackend::slot("yubikey-piv-9a");
        assert_eq!(backend.route(), SignatureRoute::HardwareFuture);
        assert!(!backend.exports_plaintext_key());
        assert!(matches!(
            backend.sign(&card()),
            Err(SigningError::HardwareBackendUnavailable { .. })
        ));
        assert!(matches!(
            backend.authority_key_record(7),
            Err(SigningError::HardwareBackendUnavailable { .. })
        ));
        assert!(matches!(
            backend.verify(&card(), &sig_placeholder(), &AuthorityKeySet::default()),
            Err(SigningError::HardwareBackendUnavailable { .. })
        ));
    }

    fn sig_placeholder() -> SignatureEnvelope {
        SignatureEnvelope {
            schema_id: "approval_signature.v1".to_string(),
            key_id: "yubikey-piv-9a".to_string(),
            authority_epoch: 7,
            signature_route: SignatureRoute::HardwareFuture,
            public_key_fingerprint: "sha256:00".to_string(),
            verifying_key: "ed25519-pub:00".to_string(),
            signed_payload_hash: "sha256:00".to_string(),
            signature: "ed25519:00".to_string(),
        }
    }

    #[test]
    fn negotiate_hardware_ecdsa_is_the_explicit_fallback() {
        let backend = YubiKeySigningBackend::slot("yubikey-piv-9a");
        let negotiated = negotiate(
            SignatureRoute::HardwareFuture,
            SignatureAlgorithm::EcdsaP256,
            &backend,
        )
        .expect("hardware backend explicitly supports EcdsaP256");
        assert_eq!(
            negotiated,
            NegotiatedRoute {
                route: SignatureRoute::HardwareFuture,
                algorithm: SignatureAlgorithm::EcdsaP256,
            }
        );
    }

    #[test]
    fn software_backend_never_silently_swaps_to_ecdsa() {
        let backend = InMemoryTestSigningBackend::new("k");
        let result = negotiate(
            SignatureRoute::InMemoryTest,
            SignatureAlgorithm::EcdsaP256,
            &backend,
        );
        assert!(matches!(
            result,
            Err(SigningError::RouteAlgorithmUnsupported { .. })
        ));
    }
}
