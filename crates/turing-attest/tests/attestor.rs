//! HW-SW-009 (PREDICATE C1) — `Attestor` trait, `SimulatedAttestor`, and the
//! `tee.rs` typed stub. `tpm.rs` graduated from a typed stub to a real
//! `tpm2-tools`-backed attestor in HW-SW-011 (Phase 4); its dedicated
//! coverage (swtpm roundtrip, tamper rejection) lives in `tests/tpm.rs`.
//! This file keeps only the construction-time (no swtpm required) checks:
//! the two constructors report the two new hardware `AttestorKind`
//! variants correctly.

use turing_attest::tee::TeeAttestor;
use turing_attest::tpm::TpmAttestor;
use turing_attest::{AttestError, AttestationQuote, Attestor, AttestorKind, SimulatedAttestor};

#[test]
fn simulated_attestor_quote_is_marked_fake() {
    let attestor = SimulatedAttestor {
        device_id: "dev-zephryj-01".into(),
    };
    let qualifying = [7u8; 32];
    let quote: AttestationQuote = attestor
        .quote(&qualifying)
        .expect("simulated quote never fails");
    assert_eq!(quote.kind, AttestorKind::Simulated);
    assert_eq!(attestor.kind(), AttestorKind::Simulated);
    assert!(quote.signature.starts_with("simulated:"));

    // Deterministic: same qualifying data -> same signature.
    let again = attestor
        .quote(&qualifying)
        .expect("simulated quote never fails");
    assert_eq!(quote.signature, again.signature);
}

#[test]
fn tee_stub_typed_error_never_panics() {
    let tee = TeeAttestor;
    match tee.quote(&[0u8; 32]) {
        Err(AttestError::NotYetImplemented { phase }) => assert_eq!(phase, "phase07"),
        other => panic!("expected NotYetImplemented, got {other:?}"),
    }
    assert_eq!(tee.kind(), AttestorKind::Tee);
}

#[test]
fn tpm_attestor_constructors_report_correct_kind() {
    // No swtpm/device access needed: construction alone must not touch the
    // network or spawn a process (kind() is a pure field read).
    let sim = TpmAttestor::simulator("swtpm:host=localhost,port=0");
    assert_eq!(sim.kind(), AttestorKind::TpmSimulator);
    assert_eq!(Attestor::kind(&sim), AttestorKind::TpmSimulator);

    let real = TpmAttestor::device("/dev/tpmrm0");
    assert_eq!(real.kind(), AttestorKind::Vtpm);
    assert_eq!(Attestor::kind(&real), AttestorKind::Vtpm);
}
