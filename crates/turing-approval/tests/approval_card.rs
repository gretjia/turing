use turing_approval::{
    ApprovalCard, ApprovalPayload, AuthorityKeySet, DisplayCopy, HardwareSigningBackend,
    InMemoryTestSigningBackend, LocalFileSigningBackend, OsKeyringSigningBackend, SignatureRoute,
    SigningBackend, SigningError,
};

fn approval_payload() -> ApprovalPayload {
    approval_payload_with_route(SignatureRoute::OsKeyring)
}

fn approval_payload_with_route(signature_route: SignatureRoute) -> ApprovalPayload {
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
        signature_route,
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
        approval_payload_with_route(SignatureRoute::InMemoryTest),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );

    let os = OsKeyringSigningBackend::new("operator-local-key");
    assert!(!os.exports_plaintext_key());
    assert_eq!(os.route(), SignatureRoute::OsKeyring);

    let test_backend = InMemoryTestSigningBackend::new("operator-local-key");
    let signature = test_backend
        .sign(&card)
        .expect("explicit in-memory test signature envelope");
    assert_eq!(signature.key_id, "operator-local-key");
    assert_eq!(signature.authority_epoch, 7);
    assert_eq!(signature.signature_route, SignatureRoute::InMemoryTest);
    assert!(signature.verifying_key.starts_with("ed25519-pub:"));
    assert!(signature.public_key_fingerprint.starts_with("sha256:"));
    assert!(signature.signature.starts_with("ed25519:"));

    let hardware = HardwareSigningBackend::slot("future-hsm-slot-0");
    assert!(!hardware.exports_plaintext_key());
    assert!(matches!(
        hardware.sign(&card),
        Err(SigningError::HardwareBackendUnavailable { .. })
    ));
}

#[test]
fn os_keyring_signatures_are_real_signatures_and_verify_against_payload_bytes() {
    let card = ApprovalCard::new(
        approval_payload_with_route(SignatureRoute::InMemoryTest),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );

    let signer = InMemoryTestSigningBackend::new("operator-local-key");
    let signature = signer.sign(&card).expect("signature envelope");
    let trusted_keys = AuthorityKeySet::from_record(
        signer
            .authority_key_record(card.payload().authority_epoch)
            .expect("trusted authority key record"),
    );
    let surfaces = card.byte_surfaces().expect("canonical surfaces");

    let recomputable = format!(
        "sha256:{}{}",
        turing_contracts::jcs::sha256_hex(&surfaces.canonical_bytes),
        "operator-local-key"
    );
    assert_ne!(signature.signature, recomputable);
    let verifier_without_private_key = InMemoryTestSigningBackend::verifier("operator-local-key");
    verifier_without_private_key
        .verify(&card, &signature, &trusted_keys)
        .expect("signature verifies from trusted key registry");

    let mut tampered_payload = approval_payload();
    tampered_payload.signature_route = SignatureRoute::InMemoryTest;
    tampered_payload.risk_class = "P3".to_string();
    let tampered = ApprovalCard::new(
        tampered_payload,
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );
    assert!(
        verifier_without_private_key
            .verify(&tampered, &signature, &trusted_keys)
            .is_err()
    );
}

#[test]
fn local_file_signature_verifies_without_private_seed_after_signing() {
    let dir = tempfile::tempdir().expect("temp dir");
    let card = ApprovalCard::new(
        approval_payload_with_route(SignatureRoute::LocalFileDev),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );

    let local = LocalFileSigningBackend::with_key_store_dir("operator-local-key", dir.path());
    assert!(local.exports_plaintext_key());
    let signature = local.sign(&card).expect("local file dev signature");
    let trusted_keys = AuthorityKeySet::from_record(
        local
            .authority_key_record(card.payload().authority_epoch)
            .expect("trusted local file dev key record"),
    );
    assert_eq!(signature.signature_route, SignatureRoute::LocalFileDev);

    let entries: Vec<_> = std::fs::read_dir(dir.path())
        .expect("read local file key dir")
        .collect::<Result<_, _>>()
        .expect("dir entries");
    assert_eq!(entries.len(), 1);
    let key_record =
        std::fs::read_to_string(entries[0].path()).expect("local file key record is readable");
    assert!(key_record.contains("signing_key_hex"));

    std::fs::remove_file(entries[0].path()).expect("delete private dev seed before verification");
    let clean_verifier =
        LocalFileSigningBackend::with_key_store_dir("operator-local-key", dir.path());
    clean_verifier
        .verify(&card, &signature, &trusted_keys)
        .expect("verification uses trusted key registry, not private seed");
    assert!(
        std::fs::read_dir(dir.path())
            .expect("read dir after verification")
            .next()
            .is_none(),
        "verification must not recreate private key material"
    );
}

#[test]
fn forged_public_key_with_same_key_id_is_rejected_by_trusted_key_registry() {
    let trusted_dir = tempfile::tempdir().expect("trusted key dir");
    let attacker_dir = tempfile::tempdir().expect("attacker key dir");
    let card = ApprovalCard::new(
        approval_payload_with_route(SignatureRoute::LocalFileDev),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );

    let trusted_signer =
        LocalFileSigningBackend::with_key_store_dir("operator-local-key", trusted_dir.path());
    let trusted_keys = AuthorityKeySet::from_record(
        trusted_signer
            .authority_key_record(card.payload().authority_epoch)
            .expect("trusted authority key record"),
    );

    let attacker_signer =
        LocalFileSigningBackend::with_key_store_dir("operator-local-key", attacker_dir.path());
    let forged_signature = attacker_signer
        .sign(&card)
        .expect("attacker can make a mathematically valid signature");

    assert!(
        trusted_signer
            .verify(&card, &forged_signature, &trusted_keys)
            .is_err(),
        "same key_id plus envelope-provided public key must not establish authority"
    );
}

#[test]
fn signature_authority_epoch_must_match_signed_payload_epoch() {
    let card = ApprovalCard::new(
        approval_payload_with_route(SignatureRoute::InMemoryTest),
        DisplayCopy {
            title_zh: "批准".to_string(),
            body_en: "Approve.".to_string(),
        },
    );
    let signer = InMemoryTestSigningBackend::new("operator-local-key");
    let mut signature = signer.sign(&card).expect("signature envelope");
    let trusted_keys = AuthorityKeySet::from_record(
        signer
            .authority_key_record(card.payload().authority_epoch)
            .expect("trusted authority key record"),
    );
    signature.authority_epoch += 1;

    assert!(
        InMemoryTestSigningBackend::verifier("operator-local-key")
            .verify(&card, &signature, &trusted_keys)
            .is_err(),
        "envelope authority_epoch must match the signed ApprovalPayload epoch"
    );
}
