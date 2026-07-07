//! HW-SW-011 (SPEC B2) — swtpm-backed `TpmAttestor` roundtrip. Spawns its
//! own swtpm simulator instance (`tests/common/mod.rs::SwtpmGuard`), fully
//! independent of `scripts/attest-tpm.sh`'s state. No sudo anywhere in
//! this file.

mod common;

use turing_attest::tpm::{TpmAttestor, TpmError};
use turing_attest::{Attestor, AttestorKind};

#[test]
fn hardware_quote_roundtrip() {
    let guard = match common::SwtpmGuard::start() {
        Ok(g) => g,
        Err(common::SwtpmUnavailable) => {
            println!("SKIP: swtpm unavailable");
            return;
        }
    };

    let attestor = TpmAttestor::simulator(guard.tcti());
    assert_eq!(attestor.kind(), AttestorKind::TpmSimulator);

    let qualifying = [0x42u8; 32];

    // Inherent API: rich `TpmError` on failure.
    let quote = attestor
        .quote(&qualifying)
        .expect("hardware_quote_roundtrip: quote must succeed against a live swtpm");
    assert_eq!(quote.kind, AttestorKind::TpmSimulator);
    assert_eq!(quote.qualifying, qualifying);

    attestor
        .verify(&quote, &qualifying)
        .expect("verify() must accept the quote's own qualifying value");

    // Negative predicate (HW-SW-011 B2): a tampered qualifying value must
    // be rejected, not silently accepted.
    let mut tampered = qualifying;
    tampered[0] ^= 0xff;
    match attestor.verify(&quote, &tampered) {
        Err(TpmError::VerifyFailed { .. }) => {}
        other => panic!("expected VerifyFailed for a tampered qualifying value, got {other:?}"),
    }

    // Attestor trait adapter: happy path returns the same AttestationQuote
    // shape via the trait-object call path (proves "Implement Attestor
    // trait for TpmAttestor" actually works, not just compiles).
    let as_trait: &dyn Attestor = &attestor;
    assert_eq!(as_trait.kind(), AttestorKind::TpmSimulator);
    let trait_quote = as_trait
        .quote(&qualifying)
        .expect("Attestor trait adapter quote() must also succeed on the happy path");
    assert_eq!(trait_quote.kind, AttestorKind::TpmSimulator);
    assert_eq!(trait_quote.qualifying, qualifying);
}

#[test]
fn read_pcrs_returns_sha256_bank() {
    let guard = match common::SwtpmGuard::start() {
        Ok(g) => g,
        Err(common::SwtpmUnavailable) => {
            println!("SKIP: swtpm unavailable");
            return;
        }
    };

    let attestor = TpmAttestor::simulator(guard.tcti());
    let pcrs = attestor.read_pcrs("sha256:0,7").expect("read_pcrs must succeed against swtpm");
    assert_eq!(pcrs.bank, "sha256");
    let indices: Vec<u32> = pcrs.values.iter().map(|(i, _)| *i).collect();
    assert!(indices.contains(&0));
    assert!(indices.contains(&7));
    for (_, digest) in &pcrs.values {
        assert_eq!(digest.len(), 64, "sha256 PCR digest must be 64 hex chars, got {digest:?}");
    }
}
