//! HW-SW-008 (PREDICATE B2) — `device_identity.json` schema tests.

use std::fs;

use turing_attest::identity::{DeviceIdentity, IdentityError, IDENTITY_SCHEMA_ID};

fn workspace_identity() -> String {
    fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../device_identity.json"
    ))
    .expect("device_identity.json must exist at worktree root")
}

#[test]
fn identity_real_file_parses_and_validates() {
    let text = workspace_identity();
    let identity = DeviceIdentity::parse(&text).expect("parse device_identity.json");
    identity.validate().expect("validate device_identity.json");
    assert_eq!(identity.schema_id, IDENTITY_SCHEMA_ID);
}

#[test]
fn identity_unknown_route_rejected() {
    let text = workspace_identity().replace("\"os_keyring\"", "\"quantum_vibes\"");
    let identity = DeviceIdentity::parse(&text).expect("parse");
    match identity.validate() {
        Err(IdentityError::UnknownIdentityRoute { found }) => assert_eq!(found, "quantum_vibes"),
        other => panic!("expected UnknownIdentityRoute, got {other:?}"),
    }
}

#[test]
fn identity_non_ascii_key_rejected() {
    let text = workspace_identity().replace("\"lineage\"", "\"lineagé\"");
    match DeviceIdentity::parse(&text) {
        Err(IdentityError::NonAsciiKey(_)) => {}
        other => panic!("expected NonAsciiKey, got {other:?}"),
    }
}
