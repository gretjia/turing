//! SG-16 — "Accepted ref law" (`cargo nextest run -p turing-kernel --test accepted_head`).
//!
//! The frozen law (`event_registry_v5_3_1.json:23-154`, greenfield spec §5.3, append algo
//! INV-3): a candidate transition advances `accepted_head` **iff**
//! `class == SOVEREIGN_ACCEPT ∧ head_effect == ADVANCE ∧ predicate_product == PASS`. For ANY
//! other class, or for a FAIL / NOT_RUN product, `accepted_head` is carried forward
//! byte-unchanged. `tape_tip` ALWAYS advances; at most one sovereign head moves.
//!
//! This is the `accepted_head` sibling of SG-15's `authorization_head` law verification, run
//! over the same pure reducer ([`turing_kernel::reducer::apply`], established at SG-12). The
//! test is **exhaustive and adversarial over the REAL registry**: it iterates ALL 46 canonical
//! event names loaded from the ratified `pack/04_registries/event_registry_v5_3_1.json` (via
//! the public contracts registry API — NOT a hand-typed list), and for each event, from a
//! non-trivial pre-state (`authorization_head = Some(A)`, `accepted_head = Some(B)`), asserts:
//!
//!   * product = PASS  → `accepted_head` advances to the new OID **IFF** the registry class is
//!     SOVEREIGN_ACCEPT (∧ the registry head_effect is ADVANCE) — exactly the 12; for every one
//!     of the other 34 events it stays == B. For the 12 SOVEREIGN_ACCEPT events the OTHER head
//!     (`authorization_head`) stays == A — at most one sovereign head moves; head_moved ==
//!     AcceptedHead.
//!   * product = FAIL and product = NOT_RUN → `accepted_head` NEVER advances (stays == B), even
//!     for the 12 SOVEREIGN_ACCEPT events; head_moved == None.
//!
//! and finally counts that EXACTLY 12 events advance `accepted_head` under PASS and that they
//! are EXACTLY the SOVEREIGN_ACCEPT class (both directions of set equality). The registry
//! head_effect is the registry-derived truth (never writer-asserted) — the test feeds
//! `registry(name).head_effect` straight into the reducer, so a reducer that ignored class, or
//! keyed off the wrong head, or honoured FAIL/NOT_RUN, would fail here. Distinct OIDs
//! (A/B/new) make a wrong-head advance or a stale carry-forward byte-detectable. Public crate
//! API only; no `assert!(true)`; the real registry is bound.

use turing_contracts::envelope::{HeadEffect, PredicateProduct};
use turing_contracts::registry::{self, EventClass, TargetRef};

use turing_kernel::reducer::{self, HeadMoved, PreState};

// --- fixtures ----------------------------------------------------------------

/// `mu:` + 64 hex helper for a deterministic, distinct OID (one byte repeated 32×).
fn mu(byte: u8) -> String {
    format!("mu:{}", format!("{byte:02x}").repeat(32))
}

/// Pre-state head `A` (`authorization_head`) — must NOT move when `accepted_head` does.
fn head_a() -> String {
    mu(0xaa)
}

/// Pre-state head `B` (`accepted_head`) — the head under test.
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
fn only_sovereign_accept_advance_pass_advances_accepted_head_over_all_46_events() {
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
        registry::TOTAL_EVENT_COUNT,
        "the exhaustive sweep must cover the full closed registry"
    );
    assert_eq!(
        names.len(),
        registry::registered_event_count(),
        "event_names() must enumerate exactly the registered set"
    );

    // Tally of events that advance accepted_head under PASS — must end at exactly 12, and that
    // set must be exactly the SOVEREIGN_ACCEPT class.
    let mut advancing_under_pass: Vec<String> = Vec::new();

    for name in &names {
        let row =
            registry::registry(name).expect("every enumerated name resolves to a registry row");
        let class = row.class;
        // The registry-derived head_effect — the ONLY trustworthy source (never writer-set).
        let head_effect = row.head_effect;

        let is_sovereign_accept = class == EventClass::SovereignAccept;
        // Sanity-bind the registry's own internal consistency: SOVEREIGN_ACCEPT ⇔ ADVANCE to
        // accepted_head; nothing else targets accepted_head.
        if is_sovereign_accept {
            assert_eq!(
                head_effect,
                HeadEffect::Advance,
                "{name}: a SOVEREIGN_ACCEPT event must carry registry head_effect ADVANCE"
            );
            assert_eq!(
                row.target_ref,
                TargetRef::AcceptedHead,
                "{name}: a SOVEREIGN_ACCEPT event must target accepted_head"
            );
        } else {
            assert_ne!(
                row.target_ref,
                TargetRef::AcceptedHead,
                "{name}: only SOVEREIGN_ACCEPT may target accepted_head"
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

            // The law: accepted_head advances IFF SOVEREIGN_ACCEPT ∧ ADVANCE ∧ PASS.
            let should_advance_accepted = is_sovereign_accept
                && head_effect == HeadEffect::Advance
                && product == PredicateProduct::Pass;

            if should_advance_accepted {
                assert_eq!(
                    decision.accepted_head.as_deref(),
                    Some(n.as_str()),
                    "{name}/{product:?}: SOVEREIGN_ACCEPT+ADVANCE+PASS MUST advance accepted_head \
                     to the new OID"
                );
                assert_eq!(
                    decision.head_moved,
                    HeadMoved::AcceptedHead,
                    "{name}/{product:?}: the moved head must be reported as AcceptedHead"
                );
                // At most one head moves: authorization_head stays == A for these.
                assert_eq!(
                    decision.authorization_head.as_deref(),
                    Some(a.as_str()),
                    "{name}/{product:?}: authorization_head A must NOT move when accepted_head does"
                );
            } else {
                // accepted_head is carried forward byte-unchanged (still B).
                assert_eq!(
                    decision.accepted_head.as_deref(),
                    Some(b.as_str()),
                    "{name}/{product:?}: accepted_head MUST stay == B (no advance) unless \
                     SOVEREIGN_ACCEPT+ADVANCE+PASS"
                );
                // And specifically it must NOT have become the new event OID.
                assert_ne!(
                    decision.accepted_head.as_deref(),
                    Some(n.as_str()),
                    "{name}/{product:?}: accepted_head must NOT advance to the new OID here"
                );
                // The reducer must not claim accepted_head moved.
                assert_ne!(
                    decision.head_moved,
                    HeadMoved::AcceptedHead,
                    "{name}/{product:?}: head_moved must not be AcceptedHead here"
                );
            }

            if product == PredicateProduct::Pass && should_advance_accepted {
                advancing_under_pass.push(name.to_string());
            }
        }
    }

    // EXACTLY 12 events advance accepted_head under PASS — and they are EXACTLY the
    // SOVEREIGN_ACCEPT class (verified two ways: count, and that each is SOVEREIGN_ACCEPT).
    assert_eq!(
        advancing_under_pass.len(),
        12,
        "exactly 12 events may advance accepted_head under PASS (the SOVEREIGN_ACCEPT class), \
         got: {advancing_under_pass:?}"
    );
    for name in &advancing_under_pass {
        assert_eq!(
            registry::registry(name).unwrap().class,
            EventClass::SovereignAccept,
            "{name} advanced accepted_head but is not SOVEREIGN_ACCEPT class"
        );
    }
    // The advancing set IS the SOVEREIGN_ACCEPT set: every SOVEREIGN_ACCEPT event is present,
    // and no non-SOVEREIGN_ACCEPT event is (count 12 + all-SOVEREIGN_ACCEPT above ⇒ set
    // equality).
    let sovereign_accept_names: Vec<&String> = names
        .iter()
        .filter(|nm| registry::registry(nm).unwrap().class == EventClass::SovereignAccept)
        .collect();
    assert_eq!(
        sovereign_accept_names.len(),
        12,
        "the registry must declare exactly 12 SOVEREIGN_ACCEPT events"
    );
    for nm in &sovereign_accept_names {
        assert!(
            advancing_under_pass.contains(nm),
            "SOVEREIGN_ACCEPT event {nm} must advance accepted_head under PASS"
        );
    }
}

// --- focused adversarial cases: FAIL / NOT_RUN never advance even SOVEREIGN_ACCEPT ----

#[test]
fn sovereign_accept_event_under_fail_or_not_run_never_advances_accepted_head() {
    let pre = nontrivial_pre();
    let b = head_b();
    let n = new_event_oid();

    // Walk EVERY SOVEREIGN_ACCEPT event (registry-derived) and prove FAIL / NOT_RUN are inert
    // on accepted_head — only a PASS may move it.
    let accept_names: Vec<String> = registry::event_names()
        .filter(|nm| registry::registry(nm).unwrap().class == EventClass::SovereignAccept)
        .map(str::to_owned)
        .collect();
    assert_eq!(
        accept_names.len(),
        12,
        "12 SOVEREIGN_ACCEPT events expected"
    );

    for name in &accept_names {
        let row = registry::registry(name).unwrap();
        for product in [PredicateProduct::Fail, PredicateProduct::NotRun] {
            let decision = reducer::apply(&pre, row.class, row.head_effect, product, &n);
            assert_eq!(
                decision.accepted_head.as_deref(),
                Some(b.as_str()),
                "{name}/{product:?}: a non-PASS SOVEREIGN_ACCEPT event must NOT advance \
                 accepted_head"
            );
            assert_eq!(
                decision.head_moved,
                HeadMoved::None,
                "{name}/{product:?}: a non-PASS SOVEREIGN_ACCEPT event moves no sovereign head"
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
            pass.accepted_head.as_deref(),
            Some(n.as_str()),
            "{name}: PASS must advance accepted_head (positive control)"
        );
        assert_eq!(pass.head_moved, HeadMoved::AcceptedHead);
    }
}

// --- focused adversarial case: an AUTHORIZATION PASS moves authorization_head, NOT accepted ----

#[test]
fn authorization_pass_moves_authorization_head_and_leaves_accepted_head_untouched() {
    let pre = nontrivial_pre();
    let b = head_b();
    let n = new_event_oid();

    // AtomAuthorized is an AUTHORIZATION (ADVANCE → authorization_head). Under PASS it must
    // move authorization_head and leave accepted_head == B. This is the adjacent-law guard:
    // SG-16 must NOT advance accepted_head for the OTHER advancing class.
    let row = registry::registry("AtomAuthorized").expect("AtomAuthorized is registered");
    assert_eq!(row.class, EventClass::Authorization);
    assert_eq!(row.head_effect, HeadEffect::Advance);

    let decision = reducer::apply(&pre, row.class, row.head_effect, PredicateProduct::Pass, &n);
    assert_eq!(
        decision.accepted_head.as_deref(),
        Some(b.as_str()),
        "an AUTHORIZATION PASS must leave accepted_head == B"
    );
    assert_eq!(
        decision.authorization_head.as_deref(),
        Some(n.as_str()),
        "an AUTHORIZATION PASS moves authorization_head to the new OID"
    );
    assert_eq!(decision.head_moved, HeadMoved::AuthorizationHead);
}
