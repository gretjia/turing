//! WP5 (design doc R1.1 §7; ADR-ECON-003 Decision 5 A-zone): acceptance test that the
//! `diversity_policy_hash` carried on every `BudgetSuggestion` is the real SHA-256 digest
//! of the committed public diversity policy document, not the previous all-zero
//! placeholder.
//!
//! Independence from the library's own `include_str!` embedding: this test re-reads the
//! policy document from disk at test-run time (via `CARGO_MANIFEST_DIR`, the standard
//! Cargo-provided path to the crate root) and hashes it itself, rather than merely calling
//! `turing_economy::diversity_policy_hash()` and comparing it to itself -- a tautology
//! would prove nothing. This gives two independently-arrived-at digests that must agree.

use std::path::PathBuf;

use sha2::{Digest, Sha256};
use turing_economy::{
    BudgetSuggestion, CandidateRoute, MarketRouter, MarketRouterMode, PriceSignal,
};

/// Repo-relative path to the WP5 public diversity policy document (design doc §7 WP5;
/// ADR-ECON-003 Decision 5 A-zone artifact). Same path `lib.rs`'s `include_str!` embeds.
const POLICY_DOCUMENT_RELATIVE_PATH: &str = "../../docs/policy/DIVERSITY-POLICY-v1.md";

fn expected_hash_from_disk() -> String {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let path = manifest_dir.join(POLICY_DOCUMENT_RELATIVE_PATH);
    let bytes = std::fs::read(&path)
        .unwrap_or_else(|e| panic!("diversity policy document must exist at {path:?}: {e}"));
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    format!("sha256:{:x}", hasher.finalize())
}

#[test]
fn diversity_policy_hash_matches_committed_public_policy_document_sha256() {
    let expected = expected_hash_from_disk();

    // Sanity: not the old all-zero placeholder, and syntactically a real digest.
    assert_ne!(
        expected,
        "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "the policy document itself must not hash to the placeholder value"
    );
    assert_eq!(expected.len(), "sha256:".len() + 64);
    assert!(
        expected["sha256:".len()..]
            .bytes()
            .all(|b| b.is_ascii_hexdigit()),
        "expected hash must be 64 lowercase-hex characters after the sha256: prefix"
    );

    assert_eq!(
        turing_economy::diversity_policy_hash(),
        expected,
        "library's diversity_policy_hash() must equal an independently-computed sha256 of \
         the on-disk policy document"
    );
}

#[test]
fn budget_suggestion_carries_the_real_policy_hash_not_the_old_placeholder() {
    let expected = expected_hash_from_disk();

    let routes = vec![CandidateRoute {
        route_id: "route_only".to_string(),
        market_id: "mkt_demo".to_string(),
        expected_failure_domain: "provider_a".to_string(),
        requested_tokens: 500,
    }];
    let signals = vec![PriceSignal {
        market_id: "mkt_demo".to_string(),
        yes_price: "0.5".to_string(),
        no_price: "0.5".to_string(),
        truth_status: "statistical_signal_only".to_string(),
    }];

    let suggestion: BudgetSuggestion = MarketRouter::new(MarketRouterMode::Shadow)
        .suggest(
            &routes,
            &signals,
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        .expect("suggest must succeed");

    assert_eq!(
        suggestion.diversity_policy_hash, expected,
        "BudgetSuggestion.diversity_policy_hash must equal the public policy document's real \
         sha256, not the retired all-zero placeholder"
    );
}
