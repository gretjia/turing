use turing_contracts::failure::FailureClass;
use turing_failure::{
    BroadcastReducer, FailureClassifier, FailureSignals, FailureTapeEvent, MemoryReducer,
    RuleShield,
};

#[test]
fn classifier_uses_observed_signals_and_preserves_unknown() {
    let timeout = FailureClassifier::classify(FailureSignals {
        exit_code: Some(124),
        stderr_excerpt: "command exceeded timeout".to_string(),
        predicate_reject_class: None,
        tool_denied: false,
        credential_signal: false,
        sandbox_signal: false,
    });
    assert_eq!(timeout.failure_class, FailureClass::TimeoutSoft);

    let credential = FailureClassifier::classify(FailureSignals {
        exit_code: Some(1),
        stderr_excerpt: "credential material appeared in stdout".to_string(),
        predicate_reject_class: None,
        tool_denied: false,
        credential_signal: true,
        sandbox_signal: false,
    });
    assert_eq!(credential.failure_class, FailureClass::CredentialViolation);

    let unknown = FailureClassifier::classify(FailureSignals {
        exit_code: Some(2),
        stderr_excerpt: "opaque vendor error".to_string(),
        predicate_reject_class: None,
        tool_denied: false,
        credential_signal: false,
        sandbox_signal: false,
    });
    assert_eq!(unknown.failure_class, FailureClass::UnknownNonzero);
    assert_eq!(unknown.observed_signals.len(), 2);
}

#[test]
fn failure_memory_is_derived_from_tape_events_only() {
    let events = vec![
        FailureTapeEvent::new(
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "wc_alpha",
            FailureClass::NoDiff,
            "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        ),
        FailureTapeEvent::new(
            "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "wc_alpha",
            FailureClass::NoDiff,
            "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        ),
        FailureTapeEvent::new(
            "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "wc_beta",
            FailureClass::OverScope,
            "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        ),
    ];

    let memory = MemoryReducer::from_tape_events(&events).expect("failure memory");
    let no_diff = memory
        .clusters
        .iter()
        .find(|cluster| cluster.failure_class == FailureClass::NoDiff)
        .expect("NoDiff cluster");
    assert_eq!(no_diff.count, 2);
    assert!(no_diff.repeated);
    assert_eq!(memory.source, "micro_tape_only");
}

#[test]
fn broadcast_rule_is_abstract_and_references_failure_nodes() {
    let events = vec![
        FailureTapeEvent::new(
            "mu:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "wc_ui",
            FailureClass::OutputSchemaViolation,
            "sha256:4444444444444444444444444444444444444444444444444444444444444444",
        )
        .with_raw_detail("Traceback: hidden_predicate score PPUT progress / (tokens * time)"),
    ];
    let memory = MemoryReducer::from_tape_events(&events).expect("failure memory");
    let rule = BroadcastReducer::from_cluster(&memory.clusters[0]).expect("broadcast rule");

    assert_eq!(rule.schema_id, "broadcast_rule.v1");
    assert_eq!(
        rule.source_failure_nodes,
        vec!["mu:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"]
    );
    assert!(!rule.summary.contains("Traceback"));
    assert!(!rule.summary.contains("hidden_predicate"));
    assert!(!rule.summary.contains("PPUT"));

    let relevant = RuleShield::select_for_capsule(&[rule.clone()], "wc_ui");
    assert_eq!(relevant, vec![rule]);
    assert!(RuleShield::select_for_capsule(&relevant, "wc_other").is_empty());
}
