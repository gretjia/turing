//! SG-11 — Identity profile (greenfield `MicroOid`).
//!
//! Binds the ratified greenfield identity rule (ADR-007 §3-4,
//! `capability_grant.v1.schema.json` `$defs.microOid`, `execd_verification_v5_3_1.md`
//! §1/§6): a governed identity is EXACTLY `^mu:[0-9a-f]{64}$` — the ASCII `mu:`
//! literal (bytes 0x6D 0x75 0x3A) followed by exactly 64 LOWERCASE hex chars.
//!
//! Greek `μ:` (U+00B5 MICRO SIGN and/or U+03BC GREEK SMALL LETTER MU), 40-hex
//! (SHA-1 length) identities, uppercase hex, and every other malformed shape are
//! REJECTED in greenfield mode — the default and only-enabled validator path
//! (`execd_verification_v5_3_1.md:17` "Greek `μ:`, 40-hex OIDs ... are invalid in
//! the greenfield grant path"; the conformance matrix line "Greek identity;
//! 40-hex identity", §6).
//!
//! Anti-Goodhart: this test calls only the PUBLIC crate API
//! (`turing_contracts::identity::{MicroOid, IdentityError, is_valid_micro_oid}`).
//! It is table-driven over a thorough positive set (each MUST accept) and a
//! thorough negative set (each MUST reject) — no `assert!(true)` filler, and no
//! reject case is allowed to slip through as accepted. Where a reject reason is
//! structurally distinguishable, the precise `IdentityError` variant is asserted.

use turing_contracts::identity::{IdentityError, MicroOid, is_valid_micro_oid};

/// A valid greenfield identity: `mu:` + 64 lowercase hex.
const ALL_ZEROS: &str = "mu:0000000000000000000000000000000000000000000000000000000000000000";
/// 64 lowercase-hex chars mixing 0-9 and a-f (the SG-10 content_digest hex).
const MIXED_64: &str = "mu:317d70bd958db75dee5483853f5d699445f8d3f9fa2f1c8f05e673a3c2a6062a";
/// Another mixed 0-9a-f 64-hex (the SG-10 goal_digest hex).
const MIXED_64_B: &str = "mu:9a549a898e94716e8ca179be48722fce96678251d62d4c06754225485d5c14bd";
/// All `f` (max nibble) — boundary of the lowercase-hex class.
const ALL_F: &str = "mu:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";
/// Every lowercase-hex digit exercised, length exactly 64.
const ALL_DIGITS: &str = "mu:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

/// POSITIVE cases — each MUST be accepted by both the parser and the predicate.
fn positive_cases() -> Vec<(&'static str, &'static str)> {
    vec![
        ("all_zeros", ALL_ZEROS),
        ("mixed_0-9a-f (content_digest)", MIXED_64),
        ("mixed_0-9a-f (goal_digest)", MIXED_64_B),
        ("all_f", ALL_F),
        ("every_lowercase_hex_digit", ALL_DIGITS),
    ]
}

/// The 64-hex tail reused to build well-formed-tail negative prefixes.
const TAIL_64: &str = "317d70bd958db75dee5483853f5d699445f8d3f9fa2f1c8f05e673a3c2a6062a";
/// A 40-hex (SHA-1 length) tail — the legacy length that greenfield rejects.
const TAIL_40: &str = "0123456789abcdef0123456789abcdef01234567";

/// Which reject family a negative case is expected to land in. `Any` means the
/// case is unambiguously invalid but the implementation MAY classify it under
/// more than one structurally-defensible variant (we still require it to REJECT,
/// just not a single fixed variant).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Reject {
    BadPrefix,
    BadLength,
    NonLowerHex,
    Any,
}

/// NEGATIVE cases — each MUST be rejected. Built lazily because two entries embed
/// non-ASCII (Greek) prefixes that are clearer as owned `String`s.
fn negative_cases() -> Vec<(String, String, Reject)> {
    let mut v: Vec<(String, String, Reject)> = Vec::new();

    // --- Greek μ: prefix — BOTH Unicode forms must reject (ADR-007 §4). ---
    // U+00B5 MICRO SIGN + 'u' + ':' + 64-hex.
    v.push((
        "greek_micro_sign_U+00B5".into(),
        format!("\u{00B5}u:{TAIL_64}"),
        Reject::BadPrefix,
    ));
    // U+03BC GREEK SMALL LETTER MU + 'u' + ':' + 64-hex.
    v.push((
        "greek_small_mu_U+03BC".into(),
        format!("\u{03BC}u:{TAIL_64}"),
        Reject::BadPrefix,
    ));
    // U+00B5 as a single-glyph prefix immediately followed by ':' (no ASCII 'm'/'u').
    v.push((
        "greek_micro_sign_glyph_colon_U+00B5".into(),
        format!("\u{00B5}:{TAIL_64}"),
        Reject::BadPrefix,
    ));
    // U+03BC as a single-glyph prefix immediately followed by ':'.
    v.push((
        "greek_small_mu_glyph_colon_U+03BC".into(),
        format!("\u{03BC}:{TAIL_64}"),
        Reject::BadPrefix,
    ));

    // --- 40-hex (SHA-1 length) even WITH a correct ASCII mu: prefix. ---
    v.push((
        "mu_prefix_40_hex_sha1_length".into(),
        format!("mu:{TAIL_40}"),
        Reject::BadLength,
    ));

    // --- Uppercase / mixed-case hex (pattern is [0-9a-f] lowercase only). ---
    v.push((
        "uppercase_hex_all".into(),
        format!("mu:{}", TAIL_64.to_uppercase()),
        Reject::NonLowerHex,
    ));
    v.push((
        "uppercase_hex_single_char".into(),
        // Flip exactly one nibble to uppercase 'A'.
        "mu:A17d70bd958db75dee5483853f5d699445f8d3f9fa2f1c8f05e673a3c2a6062a".into(),
        Reject::NonLowerHex,
    ));

    // --- Wrong length (63, 65, 0 hex chars) with a correct prefix. ---
    v.push((
        "len_63_one_short".into(),
        format!("mu:{}", &TAIL_64[..63]),
        Reject::BadLength,
    ));
    v.push((
        "len_65_one_long".into(),
        format!("mu:{TAIL_64}a"),
        Reject::BadLength,
    ));
    v.push(("len_0_prefix_only".into(), "mu:".into(), Reject::BadLength));

    // --- Non-hex characters inside an otherwise 64-long, lowercase tail. ---
    // 'g' is past 'f' (not a hex digit).
    v.push((
        "non_hex_g".into(),
        format!("mu:g{}", &TAIL_64[1..]),
        Reject::NonLowerHex,
    ));
    // 'z' non-hex.
    v.push((
        "non_hex_z".into(),
        format!("mu:{}z", &TAIL_64[..63]),
        Reject::NonLowerHex,
    ));
    // Embedded ASCII space inside the tail (length stays 64).
    v.push((
        "non_hex_embedded_space".into(),
        format!("mu:{} {}", &TAIL_64[..31], &TAIL_64[32..]),
        Reject::NonLowerHex,
    ));

    // --- Missing / wrong prefix. ---
    // No prefix at all — bare 64-hex.
    v.push((
        "missing_prefix_bare_64hex".into(),
        TAIL_64.into(),
        Reject::BadPrefix,
    ));
    // sha256: prefix (a sibling digest form, NOT a MicroOid).
    v.push((
        "wrong_prefix_sha256".into(),
        format!("sha256:{TAIL_64}"),
        Reject::Any,
    ));
    // Just 'm' (missing the 'u') + ':'.
    v.push((
        "prefix_m_colon_only".into(),
        format!("m:{TAIL_64}"),
        Reject::Any,
    ));
    // 'mu' present but NO colon separator.
    v.push((
        "prefix_mu_no_colon".into(),
        format!("mu{TAIL_64}"),
        Reject::Any,
    ));
    // Uppercase prefix 'MU:'.
    v.push((
        "uppercase_prefix_MU".into(),
        format!("MU:{TAIL_64}"),
        Reject::BadPrefix,
    ));
    // Leading whitespace before the prefix.
    v.push((
        "leading_space_before_prefix".into(),
        format!(" mu:{TAIL_64}"),
        Reject::BadPrefix,
    ));

    // --- Extra leading / trailing data around an otherwise-valid identity. ---
    // Trailing space after a full valid identity.
    v.push((
        "trailing_space".into(),
        format!("mu:{TAIL_64} "),
        Reject::Any,
    ));
    // Trailing newline (embedded framing) after a full valid identity.
    v.push((
        "trailing_newline".into(),
        format!("mu:{TAIL_64}\n"),
        Reject::Any,
    ));
    // Embedded newline in the middle of the tail (length still 64 visible hex + \n).
    v.push((
        "embedded_newline_mid_tail".into(),
        format!("mu:{}\n{}", &TAIL_64[..31], &TAIL_64[31..]),
        Reject::Any,
    ));
    // Leading junk then a valid-looking identity.
    v.push((
        "extra_leading_data".into(),
        format!("xmu:{TAIL_64}"),
        Reject::BadPrefix,
    ));

    // --- Degenerate empties. ---
    v.push(("empty_string".into(), String::new(), Reject::Any));

    v
}

#[test]
fn positives_accept_via_parse_and_predicate() {
    for (name, s) in positive_cases() {
        // Predicate API: must be true.
        assert!(
            is_valid_micro_oid(s),
            "POSITIVE `{name}` ({s:?}) must satisfy is_valid_micro_oid"
        );
        // Parser API: must be Ok and round-trip to the exact same canonical string.
        let parsed = MicroOid::parse(s)
            .unwrap_or_else(|e| panic!("POSITIVE `{name}` ({s:?}) must parse Ok, got Err({e:?})"));
        assert_eq!(
            parsed.as_str(),
            s,
            "POSITIVE `{name}`: as_str() must round-trip the input verbatim"
        );
    }
}

#[test]
fn negatives_reject_via_parse_and_predicate() {
    for (name, s, expected) in negative_cases() {
        // Predicate API: must be false — no reject case may slip through as accepted.
        assert!(
            !is_valid_micro_oid(&s),
            "NEGATIVE `{name}` ({s:?}) MUST be rejected by is_valid_micro_oid, but it accepted"
        );
        // Parser API: must be Err.
        let err = match MicroOid::parse(&s) {
            Ok(ok) => panic!(
                "NEGATIVE `{name}` ({s:?}) MUST reject, but MicroOid::parse accepted {:?}",
                ok.as_str()
            ),
            Err(e) => e,
        };
        // Where the reject reason is structurally unambiguous, bind the variant so a
        // future weakening that mis-routes (or universally collapses) the reason fails.
        match expected {
            Reject::BadPrefix => assert!(
                matches!(err, IdentityError::BadPrefix { .. }),
                "NEGATIVE `{name}` ({s:?}) expected IdentityError::BadPrefix, got {err:?}"
            ),
            Reject::BadLength => assert!(
                matches!(err, IdentityError::BadLength { .. }),
                "NEGATIVE `{name}` ({s:?}) expected IdentityError::BadLength, got {err:?}"
            ),
            Reject::NonLowerHex => assert!(
                matches!(err, IdentityError::NonLowerHex { .. }),
                "NEGATIVE `{name}` ({s:?}) expected IdentityError::NonLowerHex, got {err:?}"
            ),
            // Unambiguously invalid but variant left to the implementation's discretion;
            // the REJECT (Err above) is the binding assertion.
            Reject::Any => {}
        }
    }
}

/// Greenfield mode is the default and only-enabled path: there is no runtime flag,
/// and a 40-hex identity is rejected exactly like any other malformed shape. This
/// pins the ADR-007 §4 rule that any legacy 40-hex decoder is default-off and NOT
/// accepted by the greenfield validator.
#[test]
fn greenfield_is_default_and_rejects_legacy_40_hex() {
    let legacy_40 = format!("mu:{TAIL_40}");
    assert_eq!(legacy_40.len(), 3 + 40, "fixture sanity: mu: + 40 hex");
    assert!(
        !is_valid_micro_oid(&legacy_40),
        "greenfield default path must reject the legacy 40-hex (SHA-1) identity"
    );
    assert!(matches!(
        MicroOid::parse(&legacy_40),
        Err(IdentityError::BadLength { .. })
    ));
}

/// The ASCII `mu:` prefix is byte-exact: 0x6D ('m') 0x75 ('u') 0x3A (':'). Confirm the
/// accepted fixtures truly begin with those three bytes (guards against a Unicode
/// homoglyph silently masquerading as the prefix in the positive set).
#[test]
fn accepted_prefix_is_byte_exact_ascii_mu_colon() {
    for (name, s) in positive_cases() {
        let bytes = s.as_bytes();
        assert!(
            bytes.len() >= 3 && bytes[0] == 0x6D && bytes[1] == 0x75 && bytes[2] == 0x3A,
            "POSITIVE `{name}` ({s:?}) must start with ASCII bytes 0x6D 0x75 0x3A"
        );
        // Total byte length is exactly 3 (prefix) + 64 (hex) = 67 for every positive.
        assert_eq!(
            bytes.len(),
            67,
            "POSITIVE `{name}` must be exactly 67 bytes (mu: + 64 hex)"
        );
    }
}
