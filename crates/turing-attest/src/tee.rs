//! P2 TEE (Gramine/SGX) attestor — real wiring lands in Phase 7 (HW-SW-0xx
//! TEE phase). Typed contract stub only: `quote()` always returns
//! `AttestError::NotYetImplemented`; it never panics and never invokes an
//! unfinished-code macro.

use crate::{AttestError, AttestationQuote, Attestor, AttestorKind};

pub struct TeeAttestor;

impl Attestor for TeeAttestor {
    fn kind(&self) -> AttestorKind {
        AttestorKind::Tee
    }

    fn quote(&self, _qualifying: &[u8; 32]) -> Result<AttestationQuote, AttestError> {
        Err(AttestError::NotYetImplemented { phase: "phase07" })
    }
}
