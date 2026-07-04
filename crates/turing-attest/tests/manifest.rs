//! HW-SW-007 (PREDICATE A2) — `hardware_manifest.toml` schema tests.

use std::fs;

use turing_attest::manifest::{HardwareManifest, ManifestError, MANIFEST_SCHEMA_VERSION};

fn workspace_manifest() -> String {
    fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../hardware_manifest.toml"
    ))
    .expect("hardware_manifest.toml must exist at worktree root")
}

#[test]
fn manifest_real_file_parses_and_validates() {
    let text = workspace_manifest();
    let manifest = HardwareManifest::parse(&text).expect("parse hardware_manifest.toml");
    manifest.validate().expect("validate hardware_manifest.toml");
    assert_eq!(manifest.schema_version, MANIFEST_SCHEMA_VERSION);
}

#[test]
fn manifest_bad_schema_version_rejected() {
    let text = workspace_manifest().replace("hardware_manifest.v1", "hardware_manifest.v0");
    let manifest = HardwareManifest::parse(&text).expect("parse");
    match manifest.validate() {
        Err(ManifestError::BadSchemaVersion { found }) => assert_eq!(found, "hardware_manifest.v0"),
        other => panic!("expected BadSchemaVersion, got {other:?}"),
    }
}

#[test]
fn manifest_missing_signing_section_rejected() {
    let text = workspace_manifest();
    let start = text.find("[signing]").expect("fixture has [signing]");
    let stripped = text[..start].to_string();
    let manifest = HardwareManifest::parse(&stripped).expect("parse");
    match manifest.validate() {
        Err(ManifestError::MissingSection { name }) => assert_eq!(name, "signing"),
        other => panic!("expected MissingSection, got {other:?}"),
    }
}

#[test]
fn manifest_non_hex_digest_rejected() {
    let text = workspace_manifest().replacen(
        "a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0",
        "0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0z",
        1,
    );
    let manifest = HardwareManifest::parse(&text).expect("parse");
    match manifest.validate() {
        Err(ManifestError::BadDigestFormat { field }) => {
            assert_eq!(field, "measurements.constitution_sha256")
        }
        other => panic!("expected BadDigestFormat, got {other:?}"),
    }
}

#[test]
fn manifest_uppercase_hex_digest_rejected() {
    let text = workspace_manifest().replacen(
        "a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0",
        "A0174EF8A2BE6914F86EA8E594E022C7CA6A4221ED63535D65A997E096CA3AD0",
        1,
    );
    let manifest = HardwareManifest::parse(&text).expect("parse");
    match manifest.validate() {
        Err(ManifestError::BadDigestFormat { field }) => {
            assert_eq!(field, "measurements.constitution_sha256")
        }
        other => panic!("expected BadDigestFormat, got {other:?}"),
    }
}

#[test]
fn manifest_non_ascii_device_id_rejected() {
    let text = workspace_manifest().replace("dev-zephryj-01", "dev-zéphryj-01");
    let manifest = HardwareManifest::parse(&text).expect("parse");
    match manifest.validate() {
        Err(ManifestError::NonAsciiKey { field }) => assert_eq!(field, "device.id"),
        other => panic!("expected NonAsciiKey, got {other:?}"),
    }
}
