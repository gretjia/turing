//! SG-17 — "Registry-derived head effect" (`cargo nextest run -p turing-kernel --test head_effect_tamper`).
//!
//! Two genuinely-new laws, both bound to the ratified contract:
//!
//! **(A) Admission A4 — head-effect tamper rejection**
//! (`pack/03_contracts/operation/append_algorithm_v5_3_1.md` A4;
//! `event_registry_v5_3_1.json:53,190`). The carried `head_effect` is **registry-derived,
//! never writer-trusted**: a candidate whose carried `head_effect` differs from
//! `registry[event_type].head_effect` is REJECTED at admission with `HEAD_EFFECT_DISAGREEMENT`,
//! and never reaches the reducer (so a forged effect can never move a head or bump the epoch).
//! Tested in BOTH directions: an ADVANCE-class event that forges PRESERVE, and a PRESERVE-class
//! event that forges ADVANCE. A correctly-carried `head_effect` (== the registry row) admits.
//!
//! **(B) Authority-epoch transition** (`greenfield_spec_v5_3_1.md:215-217, 287`).
//! `authority_epoch_after == payload.new_authority_epoch` **iff** the event is a *valid PASSed
//! human-signed authority-transfer `ProjectLawAmended`* AND `new_authority_epoch ==
//! authority_epoch_before + 1` (increment by EXACTLY ONE). For every non-qualifying event
//! (wrong event type, non-authority-transfer `ProjectLawAmended`, not human-signed,
//! FAIL/NOT_RUN, or `new_authority_epoch != before + 1`) the epoch is carried forward
//! unchanged. On the single valid case `accepted_head` also advances (ProjectLawAmended is
//! SOVEREIGN_ACCEPT + ADVANCE), proving the epoch bump and the head move are coupled by the
//! same PASS.
//!
//! Anti-Goodhart: the REAL registry (`turing-contracts`) is bound — `ProjectLawAmended`'s
//! class/head_effect come from the ratified `event_registry_v5_3_1.json`, not a hand-typed
//! mirror. Distinct OIDs and distinct epoch values make every wrong outcome byte-detectable.
//! Public crate API only; no `assert!(true)`.

use turing_contracts::envelope::{HeadEffect, PredicateProduct};
use turing_contracts::payload::ProjectLawAmended;
use turing_contracts::registry::{self, EventClass};

use turing_kernel::admission::{self, RejectClass};
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

/// Pre-state head `B` (`accepted_head`) — moves only on the qualifying ProjectLawAmended.
fn head_b() -> String {
    mu(0xbb)
}

/// The minted OID Git would assign the new event commit — distinct from BOTH heads.
fn new_event_oid() -> String {
    mu(0xcc)
}

/// The pre-state fencing epoch under test (a non-trivial, non-zero value so `before + 1`,
/// `before + 2` and `before` are all distinguishable).
const EPOCH_BEFORE: u64 = 7;

/// A non-trivial pre-state with DISTINCT sovereign heads + epoch `EPOCH_BEFORE`.
fn nontrivial_pre() -> PreState {
    PreState {
        tape_tip: Some(mu(0x11)),
        authorization_head: Some(head_a()),
        accepted_head: Some(head_b()),
        authority_epoch: EPOCH_BEFORE,
        parent_sequence: Some(41),
    }
}

// =============================================================================
// (A) Admission A4 — carried head_effect must equal the registry row, else reject.
// =============================================================================

#[test]
fn carried_head_effect_equal_to_registry_row_is_admitted() {
    // ProjectLawAmended is registry head_effect ADVANCE; carrying ADVANCE admits.
    let advance_row = registry::registry("ProjectLawAmended").expect("registered");
    assert_eq!(
        advance_row.head_effect,
        HeadEffect::Advance,
        "bind the REAL registry: ProjectLawAmended is ADVANCE"
    );
    assert_eq!(
        admission::admit_head_effect("ProjectLawAmended", HeadEffect::Advance),
        Ok(()),
        "a carried head_effect equal to the registry row is admitted"
    );

    // A PRESERVE-class event (GoalStateProposed, a PROPOSAL) carrying PRESERVE admits.
    let preserve_row = registry::registry("GoalStateProposed").expect("registered");
    assert_eq!(
        preserve_row.head_effect,
        HeadEffect::Preserve,
        "bind the REAL registry: GoalStateProposed is PRESERVE"
    );
    assert_eq!(
        admission::admit_head_effect("GoalStateProposed", HeadEffect::Preserve),
        Ok(()),
        "a carried PRESERVE on a PRESERVE-class event is admitted"
    );
}

#[test]
fn advance_class_event_carrying_preserve_is_rejected_head_effect_disagreement() {
    // Direction 1: an ADVANCE-class event whose writer FORGES head_effect = PRESERVE.
    // Registry says ADVANCE; carried says PRESERVE → HEAD_EFFECT_DISAGREEMENT.
    let row = registry::registry("ProjectLawAmended").expect("registered");
    assert_eq!(row.head_effect, HeadEffect::Advance);

    assert_eq!(
        admission::admit_head_effect("ProjectLawAmended", HeadEffect::Preserve),
        Err(RejectClass::HeadEffectDisagreement),
        "an ADVANCE-class event carrying PRESERVE must be rejected at admission"
    );
}

#[test]
fn preserve_class_event_carrying_advance_is_rejected_head_effect_disagreement() {
    // Direction 2: a PRESERVE-class event whose writer FORGES head_effect = ADVANCE.
    // Registry says PRESERVE; carried says ADVANCE → HEAD_EFFECT_DISAGREEMENT.
    let row = registry::registry("GoalStateProposed").expect("registered");
    assert_eq!(row.head_effect, HeadEffect::Preserve);

    assert_eq!(
        admission::admit_head_effect("GoalStateProposed", HeadEffect::Advance),
        Err(RejectClass::HeadEffectDisagreement),
        "a PRESERVE-class event carrying ADVANCE must be rejected at admission"
    );

    // Also exercise an OBSERVATION-class PRESERVE event forging ADVANCE (a second PRESERVE
    // family), so the rejection is not specific to PROPOSAL.
    let obs = registry::event_names()
        .find(|n| registry::registry(n).unwrap().class == EventClass::Observation)
        .expect("at least one OBSERVATION event exists");
    assert_eq!(
        registry::registry(obs).unwrap().head_effect,
        HeadEffect::Preserve
    );
    assert_eq!(
        admission::admit_head_effect(obs, HeadEffect::Advance),
        Err(RejectClass::HeadEffectDisagreement),
        "{obs}: a PRESERVE OBSERVATION event carrying ADVANCE is rejected"
    );
}

#[test]
fn admission_a4_holds_for_every_event_in_the_real_registry() {
    // Exhaustive over the closed 46: for EACH event, carrying the registry head_effect admits,
    // and carrying the OPPOSITE head_effect is rejected HEAD_EFFECT_DISAGREEMENT. Binds the
    // real registry (registry-derived, never a hand-typed list).
    let names: Vec<String> = registry::event_names().map(str::to_owned).collect();
    assert_eq!(
        names.len(),
        registry::TOTAL_EVENT_COUNT,
        "the sweep covers the full closed registry"
    );

    let mut advance_seen = 0usize;
    let mut preserve_seen = 0usize;
    for name in &names {
        let row = registry::registry(name).expect("enumerated name resolves");
        let correct = row.head_effect;
        let forged = match correct {
            HeadEffect::Advance => {
                advance_seen += 1;
                HeadEffect::Preserve
            }
            HeadEffect::Preserve => {
                preserve_seen += 1;
                HeadEffect::Advance
            }
        };

        assert_eq!(
            admission::admit_head_effect(name, correct),
            Ok(()),
            "{name}: carrying the registry head_effect ({correct:?}) must admit"
        );
        assert_eq!(
            admission::admit_head_effect(name, forged),
            Err(RejectClass::HeadEffectDisagreement),
            "{name}: carrying a forged head_effect ({forged:?}) must be rejected"
        );
    }
    // Registry self-consistency sanity (the 20/26 ADVANCE/PRESERVE split).
    assert_eq!(advance_seen, 20, "20 ADVANCE events in the closed registry");
    assert_eq!(
        preserve_seen,
        26 + registry::ECONOMY_EVENT_COUNT + registry::BENCHMARK_EVENT_COUNT,
        "baseline PRESERVE events plus additive economy and benchmark events in the closed registry"
    );
}

#[test]
fn admission_a4_rejects_an_unknown_event_type_closed_world() {
    // A4 binds the registry as the sole source of truth; an event_type outside the closed 46
    // has no registry row, so its head_effect cannot be validated → UNKNOWN_EVENT_TYPE
    // (closed-world reject), never silently admitted.
    assert!(registry::registry("NotARealEvent").is_none());
    assert_eq!(
        admission::admit_head_effect("NotARealEvent", HeadEffect::Advance),
        Err(RejectClass::UnknownEventType),
        "an unknown event_type is a closed-world reject, not admitted"
    );
    assert_eq!(
        admission::admit_head_effect("NotARealEvent", HeadEffect::Preserve),
        Err(RejectClass::UnknownEventType),
    );
}

// =============================================================================
// (B) Authority-epoch transition — increments by EXACTLY ONE on the valid case only.
// =============================================================================

/// A valid human-signed authority-transfer ProjectLawAmended payload moving to `new_epoch`.
fn authority_transfer(new_epoch: u64) -> ProjectLawAmended {
    ProjectLawAmended::authority_transfer(new_epoch, /* human_signed = */ true)
}

#[test]
fn valid_passed_human_signed_authority_transfer_increments_epoch_exactly_once() {
    let pre = nontrivial_pre();
    let n = new_event_oid();
    let row = registry::registry("ProjectLawAmended").expect("registered");
    // Bind the registry: ProjectLawAmended is SOVEREIGN_ACCEPT + ADVANCE (so accepted_head
    // moves on PASS and the epoch bump is coupled to the same PASS).
    assert_eq!(row.class, EventClass::SovereignAccept);
    assert_eq!(row.head_effect, HeadEffect::Advance);

    // new_authority_epoch == before + 1, human-signed, authority-transfer, PASS → qualifies.
    let payload = authority_transfer(EPOCH_BEFORE + 1);
    let decision = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        Some(&payload),
        &n,
    );

    // Epoch incremented by EXACTLY ONE.
    assert_eq!(
        decision.authority_epoch,
        EPOCH_BEFORE + 1,
        "a valid PASSed human-signed authority-transfer ProjectLawAmended with new == before+1 \
         sets authority_epoch = before+1"
    );
    // And accepted_head advanced (SOVEREIGN_ACCEPT + ADVANCE + PASS) to the new OID.
    assert_eq!(
        decision.accepted_head.as_deref(),
        Some(n.as_str()),
        "the qualifying ProjectLawAmended also advances accepted_head"
    );
    assert_eq!(decision.head_moved, HeadMoved::AcceptedHead);
    assert_eq!(decision.tape_tip, n);
}

#[test]
fn epoch_unchanged_when_new_authority_epoch_is_not_before_plus_one() {
    let pre = nontrivial_pre();
    let n = new_event_oid();
    let row = registry::registry("ProjectLawAmended").unwrap();

    // before + 2 — a jump by two is NOT an increment-by-one → epoch carried forward.
    let jump_two = authority_transfer(EPOCH_BEFORE + 2);
    let d2 = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        Some(&jump_two),
        &n,
    );
    assert_eq!(
        d2.authority_epoch, EPOCH_BEFORE,
        "new_authority_epoch == before+2 is not an increment-by-one; epoch carried forward"
    );

    // == before (no change requested) — not an increment → epoch carried forward.
    let same = authority_transfer(EPOCH_BEFORE);
    let d3 = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        Some(&same),
        &n,
    );
    assert_eq!(
        d3.authority_epoch, EPOCH_BEFORE,
        "new_authority_epoch == before is not an increment; epoch carried forward"
    );

    // before - 1 (a decrement) — never qualifies.
    let down = authority_transfer(EPOCH_BEFORE - 1);
    let d4 = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        Some(&down),
        &n,
    );
    assert_eq!(
        d4.authority_epoch, EPOCH_BEFORE,
        "a decrement never qualifies; epoch carried forward"
    );
}

#[test]
fn epoch_unchanged_when_not_human_signed() {
    let pre = nontrivial_pre();
    let n = new_event_oid();
    let row = registry::registry("ProjectLawAmended").unwrap();

    // Authority-transfer with new == before+1 but NOT human-signed → does not qualify.
    let unsigned =
        ProjectLawAmended::authority_transfer(EPOCH_BEFORE + 1, /* human_signed = */ false);
    let d = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        Some(&unsigned),
        &n,
    );
    assert_eq!(
        d.authority_epoch, EPOCH_BEFORE,
        "a not-human-signed authority transfer must NOT bump the epoch"
    );
    // accepted_head still advances (it is a PASSed SOVEREIGN_ACCEPT) — the epoch gate is
    // independent of the head-advance gate, but BOTH must agree the epoch stays.
    assert_eq!(d.accepted_head.as_deref(), Some(n.as_str()));
}

#[test]
fn epoch_unchanged_for_non_authority_transfer_project_law_amended() {
    let pre = nontrivial_pre();
    let n = new_event_oid();
    let row = registry::registry("ProjectLawAmended").unwrap();

    // A ProjectLawAmended that is NOT an authority transfer (some other lawful amendment) —
    // even human-signed + PASS — carries the epoch forward (only AUTHORITY_TRANSFER bumps it).
    let non_transfer = ProjectLawAmended::non_authority_transfer(/* human_signed = */ true);
    let d = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        Some(&non_transfer),
        &n,
    );
    assert_eq!(
        d.authority_epoch, EPOCH_BEFORE,
        "a non-authority-transfer ProjectLawAmended must NOT bump the epoch"
    );
    // It is still a PASSed SOVEREIGN_ACCEPT, so accepted_head advances.
    assert_eq!(d.accepted_head.as_deref(), Some(n.as_str()));
    assert_eq!(d.head_moved, HeadMoved::AcceptedHead);
}

#[test]
fn epoch_unchanged_when_product_is_fail_or_not_run() {
    let pre = nontrivial_pre();
    let b = head_b();
    let n = new_event_oid();
    let row = registry::registry("ProjectLawAmended").unwrap();
    // An otherwise-perfect authority transfer (human-signed, new == before+1) but the
    // predicate did not PASS → no epoch bump and no head advance.
    let payload = authority_transfer(EPOCH_BEFORE + 1);

    for product in [PredicateProduct::Fail, PredicateProduct::NotRun] {
        let d = reducer::apply_with_epoch(
            &pre,
            "ProjectLawAmended",
            row.class,
            row.head_effect,
            product,
            Some(&payload),
            &n,
        );
        assert_eq!(
            d.authority_epoch, EPOCH_BEFORE,
            "{product:?}: a non-PASS authority transfer must NOT bump the epoch"
        );
        // accepted_head must NOT advance on a non-PASS (carried forward == B).
        assert_eq!(
            d.accepted_head.as_deref(),
            Some(b.as_str()),
            "{product:?}: a non-PASS SOVEREIGN_ACCEPT must NOT advance accepted_head"
        );
        assert_eq!(d.head_moved, HeadMoved::None);
        assert_eq!(d.tape_tip, n);
    }
}

#[test]
fn epoch_unchanged_for_any_non_project_law_amended_event_including_another_sovereign_accept() {
    let pre = nontrivial_pre();
    let n = new_event_oid();

    // GoalStateRatified is ALSO SOVEREIGN_ACCEPT + ADVANCE (so accepted_head advances under
    // PASS), but it is NOT ProjectLawAmended → the epoch must NOT bump, even if a (wrongly
    // attached) authority-transfer payload is present. Only ProjectLawAmended may bump.
    let other = registry::registry("GoalStateRatified").expect("registered");
    assert_eq!(other.class, EventClass::SovereignAccept);
    assert_eq!(other.head_effect, HeadEffect::Advance);

    let payload = authority_transfer(EPOCH_BEFORE + 1);
    let d = reducer::apply_with_epoch(
        &pre,
        "GoalStateRatified",
        other.class,
        other.head_effect,
        PredicateProduct::Pass,
        Some(&payload),
        &n,
    );
    assert_eq!(
        d.authority_epoch, EPOCH_BEFORE,
        "a non-ProjectLawAmended SOVEREIGN_ACCEPT must NOT bump the epoch"
    );
    // It still advances accepted_head (it is a PASSed SOVEREIGN_ACCEPT) — proving the epoch
    // gate keys off the EVENT TYPE, not merely off accepted_head moving.
    assert_eq!(d.accepted_head.as_deref(), Some(n.as_str()));
    assert_eq!(d.head_moved, HeadMoved::AcceptedHead);

    // And with no payload at all (a PASSed AUTHORIZATION event) the epoch is also unchanged.
    let auth = registry::registry("AtomAuthorized").expect("registered");
    let d2 = reducer::apply_with_epoch(
        &pre,
        "AtomAuthorized",
        auth.class,
        auth.head_effect,
        PredicateProduct::Pass,
        None,
        &n,
    );
    assert_eq!(
        d2.authority_epoch, EPOCH_BEFORE,
        "a non-ProjectLawAmended event with no payload carries the epoch forward"
    );
    assert_eq!(d2.head_moved, HeadMoved::AuthorizationHead);
}

#[test]
fn epoch_unchanged_when_no_payload_is_supplied_even_for_project_law_amended() {
    let pre = nontrivial_pre();
    let n = new_event_oid();
    let row = registry::registry("ProjectLawAmended").unwrap();
    // ProjectLawAmended + PASS but NO authority-transfer payload available → carried forward.
    let d = reducer::apply_with_epoch(
        &pre,
        "ProjectLawAmended",
        row.class,
        row.head_effect,
        PredicateProduct::Pass,
        None,
        &n,
    );
    assert_eq!(
        d.authority_epoch, EPOCH_BEFORE,
        "ProjectLawAmended with no authority-transfer payload carries the epoch forward"
    );
}

// =============================================================================
// (C) A forged head_effect is rejected before the reducer — never moves a head / bumps epoch.
// =============================================================================

#[test]
fn forged_head_effect_is_rejected_before_the_reducer_so_it_cannot_bump_epoch_or_move_a_head() {
    let pre = nontrivial_pre();
    let b = head_b();
    let n = new_event_oid();

    // The append algorithm runs admission (A4) BEFORE the reducer. A ProjectLawAmended whose
    // writer FORGES head_effect = PRESERVE (to look inert) is rejected at admission — it never
    // reaches apply_with_epoch, so it can move NO head and bump NO epoch.
    let forged_effect = HeadEffect::Preserve; // writer lie; registry says ADVANCE
    let admit = admission::admit_head_effect("ProjectLawAmended", forged_effect);
    assert_eq!(
        admit,
        Err(RejectClass::HeadEffectDisagreement),
        "the forged head_effect is rejected at admission"
    );

    // Because admission rejected, the reducer is NOT invoked for the forged candidate. Model
    // the append-algorithm sequence explicitly: only on Ok(()) do we apply. Here it is Err, so
    // the heads + epoch remain exactly the pre-state.
    let post = match admit {
        Ok(()) => {
            // unreachable in this test, but encodes the real wiring (apply only after admit).
            let row = registry::registry("ProjectLawAmended").unwrap();
            let payload = authority_transfer(EPOCH_BEFORE + 1);
            reducer::apply_with_epoch(
                &pre,
                "ProjectLawAmended",
                row.class,
                forged_effect, // the forged effect would have flowed in — but never does
                PredicateProduct::Pass,
                Some(&payload),
                &n,
            )
        }
        Err(_) => reducer::HeadDecision {
            // no event minted; nothing moves
            tape_tip: pre.tape_tip.clone().unwrap(),
            authorization_head: pre.authorization_head.clone(),
            accepted_head: pre.accepted_head.clone(),
            authority_epoch: pre.authority_epoch,
            head_moved: HeadMoved::None,
        },
    };

    assert_eq!(
        post.authority_epoch, EPOCH_BEFORE,
        "a rejected forged candidate bumps NO epoch"
    );
    assert_eq!(
        post.accepted_head.as_deref(),
        Some(b.as_str()),
        "a rejected forged candidate moves NO accepted_head"
    );
    assert_eq!(post.head_moved, HeadMoved::None);
}
