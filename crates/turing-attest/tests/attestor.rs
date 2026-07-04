//! HW-SW-009 (PREDICATE C1) — `Attestor` trait, `SimulatedAttestor`, and the
//! `tpm.rs`/`tee.rs` typed stubs.

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
fn stub_backends_typed_error_never_panics() {
    let tpm = TpmAttestor;
    match tpm.quote(&[0u8; 32]) {
        Err(AttestError::NotYetImplemented { phase }) => assert_eq!(phase, "phase04"),
        other => panic!("expected NotYetImplemented, got {other:?}"),
    }
    assert_eq!(tpm.kind(), AttestorKind::Tpm);

    let tee = TeeAttestor;
    match tee.quote(&[0u8; 32]) {
        Err(AttestError::NotYetImplemented { phase }) => assert_eq!(phase, "phase07"),
        other => panic!("expected NotYetImplemented, got {other:?}"),
    }
    assert_eq!(tee.kind(), AttestorKind::Tee);
}
