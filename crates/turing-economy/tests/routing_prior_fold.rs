//! WP4 (`RES_ECON_emergence_toplevel_design_20260707.md` §4 G3 row / §7 WP4; spec source
//! `ADR-ECON-003` Decision 2/6) acceptance tests for the `EconomyEvent::RoutingPriorUpdated`
//! / `RoutingPriorClawback` -> `routing_fold::RoutingFoldEvent` translation.
//!
//! Scope covered (design doc §7 WP4 acceptance predicate, literal):
//! 1. "事件→fold 映射守恒测试" -- translating a tape of `RoutingPriorUpdated`/
//!    `RoutingPriorClawback` events through `economy_events_to_routing_fold_events` and
//!    feeding it to `fold_routing_state` must agree with hand-built `RoutingFoldEvent`s
//!    fed directly (WP4 must not reinvent WP3's fold, only translate into its existing
//!    input contract) -- and folding the identical tape twice must be byte-identical
//!    (Art 0.2 determinism, same convention as `tests/hunt_replay.rs`).
//! 2. "旧 tape 向后兼容读取测试" -- a tape containing only pre-WP4 `EconomyEvent` variants
//!    (the ADR-ECON-001 back-compat convention: no declaration/new-variant present ->
//!    the new machinery is a pure no-op) translates to an empty fold-event list and folds
//!    to an empty node map, never an error.
//! 3. A malformed hash on either new variant is a hard translation error (never silently
//!    dropped/truncated), mirroring WP3's own "never swallow an invalid state" convention.

use std::collections::BTreeMap;

use turing_economy::routing_fold::{
    self, fold_routing_state, fold_routing_state_from_tape, NodeState, RoutingFoldEvent,
    RoutingKey,
};
use turing_economy::{EconomyError, EconomyEvent};

fn updated_event(
    domain: &str,
    scaffold: &str,
    verdict: bool,
    source: &str,
    attestation: &str,
) -> EconomyEvent {
    EconomyEvent::routing_prior_updated(domain, scaffold, verdict, source, attestation)
        .expect("routing_prior_updated constructs on well-formed input")
}

fn updated_payload(event: &EconomyEvent) -> &turing_economy::RoutingPriorUpdated {
    match event {
        EconomyEvent::RoutingPriorUpdated(payload) => payload,
        other => panic!("expected RoutingPriorUpdated, got {other:?}"),
    }
}

/// Scope 1: translation agrees with a hand-built `RoutingFoldEvent` tape, and folding the
/// translated tape through the public `fold_routing_state_from_tape` entry point produces
/// byte-identical `NodeState`s to calling `fold_routing_state` directly on the hand-built
/// equivalent -- i.e. WP4 is a pure relay into WP3's pre-existing seam, not a parallel
/// reimplementation that merely agrees by construction.
#[test]
fn economy_event_translation_agrees_with_hand_built_fold_events() {
    let attestation_a =
        "sha256:1111111111111111111111111111111111111111111111111111111111111111".to_string();
    let attestation_b =
        "sha256:2222222222222222222222222222222222222222222222222222222222222222".to_string();

    let update_1 = updated_event(
        "code_review",
        "scaffold:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        true,
        "verifier:heldout-diff-checker-v1",
        &attestation_a,
    );
    let update_2 = updated_event(
        "code_review",
        "scaffold:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        false,
        "verifier:heldout-diff-checker-v1",
        &attestation_b,
    );
    let update_1_hash = updated_payload(&update_1).event_hash.clone();
    let clawback = EconomyEvent::routing_prior_clawback(update_1_hash.clone())
        .expect("routing_prior_clawback constructs on a well-formed digest");

    let tape = vec![update_1.clone(), update_2.clone(), clawback.clone()];

    // Translate, then fold via the public seam.
    let translated = routing_fold::economy_events_to_routing_fold_events(&tape)
        .expect("translation of a well-formed tape must not error");
    assert_eq!(translated.len(), 3, "every routing-prior event must translate 1:1");

    let via_public_seam =
        fold_routing_state_from_tape(&BTreeMap::new(), &tape).expect("fold_routing_state_from_tape");

    // Hand-built equivalent, calling WP3's fold_routing_state directly (never
    // reimplemented -- same function, same inputs).
    let key = RoutingKey {
        domain_bucket: "code_review".to_string(),
        scaffold_id:
            "scaffold:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                .to_string(),
    };
    let hand_built = vec![
        RoutingFoldEvent::PriorUpdated {
            key: key.clone(),
            verdict: true,
            event_hash: parse_sha256(&update_1_hash),
        },
        RoutingFoldEvent::PriorUpdated {
            key: key.clone(),
            verdict: false,
            event_hash: parse_sha256(&updated_payload(&update_2).event_hash),
        },
        RoutingFoldEvent::Clawback {
            updated_event_hash: parse_sha256(&update_1_hash),
        },
    ];
    assert_eq!(translated, hand_built, "translation must match the hand-built fold-event tape exactly");

    let via_hand_built =
        fold_routing_state(&BTreeMap::new(), &hand_built).expect("fold_routing_state");
    assert_eq!(
        node_state_tuple(via_public_seam.get(&key)),
        node_state_tuple(via_hand_built.get(&key)),
        "fold_routing_state_from_tape must agree byte-for-byte with fold_routing_state \
         called directly on the equivalent hand-built RoutingFoldEvent tape"
    );

    // update_1 (verdict true) was clawed back -> only update_2 (verdict false) remains.
    let (p, n, s) = node_state_tuple(via_public_seam.get(&key)).expect("key present");
    assert_eq!(n, 1, "one PriorUpdated survives the clawback");
    assert_eq!(s, 0, "the surviving update's verdict was false");
    assert_eq!(p, turing_economy::routing_fold::Q32_ONE / 2, "no AMM price supplied -> uninformative P=0.5");

    // Determinism: folding the identical tape twice must be byte-identical (Art 0.2).
    let run_2 =
        fold_routing_state_from_tape(&BTreeMap::new(), &tape).expect("fold_routing_state_from_tape run 2");
    assert_eq!(via_public_seam, run_2, "replaying the identical tape must be byte-identical");
}

/// Scope 2: a tape containing only pre-WP4 `EconomyEvent` variants (no `RoutingPriorUpdated`
/// / `RoutingPriorClawback` present at all -- the exact shape of every tape written before
/// this capsule landed) is a pure no-op through the new translation seam: empty fold-event
/// list, empty node map, never an error. Same back-compat convention as ADR-ECON-001's
/// `PrincipalDeclared` ("无声明时退化为当前 agent_id 行为").
#[test]
fn pre_wp4_tape_translates_and_folds_as_a_pure_no_op() {
    let old_tape = vec![
        EconomyEvent::market_created("mkt_old", "100", "100").expect("market_created"),
        EconomyEvent::position_minted("mkt_old", "agent_old", "10").expect("position_minted"),
        EconomyEvent::principal_declared("principal_old", "agent_old"),
    ];

    let translated = routing_fold::economy_events_to_routing_fold_events(&old_tape)
        .expect("a pre-WP4 tape must translate without error");
    assert!(
        translated.is_empty(),
        "a tape with no RoutingPriorUpdated/RoutingPriorClawback must translate to no fold events"
    );

    let folded =
        fold_routing_state_from_tape(&BTreeMap::new(), &old_tape).expect("fold_routing_state_from_tape");
    assert!(
        folded.is_empty(),
        "a tape with no routing-prior events must fold to an empty node map, not an error"
    );

    // Round-trip through JSON (the tape's actual wire format) to pin that OLD serialized
    // rows (predating this capsule, so they never carry the new fields at all) still
    // deserialize as their original variant unaffected by this capsule's additions.
    let json = serde_json::to_string(&old_tape).expect("serialize old-shaped tape");
    let round_tripped: Vec<EconomyEvent> =
        serde_json::from_str(&json).expect("deserialize old-shaped tape back");
    assert_eq!(old_tape, round_tripped, "old-shaped tape must round-trip byte-for-byte");
}

/// Scope 3: a malformed hash (not `sha256:` + 64 hex) on either new variant is a hard
/// translation error, never silently dropped/truncated/zero-padded.
#[test]
fn malformed_hash_is_a_hard_translation_error_not_swallowed() {
    // routing_prior_updated's own constructor already validates verifier_attestation_hash,
    // so exercise the translation-layer guard via a directly-constructed (bypassing the
    // constructor) malformed payload -- this simulates a forged/corrupted tape row, the
    // untrusted-input posture this crate's other hunt_* suites use throughout.
    let forged = EconomyEvent::RoutingPriorUpdated(turing_economy::RoutingPriorUpdated {
        schema_id: "routing_prior_updated.v1".to_string(),
        event_type: "RoutingPriorUpdated".to_string(),
        head_effect: "PRESERVE".to_string(),
        route_domain: "code_review".to_string(),
        route_scaffold: "scaffold:sha256:deadbeef".to_string(),
        verdict: true,
        verdict_source_id: "verifier:x".to_string(),
        verifier_attestation_hash:
            "sha256:3333333333333333333333333333333333333333333333333333333333333333".to_string(),
        event_hash: "not-a-valid-hash".to_string(),
    });
    let result = routing_fold::economy_event_to_routing_fold_event(&forged);
    assert_eq!(result, Err(EconomyError::RoutingFoldMalformedEventHash));

    let forged_clawback = EconomyEvent::RoutingPriorClawback(turing_economy::RoutingPriorClawback {
        schema_id: "routing_prior_clawback.v1".to_string(),
        event_type: "RoutingPriorClawback".to_string(),
        head_effect: "PRESERVE".to_string(),
        updated_event_hash: "sha256:tooshort".to_string(),
    });
    let result = routing_fold::economy_event_to_routing_fold_event(&forged_clawback);
    assert_eq!(result, Err(EconomyError::RoutingFoldMalformedEventHash));
}

/// Fix-regression: `parse_event_hash` must reject `+`-signed and uppercase hex aliases.
/// `u8::from_str_radix` alone is lenient (`"+f"` parses as 15; `"AB"`/`"ab"` parse to the
/// same byte), so without a strict `[0-9a-f]` alphabet check two differently-spelled hash
/// strings would alias to one clawback-dedup identity. Exercised through the clawback
/// variant (whose hash is a pure reference, with no recompute-from-fields cross-check).
#[test]
fn parse_event_hash_rejects_signed_and_uppercase_hex_aliases() {
    let signed = format!("sha256:+f{}", "ab".repeat(31)); // 64 chars, "+f" leads
    let uppercase = format!("sha256:{}", "AB".repeat(32)); // 64 chars, uppercase hex
    let mixed_case = format!("sha256:{}{}", "Ab".repeat(16), "ab".repeat(16));
    for bad_hash in [signed, uppercase, mixed_case] {
        let forged_clawback =
            EconomyEvent::RoutingPriorClawback(turing_economy::RoutingPriorClawback {
                schema_id: "routing_prior_clawback.v1".to_string(),
                event_type: "RoutingPriorClawback".to_string(),
                head_effect: "PRESERVE".to_string(),
                updated_event_hash: bad_hash.clone(),
            });
        assert_eq!(
            routing_fold::economy_event_to_routing_fold_event(&forged_clawback),
            Err(EconomyError::RoutingFoldMalformedEventHash),
            "hash spelling {bad_hash:?} must be rejected, not leniently parsed"
        );
    }

    // The exact lowercase spelling of the same bytes remains parseable (referencing an
    // unknown target is then the fold's problem, not the parser's) -- only the alias
    // spellings are newly rejected.
    let lowercase = format!("sha256:{}", "ab".repeat(32));
    let legit_clawback = EconomyEvent::routing_prior_clawback(lowercase).expect("constructs");
    assert!(routing_fold::economy_event_to_routing_fold_event(&legit_clawback).is_ok());
}

/// Fix-regression (tape-integrity guard): the translation layer must never trust a
/// deserialized `RoutingPriorUpdated.event_hash` field -- it re-derives the identity digest
/// from the event's own fields and hard-errors on mismatch. A constructor-built event (the
/// only kind this codebase ever writes, incl. via `econ_fold_cli build-routing-prior-updated`)
/// still translates fine.
#[test]
fn tampered_event_hash_is_rejected_and_constructor_built_event_still_translates() {
    let legit = updated_event(
        "code_review",
        "scaffold:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        true,
        "verifier:heldout-diff-checker-v1",
        "sha256:4444444444444444444444444444444444444444444444444444444444444444",
    );
    // Legit path: constructor-minted event_hash matches the re-derivation -> Ok(Some(..)).
    let translated = routing_fold::economy_event_to_routing_fold_event(&legit)
        .expect("constructor-built event must translate");
    assert!(translated.is_some(), "RoutingPriorUpdated must map to a fold event");

    // Tampered path: same event, but the event_hash field is swapped for a *well-formed*
    // (correct format, wrong value) digest -- e.g. an attacker re-pointing dedup identity.
    let mut tampered_payload = updated_payload(&legit).clone();
    tampered_payload.event_hash = format!("sha256:{}", "ab".repeat(32));
    let tampered = EconomyEvent::RoutingPriorUpdated(tampered_payload);
    assert_eq!(
        routing_fold::economy_event_to_routing_fold_event(&tampered),
        Err(EconomyError::RoutingFoldEventHashMismatch),
        "a tampered event_hash must be a hard error, never folded"
    );

    // A tampered *field* (verdict flip) with the original hash is the same forgery seen
    // from the other side: the recomputed digest no longer matches the carried hash.
    let mut flipped_payload = updated_payload(&legit).clone();
    flipped_payload.verdict = false;
    let flipped = EconomyEvent::RoutingPriorUpdated(flipped_payload);
    assert_eq!(
        routing_fold::economy_event_to_routing_fold_event(&flipped),
        Err(EconomyError::RoutingFoldEventHashMismatch),
        "a verdict flip under the original hash must be a hard error, never folded"
    );
}

fn parse_sha256(value: &str) -> [u8; 32] {
    let hex = value.strip_prefix("sha256:").expect("sha256: prefix");
    let mut bytes = [0u8; 32];
    for (i, byte) in bytes.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&hex[i * 2..i * 2 + 2], 16).expect("valid hex byte");
    }
    bytes
}

fn node_state_tuple(node: Option<&NodeState>) -> Option<(i128, u64, u64)> {
    node.map(|n| (n.p_q32(), n.n(), n.s()))
}
