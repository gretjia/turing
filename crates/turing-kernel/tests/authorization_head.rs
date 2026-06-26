//! SG-15 — "Authorization ref law" (`cargo nextest run -p turing-kernel --test authorization_head`).
//!
//! The frozen law (`event_registry_v5_3_1.json:44-51`, greenfield spec §5.3, append algo
//! INV-3): a candidate transition advances `authorization_head` **iff**
//! `class == AUTHORIZATION ∧ head_effect == ADVANCE ∧ predicate_product == PASS`. For ANY
//! other class, or for a FAIL / NOT_RUN product, `authorization_head` is carried forward
//! byte-unchanged. `tape_tip` ALWAYS advances; at most one sovereign head moves.
//!
//! This is a LAW-VERIFICATION gate over the pure reducer ([`turing_kernel::reducer::apply`],
//! established at SG-12). The test is **exhaustive and adversarial over the REAL registry**:
//! it iterates ALL 46 canonical event names loaded from the ratified
//! `pack/04_registries/event_registry_v5_3_1.json` (via the public contracts registry API —
//! NOT a hand-typed list), and for each event, from a non-trivial pre-state
//! (`authorization_head = Some(A)`, `accepted_head = Some(B)`), asserts:
//!
//!   * product = PASS  → `authorization_head` advances to the new OID **IFF** the registry
//!     class is AUTHORIZATION (∧ the registry head_effect is ADVANCE); for every one of the
//!     38 non-AUTHORIZATION events it stays == A. For the 8 AUTHORIZATION events the OTHER
//!     head (`accepted_head`) stays == B — at most one sovereign head moves.
//!   * product = FAIL and product = NOT_RUN → `authorization_head` NEVER advances (stays
//!     == A), even for the 8 AUTHORIZATION events.
//!
//! and finally counts that EXACTLY 8 events advance `authorization_head` under PASS and that
//! they are EXACTLY the AUTHORIZATION class. The registry head_effect is the registry-derived
//! truth (never writer-asserted) — the test feeds `registry(name).head_effect` straight into
//! the reducer, so a reducer that ignored class, or keyed off the wrong head, or honoured
//! FAIL/NOT_RUN, would fail here. Public crate API only; no `assert!(true)`.

use turing_contracts::envelope::{HeadEffect, PredicateProduct};
use turing_contracts::registry::{self, EventClass, TargetRef};

use turing_kernel::reducer::{self, HeadMoved, PreState};

// --- fixtures ----------------------------------------------------------------

/// `mu:` + 64 hex helper for a deterministic, distinct OID (one byte repeated 32×).
fn mu(byte: u8) -> String {
    format!("mu:{}", format!("{byte:02x}").repeat(32))
}

/// Pre-state head `A` (`authorization_head`).
fn head_a() -> String {
    mu(0xaa)
}

/// Pre-state head `B` (`accepted_head`).
fn head_b() -> String {
    mu(0xbb)
}

/// The minted OID Git would assign the new event commit — distinct from BOTH heads, so a
/// spurious advance is observable (the moved head would become `N`, not stay `A`/`B`).
fn new_event_oid() -> String {
    mu(0xcc)
}

/// A non-trivial pre-state with DISTINCT sovereign heads:
/// `tape_tip = T`, `authorization_head = A`, `accepted_head = B`, epoch 7, parent seq 41.
/// Distinct values make a wrong-head advance, or a stale carry-forward, byte-detectable.
fn nontrivial_pre() -> PreState {
    PreState {
        tape_tip: Some(mu(0x11)), // T
        authorization_head: Some(head_a()),
        accepted_head: Some(head_b()),
        authority_epoch: 7,
        parent_sequence: Some(41),
    }
}

/// Every product variant — the law must hold across ALL of them, not just PASS.
const ALL_PRODUCTS: [PredicateProduct; 3] = [
    PredicateProduct::Pass,
    PredicateProduct::Fail,
    PredicateProduct::NotRun,
];

// --- the exhaustive registry-derived law check -------------------------------

#[test]
fn only_authorization_advance_pass_advances_authorization_head_over_all_46_events() {
    let pre = nontrivial_pre();
    let a = head_a();
    let b = head_b();
    let n = new_event_oid();

    // Bind the REAL registry: iterate ALL 46 canonical names from the ratified pack
    // (registry-derived, never a hand-typed list). Guard the count so a shrunk/grown
    // registry can't silently make this vacuous.
    let names: Vec<String> = registry::event_names().map(str::to_owned).collect();
    assert_eq!(
        names.len(),
        46,
        "the exhaustive sweep must cover the full closed 46-event registry"
    );
    assert_eq!(
        names.len(),
        registry::registered_event_count(),
        "event_names() must enumerate exactly the registered set"
    );

    // Tally of events that advance authorization_head under PASS — must end at exactly 8,
    // and that set must be exactly the AUTHORIZATION class.
    let mut advancing_under_pass: Vec<String> = Vec::new();

    for name in &names {
        let row =
            registry::registry(name).expect("every enumerated name resolves to a registry row");
        let class = row.class;
        // The registry-derived head_effect — the ONLY trustworthy source (never writer-set).
        let head_effect = row.head_effect;

        let is_authorization = class == EventClass::Authorization;
        // Sanity-bind the registry's own internal consistency: AUTHORIZATION ⇔ ADVANCE to
        // authorization_head; nothing else targets authorization_head.
        if is_authorization {
            assert_eq!(
                head_effect,
                HeadEffect::Advance,
                "{name}: an AUTHORIZATION event must carry registry head_effect ADVANCE"
            );
            assert_eq!(
                row.target_ref,
                TargetRef::AuthorizationHead,
                "{name}: an AUTHORIZATION event must target authorization_head"
            );
        } else {
            assert_ne!(
                row.target_ref,
                TargetRef::AuthorizationHead,
                "{name}: only AUTHORIZATION may target authorization_head"
            );
        }

        for product in ALL_PRODUCTS {
            let decision = reducer::apply(&pre, class, head_effect, product, &n);

            // tape_tip ALWAYS advances to the new event OID — for every class & product.
            assert_eq!(
                decision.tape_tip, n,
                "{name}/{product:?}: tape_tip must always advance to the new event OID"
            );
            // The reducer never invents an authority-epoch change (SG-17 owns that).
            assert_eq!(
                decision.authority_epoch, pre.authority_epoch,
                "{name}/{product:?}: authority_epoch carries forward in the reducer"
            );

            // The law: authorization_head advances IFF AUTHORIZATION ∧ ADVANCE ∧ PASS.
            let should_advance_auth = is_authorization
                && head_effect == HeadEffect::Advance
                && product == PredicateProduct::Pass;

            if should_advance_auth {
                assert_eq!(
                    decision.authorization_head.as_deref(),
                    Some(n.as_str()),
                    "{name}/{product:?}: AUTHORIZATION+ADVANCE+PASS MUST advance authorization_head \
                     to the new OID"
                );
                assert_eq!(
                    decision.head_moved,
                    HeadMoved::AuthorizationHead,
                    "{name}/{product:?}: the moved head must be reported as AuthorizationHead"
                );
                // At most one head moves: accepted_head stays == B for these.
                assert_eq!(
                    decision.accepted_head.as_deref(),
                    Some(b.as_str()),
                    "{name}/{product:?}: accepted_head B must NOT move when authorization_head does"
                );
            } else {
                // authorization_head is carried forward byte-unchanged (still A).
                assert_eq!(
                    decision.authorization_head.as_deref(),
                    Some(a.as_str()),
                    "{name}/{product:?}: authorization_head MUST stay == A (no advance) unless \
                     AUTHORIZATION+ADVANCE+PASS"
                );
                // And specifically it must NOT have become the new event OID.
                assert_ne!(
                    decision.authorization_head.as_deref(),
                    Some(n.as_str()),
                    "{name}/{product:?}: authorization_head must NOT advance to the new OID here"
                );
                // The reducer must not claim authorization_head moved.
                assert_ne!(
                    decision.head_moved,
                    HeadMoved::AuthorizationHead,
                    "{name}/{product:?}: head_moved must not be AuthorizationHead here"
                );
            }

            if product == PredicateProduct::Pass && should_advance_auth {
                advancing_under_pass.push(name.to_string());
            }
        }
    }

    // EXACTLY 8 events advance authorization_head under PASS — and they are EXACTLY the
    // AUTHORIZATION class (verified two ways: count, and that each is AUTHORIZATION).
    assert_eq!(
        advancing_under_pass.len(),
        8,
        "exactly 8 events may advance authorization_head under PASS (the AUTHORIZATION class), \
         got: {advancing_under_pass:?}"
    );
    for name in &advancing_under_pass {
        assert_eq!(
            registry::registry(name).unwrap().class,
            EventClass::Authorization,
            "{name} advanced authorization_head but is not AUTHORIZATION class"
        );
    }
    // The advancing set IS the AUTHORIZATION set: every AUTHORIZATION event is present, and
    // no non-AUTHORIZATION event is (count 8 + all-AUTHORIZATION above ⇒ set equality).
    let authorization_names: Vec<&String> = names
        .iter()
        .filter(|nm| registry::registry(nm).unwrap().class == EventClass::Authorization)
        .collect();
    assert_eq!(
        authorization_names.len(),
        8,
        "the registry must declare exactly 8 AUTHORIZATION events"
    );
    for nm in &authorization_names {
        assert!(
            advancing_under_pass.contains(nm),
            "AUTHORIZATION event {nm} must advance authorization_head under PASS"
        );
    }
}

// --- focused adversarial cases: FAIL / NOT_RUN never advance even AUTHORIZATION ----

#[test]
fn authorization_event_under_fail_or_not_run_never_advances_authorization_head() {
    let pre = nontrivial_pre();
    let a = head_a();
    let n = new_event_oid();

    // Walk EVERY AUTHORIZATION event (registry-derived) and prove FAIL / NOT_RUN are inert
    // on authorization_head — only a PASS may move it.
    let auth_names: Vec<String> = registry::event_names()
        .filter(|nm| registry::registry(nm).unwrap().class == EventClass::Authorization)
        .map(str::to_owned)
        .collect();
    assert_eq!(auth_names.len(), 8, "8 AUTHORIZATION events expected");

    for name in &auth_names {
        let row = registry::registry(name).unwrap();
        for product in [PredicateProduct::Fail, PredicateProduct::NotRun] {
            let decision = reducer::apply(&pre, row.class, row.head_effect, product, &n);
            assert_eq!(
                decision.authorization_head.as_deref(),
                Some(a.as_str()),
                "{name}/{product:?}: a non-PASS AUTHORIZATION event must NOT advance \
                 authorization_head"
            );
            assert_eq!(
                decision.head_moved,
                HeadMoved::None,
                "{name}/{product:?}: a non-PASS AUTHORIZATION event moves no sovereign head"
            );
            assert_eq!(
                decision.tape_tip, n,
                "{name}/{product:?}: tape_tip still advances"
            );
        }

        // Positive control on the SAME event: PASS DOES advance it (proves the FAIL/NOT_RUN
        // inertness above is the product gate, not a dead event).
        let pass = reducer::apply(&pre, row.class, row.head_effect, PredicateProduct::Pass, &n);
        assert_eq!(
            pass.authorization_head.as_deref(),
            Some(n.as_str()),
            "{name}: PASS must advance authorization_head (positive control)"
        );
        assert_eq!(pass.head_moved, HeadMoved::AuthorizationHead);
    }
}

// --- focused adversarial case: a SOVEREIGN_ACCEPT PASS moves accepted_head, NOT auth ----

#[test]
fn sovereign_accept_pass_moves_accepted_head_and_leaves_authorization_head_untouched() {
    let pre = nontrivial_pre();
    let a = head_a();
    let n = new_event_oid();

    // CandidateAccepted is a SOVEREIGN_ACCEPT (ADVANCE → accepted_head). Under PASS it must
    // move accepted_head and leave authorization_head == A. This is the adjacent-law guard:
    // SG-15 must NOT advance authorization_head for the OTHER advancing class.
    let row = registry::registry("CandidateAccepted").expect("CandidateAccepted is registered");
    assert_eq!(row.class, EventClass::SovereignAccept);
    assert_eq!(row.head_effect, HeadEffect::Advance);

    let decision = reducer::apply(&pre, row.class, row.head_effect, PredicateProduct::Pass, &n);
    assert_eq!(
        decision.authorization_head.as_deref(),
        Some(a.as_str()),
        "a SOVEREIGN_ACCEPT PASS must leave authorization_head == A"
    );
    assert_eq!(
        decision.accepted_head.as_deref(),
        Some(n.as_str()),
        "a SOVEREIGN_ACCEPT PASS moves accepted_head to the new OID"
    );
    assert_eq!(decision.head_moved, HeadMoved::AcceptedHead);
}
