//! HW-SW-008 (PREDICATE B1) — `attestation_policy.toml` schema tests.

use std::fs;

use turing_attest::policy::{AttestationPolicy, PolicyError, POLICY_SCHEMA_VERSION};

fn workspace_policy() -> String {
    fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../attestation_policy.toml"
    ))
    .expect("attestation_policy.toml must exist at worktree root")
}

#[test]
fn policy_real_file_parses_and_validates() {
    let text = workspace_policy();
    let policy = AttestationPolicy::parse(&text).expect("parse attestation_policy.toml");
    policy.validate().expect("validate attestation_policy.toml");
    assert_eq!(
        policy.policy.as_ref().unwrap().schema_version,
        POLICY_SCHEMA_VERSION
    );
}

#[test]
fn policy_bad_on_fail_rejected() {
    let text = workspace_policy().replace("halt_authorization", "ignore_and_pray");
    let policy = AttestationPolicy::parse(&text).expect("parse");
    match policy.validate() {
        Err(PolicyError::BadOnFail { found }) => assert_eq!(found, "ignore_and_pray"),
        other => panic!("expected BadOnFail, got {other:?}"),
    }
}

#[test]
fn policy_debug_without_simulator_rejected() {
    let text = workspace_policy()
        .replace("allow_debug                  = false", "allow_debug                  = true")
        .replace("simulator_allowed = true", "simulator_allowed = false");
    let policy = AttestationPolicy::parse(&text).expect("parse");
    match policy.validate() {
        Err(PolicyError::DebugWithoutSimulator) => {}
        other => panic!("expected DebugWithoutSimulator, got {other:?}"),
    }
}

#[test]
fn policy_missing_degraded_section_rejected() {
    let text = workspace_policy();
    let start = text.find("[degraded]").expect("fixture has [degraded]");
    let stripped = text[..start].to_string();
    let policy = AttestationPolicy::parse(&stripped).expect("parse");
    match policy.validate() {
        Err(PolicyError::MissingSection { name }) => assert_eq!(name, "degraded"),
        other => panic!("expected MissingSection, got {other:?}"),
    }
}
