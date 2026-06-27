use turing_integration::{
    AdmissionError, DriftState, IntegrationCandidate, IntegrationQueue, MainMergeGate,
};

#[test]
fn integration_queue_cas_admits_non_conflicting_and_rejects_stale() {
    let mut queue = IntegrationQueue::new(
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("queue");

    let first = IntegrationCandidate::new(
        "atom_a",
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        vec!["src/a.rs".to_string()],
    );
    queue.admit(first).expect("first admission");

    let second = IntegrationCandidate::new(
        "atom_b",
        "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        vec!["src/b.rs".to_string()],
    );
    queue
        .admit(second)
        .expect("serial non-conflicting admission");
    assert_eq!(
        queue.integration_head(),
        "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    );

    let stale = IntegrationCandidate::new(
        "atom_stale",
        "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "mu:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        vec!["src/c.rs".to_string()],
    );
    assert!(matches!(
        queue.admit(stale),
        Err(AdmissionError::StaleCandidate { .. })
    ));
    assert_eq!(
        queue.integration_head(),
        "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    );
}

#[test]
fn integration_conflict_leaves_head_unchanged() {
    let mut queue = IntegrationQueue::new(
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("queue");
    queue
        .admit(IntegrationCandidate::new(
            "atom_a",
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            vec!["src/a.rs".to_string()],
        ))
        .expect("first admission");

    let conflict = IntegrationCandidate::new(
        "atom_conflict",
        "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        vec!["src/a.rs".to_string()],
    );
    assert!(matches!(
        queue.admit(conflict),
        Err(AdmissionError::PathConflict { .. })
    ));
    assert_eq!(
        queue.integration_head(),
        "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    );
}

#[test]
fn no_auto_merge_main_and_drift_guard() {
    let auth = MainMergeGate::authorize(
        true,
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("human-gated authorization");
    assert!(auth.moves_authorization_head);
    assert!(!auth.moves_accepted_head);
    assert!(!auth.auto_merge_main);

    assert!(
        MainMergeGate::authorize(
            false,
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        .is_err()
    );

    let drift = DriftState {
        commits_ahead_main: 21,
        hours_since_last_sync: 1,
        unmerged_atoms: 1,
    };
    assert!(drift.blocks_new_admission());
}
