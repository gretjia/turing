use turing_approval::{
    ApprovalCard, ApprovalPayload, DisplayCopy, HardwareSigningBackend, OsKeyringSigningBackend,
    SignatureRoute, SigningBackend, SigningError,
};

fn approval_payload() -> ApprovalPayload {
    ApprovalPayload {
        schema_id: "approval_payload.v2".to_string(),
        approval_id: "ap_merge_candidate".to_string(),
        authority_epoch: 7,
        action: "macro_merge_authorization".to_string(),
        subject_id: "macro:branch:turingos/wc_demo".to_string(),
        evidence_digests: vec![
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa".to_string(),
        ],
        risk_class: "P1".to_string(),
        signature_route: SignatureRoute::OsKeyring,
    }
}

#[test]
fn approval_bytes_four_way_identity() {
    let card = ApprovalCard::new(
        approval_payload(),
        DisplayCopy {
            title_zh: "批准候选合并".to_string(),
            body_en: "Authorize candidate merge after predicate review.".to_string(),
        },
    );

    let surfaces = card.byte_surfaces().expect("canonical byte surfaces");
    assert_eq!(surfaces.canonical_bytes, surfaces.visible_card_hash_bytes);
    assert_eq!(surfaces.canonical_bytes, surfaces.signed_bytes);
    assert_eq!(surfaces.canonical_bytes, surfaces.gate_replay_bytes);
    assert!(surfaces.visible_card_hash.starts_with("sha256:"));

    let signed_payload =
        String::from_utf8(surfaces.signed_bytes.clone()).expect("canonical payload is UTF-8");
    assert!(signed_payload.contains("approval_payload.v2"));
    assert!(!signed_payload.contains("批准候选合并"));
    assert!(!signed_payload.contains("Authorize candidate merge"));

    let changed_display = card.with_display_copy(DisplayCopy {
        title_zh: "显示文案可改".to_string(),
        body_en: "Display text can change without changing signed payload.".to_string(),
    });
    assert_eq!(
        surfaces.visible_card_hash,
        changed_display
            .byte_surfaces()
            .expect("display text stays outside signed payload")
            .visible_card_hash
    );
}

#[test]
fn signing_backend_has_no_plaintext_default_and_hardware_slot() {
    let card = ApprovalCard::new(
        approval_payload(),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );

    let os = OsKeyringSigningBackend::new("operator-local-key");
    assert!(!os.exports_plaintext_key());
    let signature = os.sign(&card).expect("OS keyring signature envelope");
    assert_eq!(signature.key_id, "operator-local-key");
    assert_eq!(signature.authority_epoch, 7);
    assert_eq!(signature.signature_route, SignatureRoute::OsKeyring);
    assert!(signature.signature.starts_with("sha256:"));

    let hardware = HardwareSigningBackend::slot("future-hsm-slot-0");
    assert!(!hardware.exports_plaintext_key());
    assert!(matches!(
        hardware.sign(&card),
        Err(SigningError::HardwareBackendUnavailable { .. })
    ));
}
