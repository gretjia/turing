//! `turing-attest` — Phase 3 hardware attestation contract schemas (P0 pure
//! software, HW-SW-007..009). Defines the `Attestor` trait that Phase 4 (TPM)
//! and Phase 7 (TEE) implement against, plus the P0 `SimulatedAttestor` —
//! deterministic, unmistakably fake evidence (`signature` always carries a
//! `"simulated:"` prefix). No TPM/TEE code lives here; `tpm.rs`/`tee.rs` are
//! typed stubs returning `AttestError::NotYetImplemented`; they never
//! panic and never invoke an unfinished-code macro.

pub mod identity;
pub mod manifest;
pub mod policy;
pub mod qt_quote;
pub mod tee;
pub mod tpm;

/// Which family of evidence an [`Attestor`] produces.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AttestorKind {
    Simulated,
    Tpm,
    Tee,
    /// Real TPM 2.0 hardware reached via `/dev/tpmrm0` (HW-SW-011). This
    /// vTPM is hypervisor-backed, not silicon-rooted — `Vtpm` never implies
    /// a manufacturer EK certificate chain.
    Vtpm,
    /// A user-space `swtpm` simulator instance (HW-SW-010/011): real
    /// TPM2_Quote semantics, no hardware root of trust whatsoever.
    TpmSimulator,
}

/// A quote produced by an [`Attestor`]: the qualifying data it was bound to
/// and the (possibly fake, always typed) evidence produced over it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AttestationQuote {
    pub kind: AttestorKind,
    pub qualifying: [u8; 32],
    /// Evidence signature. `SimulatedAttestor` ALWAYS prefixes this with
    /// `"simulated:"` so it can never be mistaken for real hardware evidence.
    pub signature: String,
}

/// Errors an [`Attestor`] can return. Never a panic path.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AttestError {
    /// Backend has no P0 implementation; wired in a later phase.
    NotYetImplemented { phase: &'static str },
}

impl std::fmt::Display for AttestError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AttestError::NotYetImplemented { phase } => {
                write!(f, "attestor backend not yet implemented (lands {phase})")
            }
        }
    }
}

impl std::error::Error for AttestError {}

/// P0/P1/P2-uniform evidence-production contract (mirrors the `SigningBackend`
/// discipline in `turing-approval`): callers bind a 32-byte qualifying digest
/// and get typed evidence or a typed error back, never a panic.
pub trait Attestor {
    fn kind(&self) -> AttestorKind;
    fn quote(&self, qualifying: &[u8; 32]) -> Result<AttestationQuote, AttestError>;
}

/// P0 simulator: deterministic, always self-marking as fake. Never claims to
/// be hardware evidence.
pub struct SimulatedAttestor {
    pub device_id: String,
}

impl Attestor for SimulatedAttestor {
    fn kind(&self) -> AttestorKind {
        AttestorKind::Simulated
    }

    fn quote(&self, qualifying: &[u8; 32]) -> Result<AttestationQuote, AttestError> {
        Ok(AttestationQuote {
            kind: AttestorKind::Simulated,
            qualifying: *qualifying,
            signature: format!("simulated:{}", hex_lower(qualifying)),
        })
    }
}

/// Local lowercase-hex encoder. `turing-attest`'s only allowed dependencies
/// are serde/serde_json/toml/turing-contracts (no hash/hex crate), so this
/// tiny formatter stands in for the `hex` crate used by sibling crates.
pub(crate) fn hex_lower(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}
