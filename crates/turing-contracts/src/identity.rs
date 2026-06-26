//! Greenfield Micro identity (`MicroOid`) — the single source of truth.
//!
//! Every governed artifact/event/grant/predicate/capability/budget is identified by
//! a content hash in EXACTLY this form (the immutable invariant):
//!
//! ```text
//! ^mu:[0-9a-f]{64}$
//! ```
//!
//! i.e. the ASCII `mu:` literal prefix — bytes `m` (0x6D), `u` (0x75), `:` (0x3A) —
//! followed by exactly 64 LOWERCASE hexadecimal characters (a bare SHA-256 digest).
//!
//! Ratified by ADR-007 §3-4 (`pack/02_decisions/adr_007_capability_grant_and_identity_v5_3_1.md`),
//! the `$defs.microOid` pattern in `capability_grant.v1.schema.json`, and the frozen
//! byte form / conformance matrix in `execd_verification_v5_3_1.md` §1, §6.
//!
//! ## Rejected (each a distinct, deliberate failure)
//! - Greek `μ:` prefix — U+00B5 MICRO SIGN and/or U+03BC GREEK SMALL LETTER MU in
//!   place of the ASCII `m`+`u`. Both reject ([`IdentityError::BadPrefix`]).
//! - 40-hex (SHA-1 length) identities, even with a correct `mu:` prefix — the tail
//!   must be EXACTLY 64 hex chars ([`IdentityError::BadLength`]).
//! - Uppercase hex (e.g. `mu:ABC…`) — the class is `[0-9a-f]`, lowercase ONLY
//!   ([`IdentityError::NonLowerHex`]).
//! - Any other length, non-hex characters, a missing/wrong prefix, or extra
//!   leading/trailing data (including embedded whitespace/newlines).
//!
//! "Greenfield mode" is the DEFAULT and only-enabled validator path: there is no
//! runtime flag. Any legacy 40-hex decoder is a separate, default-off migration
//! feature (ADR-007 §4) and is intentionally not reachable from this module.

use std::fmt;

/// The number of lowercase-hex characters in a greenfield identity (a bare
/// SHA-256 digest rendered as hex).
const HEX_LEN: usize = 64;

/// The ASCII `mu:` prefix: bytes `m` (0x6D), `u` (0x75), `:` (0x3A).
const PREFIX: &str = "mu:";

/// Why a candidate string is not a valid greenfield [`MicroOid`].
///
/// Each variant pins a structurally distinct reject reason so a test (and any
/// caller surfacing a failure) can bind the precise cause; a future weakening
/// that collapses or mis-routes these reasons fails the SG-11 gate.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum IdentityError {
    /// The candidate does not begin with the ASCII `mu:` prefix. This is the
    /// reject path for Greek `μ:` (U+00B5 / U+03BC), an uppercase `MU:`, a
    /// `sha256:`/other prefix, a bare digest with no prefix, or leading junk.
    BadPrefix {
        /// A short, ASCII-safe description of what was found instead of `mu:`.
        found: String,
    },
    /// The prefix was correct but the hex tail was not exactly 64 characters
    /// (covers 40-hex SHA-1 length, 63/65, empty, and any other length). This is
    /// measured in bytes; a non-ASCII byte in the tail also fails [`Self::NonLowerHex`].
    BadLength {
        /// The number of bytes after the `mu:` prefix.
        tail_len: usize,
    },
    /// The prefix and length were correct but a tail character was not a lowercase
    /// hex digit `[0-9a-f]` (covers uppercase hex, `g`/`z`, embedded space, or any
    /// non-`[0-9a-f]` byte).
    NonLowerHex {
        /// Byte offset within the tail (0-based) of the first offending character.
        offset: usize,
    },
}

impl fmt::Display for IdentityError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            IdentityError::BadPrefix { found } => write!(
                f,
                "identity: missing ASCII `mu:` prefix (found {found}); greenfield MicroOid is `mu:` + 64 lowercase hex"
            ),
            IdentityError::BadLength { tail_len } => write!(
                f,
                "identity: hex tail must be exactly {HEX_LEN} lowercase hex chars, found {tail_len}"
            ),
            IdentityError::NonLowerHex { offset } => write!(
                f,
                "identity: non-lowercase-hex character at tail offset {offset} (class is [0-9a-f])"
            ),
        }
    }
}

impl std::error::Error for IdentityError {}

/// Is `b` an ASCII lowercase hex digit `[0-9a-f]`? Excludes uppercase `A-F` by design.
#[inline]
const fn is_lower_hex(b: u8) -> bool {
    b.is_ascii_digit() || matches!(b, b'a'..=b'f')
}

/// A validated greenfield Micro identity: `mu:` + 64 lowercase hex.
///
/// Construct via [`MicroOid::parse`]; there is no other way to obtain one, so a
/// `MicroOid` value is a proof that the contained string matches `^mu:[0-9a-f]{64}$`.
/// The wrapped `String` is always exactly 67 bytes and is preserved verbatim
/// (round-trips through [`MicroOid::as_str`]).
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct MicroOid(String);

impl MicroOid {
    /// Validate `s` against the frozen greenfield pattern `^mu:[0-9a-f]{64}$`.
    ///
    /// Returns the [`MicroOid`] on success, or the precise [`IdentityError`] on the
    /// first structural violation (prefix, then length, then hex class). This is
    /// the single canonical entry point for greenfield identity validation.
    pub fn parse(s: &str) -> Result<MicroOid, IdentityError> {
        // 1) Prefix MUST be the byte-exact ASCII `mu:`. Comparing on the raw bytes
        //    rejects any Unicode homoglyph (Greek U+00B5 / U+03BC encode to multi-byte
        //    UTF-8 that cannot equal 0x6D 0x75) and an uppercase `MU:`.
        let Some(tail) = s.strip_prefix(PREFIX) else {
            return Err(IdentityError::BadPrefix {
                found: describe_prefix(s),
            });
        };

        // 2) The remainder MUST be exactly 64 chars. Measured in bytes: a valid tail
        //    is pure ASCII (1 byte/char), and any non-ASCII byte is caught in step 3.
        if tail.len() != HEX_LEN {
            return Err(IdentityError::BadLength {
                tail_len: tail.len(),
            });
        }

        // 3) Every tail byte MUST be a LOWERCASE hex digit [0-9a-f]. Iterating bytes is
        //    exact for ASCII; a non-ASCII byte (>= 0x80) is by construction not lower-hex
        //    and reports the offset of the first offender.
        for (offset, &b) in tail.as_bytes().iter().enumerate() {
            if !is_lower_hex(b) {
                return Err(IdentityError::NonLowerHex { offset });
            }
        }

        Ok(MicroOid(s.to_owned()))
    }

    /// The validated identity string, exactly as parsed (`mu:` + 64 lowercase hex).
    #[inline]
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }

    /// The 64-char lowercase-hex tail (the bare SHA-256 digest), without the `mu:` prefix.
    #[inline]
    #[must_use]
    pub fn hex(&self) -> &str {
        &self.0[PREFIX.len()..]
    }
}

impl fmt::Display for MicroOid {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl AsRef<str> for MicroOid {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

impl std::str::FromStr for MicroOid {
    type Err = IdentityError;
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        MicroOid::parse(s)
    }
}

/// True iff `s` is a valid greenfield identity `^mu:[0-9a-f]{64}$`.
///
/// A total-ordering-free convenience over [`MicroOid::parse`] for call sites that
/// only need the boolean (e.g. schema-style validation); it shares the exact same
/// rules, so it can never diverge from the typed parser.
#[inline]
#[must_use]
pub fn is_valid_micro_oid(s: &str) -> bool {
    MicroOid::parse(s).is_ok()
}

/// Render a short, ASCII-safe description of the actual prefix for [`IdentityError::BadPrefix`].
/// Never embeds raw non-ASCII bytes (so error text stays printable-ASCII), and names
/// the two Greek mu code points explicitly when seen at the front.
fn describe_prefix(s: &str) -> String {
    if s.is_empty() {
        return "empty string".to_owned();
    }
    match s.chars().next() {
        Some('\u{00B5}') => "U+00B5 MICRO SIGN".to_owned(),
        Some('\u{03BC}') => "U+03BC GREEK SMALL LETTER MU".to_owned(),
        Some(c) if c.is_ascii_graphic() => {
            // Show up to the first 3 ASCII-graphic chars (the prefix window).
            let shown: String = s
                .chars()
                .take_while(|c| c.is_ascii_graphic())
                .take(3)
                .collect();
            format!("{shown:?}")
        }
        Some(c) => format!("U+{:04X}", c as u32),
        None => "empty string".to_owned(),
    }
}
