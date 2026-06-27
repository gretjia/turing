//! turing-contracts — closed types, identities, schemas, and canonical bytes.
//!
//! M0_SUBSTRATE ship gates owned here:
//! - SG-10  restricted `turingos.jcs.v1` canonical codec (cross-implementation equality; forbidden-value reject)
//! - SG-11  identity profile (`mu:` + 64 lowercase hex only; Greek `μ:` / 40-hex rejected)
//!
//! It also provides the closed schema types and the embedded event registry composed by
//! the kernel reducer and the Git Tape append (SG-12 onward):
//! - [`envelope`] — `MicroEventEnvelope.v1` (the committed body) + `HeadSet.v1`.
//! - [`registry`] — the parsed-once 46-event registry (`class` / `head_effect` /
//!   `target_ref` / `predicate_required`, all registry-derived).
//! - [`failure`] — the closed 17-value `FailureClass`, the 5-value `Disposition`, the
//!   parsed-once `17 → 5` disposition map (`dispose`), and `failure_node_payload.v1`.
//!
//! The canonical codec + `turingos.semantic_digest.v1` live in [`jcs`].
//! The greenfield `MicroOid` identity validator lives in [`identity`].

pub mod envelope;
pub mod failure;
pub mod goal;
pub mod identity;
pub mod jcs;
pub mod payload;
pub mod registry;
