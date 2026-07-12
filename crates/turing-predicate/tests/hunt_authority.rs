//! PART C.1 lens 6 (authority/boundary finder, INV-9/10/18) — adversarial attack tests
//! against `market_event_preserves_truth` (`turing-predicate/src/lib.rs:220`), the gate
//! that is supposed to prove "an economy event can never move truth". Attack model: run
//! it over EVERY event name in the closed, ratified registry (not a hand-typed subset)
//! and assert the accept/reject split matches the registry's OWN class/head_effect
//! fields exactly -- i.e. try to find an event that is class=ECONOMY but NOT accepted,
//! or an event that IS accepted despite not being a PRESERVE-class economy row (which
//! would mean a SOVEREIGN_ACCEPT event like `CandidateAccepted` could be laundered
//! through this "preserves truth" gate and mistaken for an economy signal downstream).

use turing_contracts::registry::{self, EventClass};
use turing_predicate::market_event_preserves_truth;

/// Exhaustive sweep (not a random fuzz -- the registry is a small closed enumeration,
/// so we cover all of it) over every registered event name.
#[test]
fn market_event_preserves_truth_matches_registry_exactly_for_every_event() {
    let names: Vec<String> = registry::event_names().map(str::to_owned).collect();
    assert!(
        names.len() >= registry::BASELINE_EVENT_COUNT + registry::ECONOMY_EVENT_COUNT,
        "sweep must cover at least the baseline + economy events"
    );

    let mut economy_seen = 0usize;
    let mut non_economy_seen = 0usize;

    for name in &names {
        let row = registry::registry(name).expect("enumerated name resolves");
        let result = market_event_preserves_truth(name);

        if row.class == EventClass::Economy {
            economy_seen += 1;
            assert!(
                result.is_ok(),
                "{name}: is class=ECONOMY (head_effect={:?}) but \
                 market_event_preserves_truth rejected it: {result:?}",
                row.head_effect
            );
        } else {
            non_economy_seen += 1;
            assert!(
                result.is_err(),
                "{name}: is class={:?} (NOT economy) but \
                 market_event_preserves_truth ACCEPTED it -- this would let a \
                 non-economy event (e.g. a SOVEREIGN_ACCEPT) be laundered through the \
                 economy preserve-truth gate. OBSERVED: Ok(()), EXPECTED: Err(..)",
                row.class
            );
        }
    }

    assert_eq!(
        economy_seen,
        registry::ECONOMY_EVENT_COUNT,
        "every one of the {} registered ECONOMY events must have been probed",
        registry::ECONOMY_EVENT_COUNT
    );
    assert!(non_economy_seen > 0, "sweep must also cover non-economy events");
}

/// Targeted adversarial case: the single highest-value forgery for INV-10 would be
/// getting `market_event_preserves_truth("CandidateAccepted")` (the SOVEREIGN_ACCEPT
/// event that is THE sole acceptance authority per Art I.1) to return `Ok(())`, which
/// would let code that gates on this function mistakenly treat a real acceptance event
/// as an inert economy signal.
#[test]
fn candidate_accepted_is_never_accepted_by_the_economy_preserve_gate() {
    let result = market_event_preserves_truth("CandidateAccepted");
    assert!(
        result.is_err(),
        "OBSERVED: {result:?}. EXPECTED: Err(..) -- CandidateAccepted must never pass \
         the economy preserve-truth gate"
    );
}

/// Adversarial case: a name that is NOT in the closed registry at all (a forged/unknown
/// event type) must be rejected with `UnknownEventType`, not silently treated as
/// preserve-safe.
#[test]
fn unknown_event_type_is_rejected_not_silently_preserved() {
    let forged_names = [
        "MarketAccepted",       // plausible-sounding, does not exist
        "EconomyTruthAdvanced", // adversarial name trying to sound both economy and advancing
        "",
        "candidatemarketed",
    ];
    for name in forged_names {
        let result = market_event_preserves_truth(name);
        assert!(
            result.is_err(),
            "{name:?}: OBSERVED Ok(()) for an unregistered event name, EXPECTED \
             Err(UnknownEventType)"
        );
    }
}
