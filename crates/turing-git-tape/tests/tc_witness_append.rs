use serde_json::{Value, json};

use turing_git_tape::append::{Append, AppendRequest, HeadMoved, committed_body_bytes};
use turing_git_tape::git;

fn read_body(repo: &std::path::Path, event_id: &str) -> Value {
    let bytes = committed_body_bytes(repo, event_id).expect("committed event body");
    serde_json::from_slice(&bytes).expect("event body JSON")
}

fn state(counter_a: u64, counter_b: u64, program_counter: u64, halted: bool) -> Value {
    json!({
        "counter_a": counter_a,
        "counter_b": counter_b,
        "program_counter": program_counter,
        "halted": halted,
    })
}

fn h(hex: char) -> String {
    format!("sha256:{}", hex.to_string().repeat(64))
}

#[test]
fn tc_witness_events_append_through_three_ref_writer() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");
    let tape = Append::open(repo).expect("open tape");

    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": h('a')}),
            )
            .predicate_pass(),
        )
        .expect("genesis append");

    let started = tape
        .append(
            AppendRequest::new(
                "ComputationStarted",
                "writer:tc2",
                json!({
                    "program_id": "program:add-one",
                    "program_digest": h('b'),
                    "program": [
                        {"op": "INC", "counter": "counter_a", "next_pc": 1},
                        {"op": "HALT"},
                    ],
                    "initial_state": state(0, 0, 0, false),
                    "state_hash": h('c'),
                    "step_budget": 8,
                    "instruction_registry_digest": h('d'),
                }),
            )
            .predicate_pass(),
        )
        .expect("ComputationStarted append");

    assert_eq!(started.head_moved, HeadMoved::None);
    assert_eq!(started.accepted_head_after, genesis.event_id);
    assert_eq!(started.authorization_head_after, None);

    let authorized = tape
        .append(
            AppendRequest::new(
                "InstructionAuthorized",
                "writer:tc2",
                json!({
                    "program_id": "program:add-one",
                    "step_index": 0,
                    "pc": 0,
                    "instruction": {"op": "INC", "counter": "counter_a", "next_pc": 1},
                    "predicate": "INSTRUCTION_IN_CLOSED_PROGRAM_AND_BUDGET_REMAINING",
                    "budget_remaining": 8,
                }),
            )
            .predicate_pass(),
        )
        .expect("InstructionAuthorized append");

    assert_eq!(authorized.head_moved, HeadMoved::AuthorizationHead);
    assert_eq!(
        authorized.authorization_head_after,
        Some(authorized.event_id.clone())
    );
    assert_eq!(authorized.accepted_head_after, genesis.event_id);

    let applied = tape
        .append(
            AppendRequest::new(
                "InstructionApplied",
                "writer:tc2",
                json!({
                    "program_id": "program:add-one",
                    "step_index": 0,
                    "pc_before": 0,
                    "pc_after": 1,
                    "instruction": {"op": "INC", "counter": "counter_a", "next_pc": 1},
                    "prev_state_hash": h('c'),
                    "next_state_hash": h('e'),
                }),
            )
            .predicate_pass(),
        )
        .expect("InstructionApplied append");

    assert_eq!(applied.head_moved, HeadMoved::None);
    assert_eq!(
        applied.authorization_head_after,
        Some(authorized.event_id.clone())
    );

    let observed = tape
        .append(
            AppendRequest::new(
                "MachineStateObserved",
                "writer:tc2",
                json!({
                    "program_id": "program:add-one",
                    "step_index": 1,
                    "state": state(1, 0, 1, false),
                    "state_hash": h('e'),
                    "source_event_id": applied.event_id,
                }),
            )
            .predicate_pass(),
        )
        .expect("MachineStateObserved append");

    let halted = tape
        .append(
            AppendRequest::new(
                "ComputationHalted",
                "writer:tc2",
                json!({
                    "program_id": "program:add-one",
                    "final_step_index": 1,
                    "final_state": state(1, 0, 1, true),
                    "final_state_hash": h('f'),
                    "halt_kind": "EXPLICIT_HALT",
                }),
            )
            .predicate_pass(),
        )
        .expect("ComputationHalted append");

    assert_eq!(halted.head_moved, HeadMoved::None);
    assert_eq!(halted.accepted_head_after, genesis.event_id);
    assert_eq!(
        halted.authorization_head_after,
        Some(authorized.event_id.clone())
    );

    let final_heads = tape
        .head_set()
        .expect("head set")
        .expect("post-genesis heads");
    assert_eq!(final_heads.tape_tip, halted.event_id);
    assert_eq!(final_heads.accepted_head, genesis.event_id);
    assert_eq!(final_heads.authorization_head, Some(authorized.event_id));

    let authorized_body = read_body(repo, final_heads.authorization_head.as_ref().unwrap());
    assert_eq!(
        authorized_body["event_type"],
        json!("InstructionAuthorized")
    );
    assert_eq!(authorized_body["head_effect"], json!("ADVANCE"));
    assert_eq!(
        authorized_body["event_schema_id"],
        json!("instruction_authorized.v1")
    );
    assert_eq!(
        read_body(repo, &observed.event_id)["event_type"],
        json!("MachineStateObserved")
    );
}
