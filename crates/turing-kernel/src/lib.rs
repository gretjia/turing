//! turing-kernel — admission, reducer, authority guard, and registry-derived head effect.
//!
//! M0_SUBSTRATE ship gates owned here:
//! - SG-13  failure always appends (parse/predicate/timeout/observer failures land a typed failure, heads preserved)
//! - SG-15  authorization ref law (only AUTHORIZATION + PASS advances authorization_head)
//! - SG-16  accepted ref law (only SOVEREIGN_ACCEPT + PASS advances accepted_head)
//! - SG-17  registry-derived head effect (carried class/effect mismatch rejects; epoch +1 only on signed ProjectLawAmended)
//!
//! Top Whitebox stays synchronous pure functions over closed values; I/O lives in bottom-whitebox facades.
//!
//! The pure head-transition reducer ([`reducer`]) is established here at SG-12 (it is what
//! the Git Tape append calls to decide which sovereign head a transition moves) and is
//! then exhaustively re-verified by SG-15/16/17; SG-13 extends the same decision with
//! typed failure-node construction.

pub mod admission;
pub mod failure;
pub mod reducer;
