use serde_json::json;
use turing_contracts::registry::EventClass;
use turing_git_tape::append::{Append, AppendRequest};
use turing_git_tape::git;
use turing_loop::tick::{self, TickDecision, TickPhase};

#[test]
fn single_tick_accept_and_reject() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");

    let tape = Append::open(repo).expect("open tape");
    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let accept = tick::single_tick(
        repo,
        TickDecision::AcceptCandidate {
            writer_id: "writer:tick".to_string(),
            payload: json!({"candidate_id": "cand_1"}),
        },
    )
    .expect("accept tick");

    assert_eq!(
        accept.phase_order,
        vec![
            TickPhase::Read,
            TickPhase::Propose,
            TickPhase::Verify,
            TickPhase::WriteAccept,
            TickPhase::Compress,
            TickPhase::BroadcastShield,
            TickPhase::HaltCheck,
        ]
    );
    assert!(accept.wrote_event);
    assert_eq!(accept.write_event_type, "CandidateAccepted");
    assert_eq!(accept.q_before.head_set.accepted_head, genesis.event_id);
    assert_eq!(
        accept.q_after.head_set.accepted_head,
        accept.receipt.event_id
    );
    assert_eq!(
        accept.q_after.events.last().unwrap().class,
        EventClass::SovereignAccept
    );

    let reject = tick::single_tick(
        repo,
        TickDecision::RejectFailure {
            writer_id: "writer:tick".to_string(),
            payload: json!({
                "failure_class": "PREDICATE_FAIL",
                "source_event_id": accept.receipt.event_id,
            }),
        },
    )
    .expect("reject tick");

    assert_eq!(
        reject.phase_order,
        vec![
            TickPhase::Read,
            TickPhase::Propose,
            TickPhase::Verify,
            TickPhase::WriteReject,
            TickPhase::Compress,
            TickPhase::BroadcastShield,
            TickPhase::HaltCheck,
        ]
    );
    assert!(reject.wrote_event);
    assert_eq!(reject.write_event_type, "FailureNode");
    assert_eq!(
        reject.q_after.head_set.accepted_head, accept.q_after.head_set.accepted_head,
        "reject appends a failure node but cannot advance accepted_head"
    );
    assert_eq!(reject.q_after.head_set.tape_tip, reject.receipt.event_id);
    assert_eq!(
        reject.q_after.events.last().unwrap().event_type,
        "FailureNode"
    );
    assert_eq!(
        reject.q_after.events.last().unwrap().class,
        EventClass::Failure
    );
}
