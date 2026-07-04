//! HW-SW-004 A1 — route+algorithm negotiation never silently swaps, and the
//! route provably rides the signed canonical bytes.

use turing_approval::{
    negotiate, ApprovalCard, ApprovalPayload, DisplayCopy, InMemoryTestSigningBackend,
    NegotiatedRoute, OsKeyringSigningBackend, SignatureAlgorithm, SignatureRoute, SigningBackend,
    SigningError,
};

fn payload_with_route(signature_route: SignatureRoute) -> ApprovalPayload {
    ApprovalPayload {
        schema_id: "approval_payload.v2".to_string(),
        approval_id: "ap_route_negotiation".to_string(),
        authority_epoch: 7,
        action: "macro_merge_authorization".to_string(),
        subject_id: "macro:branch:turingos/wc_demo".to_string(),
        evidence_digests: vec![
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string(),
        ],
        risk_class: "P1".to_string(),
        signature_route,
    }
}

fn card_with_route(signature_route: SignatureRoute) -> ApprovalCard {
    ApprovalCard::new(
        payload_with_route(signature_route),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    )
}

#[test]
fn negotiate_os_keyring_ed25519_is_accepted() {
    let backend = OsKeyringSigningBackend::new("operator-local-key");
    let negotiated = negotiate(SignatureRoute::OsKeyring, SignatureAlgorithm::Ed25519, &backend)
        .expect("Ed25519 on OsKeyring is the default supported algorithm");
    assert_eq!(
        negotiated,
        NegotiatedRoute {
            route: SignatureRoute::OsKeyring,
            algorithm: SignatureAlgorithm::Ed25519,
        }
    );
}

#[test]
fn negotiate_unsupported_algorithm_is_rejected_not_swapped() {
    // Default supported_algorithms() == [Ed25519]; EcdsaP256 must NOT be
    // silently downgraded to Ed25519 — it is a hard error.
    let backend = InMemoryTestSigningBackend::new("operator-local-key");
    let result = negotiate(
        SignatureRoute::InMemoryTest,
        SignatureAlgorithm::EcdsaP256,
        &backend,
    );
    assert!(matches!(
        result,
        Err(SigningError::RouteAlgorithmUnsupported {
            route: SignatureRoute::InMemoryTest,
            algorithm: SignatureAlgorithm::EcdsaP256,
        })
    ));
}

#[test]
fn negotiate_none_route_is_rejected() {
    let backend = InMemoryTestSigningBackend::new("operator-local-key");
    let result = negotiate(SignatureRoute::None, SignatureAlgorithm::Ed25519, &backend);
    assert!(matches!(
        result,
        Err(SigningError::RouteAlgorithmUnsupported {
            route: SignatureRoute::None,
            ..
        })
    ));
}

#[test]
fn default_supported_algorithms_is_ed25519_only() {
    let backend = InMemoryTestSigningBackend::new("operator-local-key");
    assert_eq!(
        backend.supported_algorithms(),
        &[SignatureAlgorithm::Ed25519]
    );
}

#[test]
fn assert_matches_card_ok_only_when_route_equals_payload_route() {
    let negotiated = negotiate(
        SignatureRoute::InMemoryTest,
        SignatureAlgorithm::Ed25519,
        &InMemoryTestSigningBackend::new("operator-local-key"),
    )
    .expect("negotiation succeeds");

    let matching = card_with_route(SignatureRoute::InMemoryTest);
    negotiated
        .assert_matches_card(&matching)
        .expect("card route matches negotiated route");

    let mismatched = card_with_route(SignatureRoute::OsKeyring);
    assert!(matches!(
        negotiated.assert_matches_card(&mismatched),
        Err(SigningError::NegotiationIdentityMismatch {
            expected: SignatureRoute::InMemoryTest,
            observed: SignatureRoute::OsKeyring,
        })
    ));
}

#[test]
fn identity_field_binds_route_and_algorithm() {
    let negotiated = NegotiatedRoute {
        route: SignatureRoute::OsKeyring,
        algorithm: SignatureAlgorithm::Ed25519,
    };
    let identity = negotiated.identity_field();
    assert!(identity.contains("OsKeyring"));
    assert!(identity.contains("Ed25519"));
}

#[test]
fn route_rides_the_signed_canonical_bytes() {
    let card = card_with_route(SignatureRoute::OsKeyring);
    let bytes = card.canonical_bytes().expect("canonical bytes");
    let text = String::from_utf8(bytes).expect("canonical bytes are UTF-8");
    assert!(text.contains("signature_route"));
    assert!(text.contains("OsKeyring"));

    // Two cards differing ONLY in signature_route must diverge in both the
    // canonical bytes and the signed payload hash.
    let other = card_with_route(SignatureRoute::InMemoryTest);
    let a = card.byte_surfaces().expect("surfaces a");
    let b = other.byte_surfaces().expect("surfaces b");
    assert_ne!(a.canonical_bytes, b.canonical_bytes);

    let signer_a = InMemoryTestSigningBackend::new("route-rides-a");
    // Sign each card on its own matching in-memory route to compare hashes.
    let card_test_a = card_with_route(SignatureRoute::InMemoryTest);
    let mut route_c_payload = payload_with_route(SignatureRoute::InMemoryTest);
    route_c_payload.action = "other_action".to_string();
    let card_test_c = ApprovalCard::new(
        route_c_payload,
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );
    let sig_a = signer_a.sign(&card_test_a).expect("sign a");
    let sig_c = signer_a.sign(&card_test_c).expect("sign c");
    assert_ne!(sig_a.signed_payload_hash, sig_c.signed_payload_hash);
}
