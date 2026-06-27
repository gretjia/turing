use serde_json::json;
use turing_evidence::{
    ConsumptionKind, EvidenceDescriptor, EvidenceError, EvidenceKind, EvidenceState,
};

#[test]
fn evidence_descriptor_digests_profiles_and_state_stamps() {
    let created_at = "2026-06-27T00:00:00Z";
    let raw = EvidenceDescriptor::raw_bytes("ev_raw", b"macro diff", created_at)
        .expect("raw bytes evidence descriptor");

    assert_eq!(raw.schema_id, "evidence_descriptor.v2");
    assert_eq!(raw.kind, EvidenceKind::RawBytes);
    assert_eq!(raw.canonicalization_profile, "raw-bytes.v1");
    assert!(raw.content_digest.starts_with("sha256:"));
    assert!(raw.storage_digest.starts_with("sha256:"));
    assert_eq!(raw.state, EvidenceState::Stored);
    assert_eq!(raw.state_history.len(), 1);
    assert_eq!(raw.state_history[0].state, EvidenceState::Stored);

    let receipt = EvidenceDescriptor::receipt_json(
        "ev_receipt",
        &json!({"schema_id":"worker_run_receipt.v2","exit_code":0}),
        created_at,
    )
    .expect("JCS receipt evidence descriptor");

    assert_eq!(receipt.kind, EvidenceKind::Receipt);
    assert_eq!(receipt.canonicalization_profile, "turingos.jcs.v1");
    assert_ne!(raw.content_digest, receipt.content_digest);

    let transitioned = raw
        .transition(
            EvidenceState::Candidate,
            "operator-visible staging",
            "2026-06-27T00:01:00Z",
        )
        .expect("state transition is stamped");
    assert_eq!(transitioned.state, EvidenceState::Candidate);
    assert_eq!(transitioned.state_history.len(), 2);
    assert_eq!(
        transitioned.state_history[1].reason,
        "operator-visible staging"
    );
}

#[test]
fn consumed_evidence_upgrades_to_required() {
    let raw =
        EvidenceDescriptor::raw_bytes("ev_predicate", b"predicate input", "2026-06-27T00:00:00Z")
            .expect("raw descriptor");

    for kind in [
        ConsumptionKind::Predicate,
        ConsumptionKind::ApprovalCard,
        ConsumptionKind::AcceptedHeadSupport,
    ] {
        let upgraded = raw
            .upgrade_if_consumed(
                kind,
                "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "2026-06-27T00:02:00Z",
            )
            .expect("consumed evidence is upgraded");
        assert_eq!(upgraded.state, EvidenceState::Required);
        assert!(upgraded.required);
        assert!(
            upgraded
                .state_history
                .iter()
                .any(|stamp| stamp.reason.contains(kind.reason_marker()))
        );
    }
}

#[test]
fn evidence_required_immutable() {
    let required =
        EvidenceDescriptor::raw_bytes("ev_required", b"accepted proof", "2026-06-27T00:00:00Z")
            .expect("raw descriptor")
            .upgrade_if_consumed(
                ConsumptionKind::AcceptedHeadSupport,
                "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "2026-06-27T00:03:00Z",
            )
            .expect("required evidence");

    let denied = required.request_tombstone("operator cleanup", None, "2026-06-27T00:04:00Z");
    assert!(matches!(
        denied,
        Err(EvidenceError::RequiredEvidenceDeletionDenied)
    ));

    let tombstone = required
        .request_tombstone(
            "constitutional amendment",
            Some("mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"),
            "2026-06-27T00:05:00Z",
        )
        .expect("amendment can tombstone required evidence");
    assert_eq!(tombstone.event.schema_id, "evidence_tombstoned.v1");
    assert_eq!(tombstone.event.evidence_id, "ev_required");
    assert!(
        tombstone
            .event
            .previous_descriptor_digest
            .starts_with("sha256:")
    );
    assert!(
        tombstone
            .permanent_descriptor
            .state_history
            .iter()
            .any(|stamp| {
                stamp.state == EvidenceState::Tombstoned
                    && stamp.reason == "constitutional amendment"
            })
    );
}
