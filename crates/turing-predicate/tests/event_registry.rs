use turing_contracts::envelope::HeadEffect;
use turing_contracts::registry::{self, EventClass, TargetRef};
use turing_predicate::{
    event_registry_closed_world, registered_event_count, registered_event_names,
};

#[test]
fn event_registry_closed_world_rejects_unknown_events() {
    assert_eq!(registered_event_count(), registry::TOTAL_EVENT_COUNT);

    let accepted = event_registry_closed_world("SystemConstitutionAccepted")
        .expect("known sovereign accept event resolves");
    assert_eq!(accepted.class, EventClass::SovereignAccept);
    assert_eq!(accepted.head_effect, HeadEffect::Advance);
    assert_eq!(accepted.target_ref, TargetRef::AcceptedHead);

    let authorization =
        event_registry_closed_world("AtomAuthorized").expect("known authorization event resolves");
    assert_eq!(authorization.class, EventClass::Authorization);
    assert_eq!(authorization.head_effect, HeadEffect::Advance);
    assert_eq!(authorization.target_ref, TargetRef::AuthorizationHead);

    let proposal =
        event_registry_closed_world("GoalStateProposed").expect("known proposal event resolves");
    assert_eq!(proposal.head_effect, HeadEffect::Preserve);
    assert_eq!(proposal.target_ref, TargetRef::TapeTip);

    assert!(event_registry_closed_world("NotARealEvent").is_err());
    assert!(event_registry_closed_world("").is_err());
}

#[test]
fn event_registry_closed_world_enumerates_only_resolvable_events() {
    let names: Vec<&str> = registered_event_names().collect();
    assert_eq!(names.len(), registry::TOTAL_EVENT_COUNT);
    assert_eq!(names.len(), registered_event_count());

    for name in names {
        assert!(
            event_registry_closed_world(name).is_ok(),
            "registered name {name:?} must resolve"
        );
    }
}

#[test]
fn economy_events_preserve_only() {
    let economy_names: Vec<&str> = registered_event_names()
        .filter(|name| event_registry_closed_world(name).unwrap().class == EventClass::Economy)
        .collect();
    assert_eq!(economy_names.len(), registry::ECONOMY_EVENT_COUNT);

    for name in economy_names {
        let row = event_registry_closed_world(name).expect("economy event resolves");
        assert_eq!(row.class, EventClass::Economy, "{name} is ECONOMY");
        assert_eq!(row.head_effect, HeadEffect::Preserve, "{name} is PRESERVE");
        assert_eq!(
            row.target_ref,
            TargetRef::TapeTip,
            "{name} targets tape_tip"
        );
    }

    for expected in [
        "MarketCreated",
        "PositionMinted",
        "AMMSwapExecuted",
        "AgentBidSubmitted",
        "MarketSettled",
        "RewardDistributed",
        "CostEvent",
        "BranchCostEvent",
        "ToolStdoutCostEvent",
        "PPUTAccounted",
    ] {
        let row = event_registry_closed_world(expected)
            .unwrap_or_else(|_| panic!("expected economy event {expected}"));
        assert_eq!(row.class, EventClass::Economy);
        assert_eq!(row.head_effect, HeadEffect::Preserve);
        assert_eq!(row.target_ref, TargetRef::TapeTip);
    }
}
