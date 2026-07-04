//! P1 TPM2 attestor — real wiring lands in Phase 4 (HW-SW-014). This is a
//! typed contract stub only: `quote()` always returns
//! `AttestError::NotYetImplemented`; it never panics and never invokes an
//! unfinished-code macro.

use crate::{AttestError, AttestationQuote, Attestor, AttestorKind};

pub struct TpmAttestor;

impl Attestor for TpmAttestor {
    fn kind(&self) -> AttestorKind {
        AttestorKind::Tpm
    }

    fn quote(&self, _qualifying: &[u8; 32]) -> Result<AttestationQuote, AttestError> {
        Err(AttestError::NotYetImplemented { phase: "phase04" })
    }
}
