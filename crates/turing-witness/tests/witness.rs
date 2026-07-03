use serde_json::{Value, json};

use turing_git_tape::append::{Append, AppendRequest, HeadMoved, committed_body_bytes};
use turing_git_tape::git;
use turing_witness::{
    CounterMachineProgram, Instruction, MachineState, WitnessEvent, emit_witness_run,
    reduce_witness_tape, state_hash_v1,
};

fn h(hex: char) -> String {
    format!("sha256:{}", hex.to_string().repeat(64))
}

fn genesis(repo: &std::path::Path) -> String {
    let tape = Append::open(repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": h('a')}),
        )
        .predicate_pass(),
    )
    .expect("genesis append")
    .event_id
}

fn body(repo: &std::path::Path, event_id: &str) -> Value {
    let bytes = committed_body_bytes(repo, event_id).expect("event body");
    serde_json::from_slice(&bytes).expect("event body JSON")
}

#[test]
fn interpreter_core_is_generic_over_counter_count() {
    let program = CounterMachineProgram::new(vec![
        Instruction::Inc {
            counter: 2,
            next_pc: 1,
        },
        Instruction::DecJz {
            counter: 2,
            zero_pc: 3,
            nonzero_pc: 2,
        },
        Instruction::Halt,
        Instruction::Halt,
    ])
    .expect("program loads");

    let initial = MachineState::new(0, vec![5, 0, 0], false).expect("state loads");
    let step1 = program.step(&initial).expect("INC counter 2");
    assert_eq!(
        step1.next_state,
        MachineState::new(1, vec![5, 0, 1], false).unwrap()
    );

    let step2 = program.step(&step1.next_state).expect("DECJZ counter 2");
    assert_eq!(
        step2.next_state,
        MachineState::new(2, vec![5, 0, 0], false).unwrap()
    );
}

#[test]
fn emitter_uses_three_ref_append_path_and_reducer_conserves_state() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");
    let genesis_id = genesis(repo);

    let program = CounterMachineProgram::new(vec![
        Instruction::Inc {
            counter: 0,
            next_pc: 1,
        },
        Instruction::Halt,
    ])
    .expect("program loads");
    let initial = MachineState::new(0, vec![0, 0], false).expect("initial state");

    let run = emit_witness_run(
        repo,
        "writer:tc2",
        "program:add-one",
        &program,
        initial.clone(),
        8,
    )
    .expect("witness run emits");

    assert_eq!(
        run.final_state,
        MachineState::new(1, vec![1, 0], true).unwrap()
    );
    assert_eq!(run.events.first().unwrap().event_type, "ComputationStarted");
    assert_eq!(run.events.last().unwrap().event_type, "ComputationHalted");
    assert!(
        run.events
            .iter()
            .any(|event| event.event_type == "InstructionAuthorized"
                && event.head_moved == HeadMoved::AuthorizationHead),
        "InstructionAuthorized must advance authorization_head through the three-ref writer"
    );

    let tape = Append::open(repo).expect("open tape");
    let heads = tape.head_set().unwrap().expect("post-genesis heads");
    assert_eq!(heads.tape_tip, run.halted_event_id);
    assert_eq!(heads.accepted_head, genesis_id);
    assert_eq!(
        heads.authorization_head,
        run.events
            .iter()
            .rev()
            .find(|event| event.event_type == "InstructionAuthorized")
            .map(|event| event.event_id.clone())
    );

    let start = run
        .events
        .iter()
        .find(|event| event.event_type == "ComputationStarted")
        .unwrap();
    let start_body = body(repo, &start.event_id);
    assert_eq!(
        start_body["event_schema_id"],
        json!("computation_started.v1")
    );
    assert_eq!(
        start_body["payload"]["state_hash"],
        json!(state_hash_v1(&initial).unwrap())
    );

    let reduced = reduce_witness_tape(repo, &run.halted_event_id).expect("reduce witness");
    assert_eq!(reduced.program_id, "program:add-one");
    assert_eq!(reduced.final_state, run.final_state);
    assert_eq!(
        reduced.final_state_hash,
        state_hash_v1(&run.final_state).unwrap()
    );
    assert_eq!(
        reduced
            .events
            .iter()
            .map(|event| &event.event_type)
            .collect::<Vec<_>>(),
        run.events
            .iter()
            .map(|event| &event.event_type)
            .collect::<Vec<_>>()
    );
    assert_eq!(
        reduced
            .events
            .iter()
            .filter(|event| event.event_type == "InstructionApplied")
            .count(),
        2,
        "INC and HALT both produce applied steps"
    );
}

#[test]
fn state_hash_v1_requires_the_two_counter_payload_shape() {
    assert_eq!(
        state_hash_v1(&MachineState::new(2, vec![3, 4], true).unwrap()).unwrap(),
        "sha256:fb982df0575545a024b2c7b2144aab0b7e5febd5da453cdf55dd5a3c50e68fa1"
    );
    assert!(state_hash_v1(&MachineState::new(0, vec![0, 0, 0], false).unwrap()).is_err());
}

fn _assert_event_shape(event: &WitnessEvent) {
    assert!(event.event_id.starts_with("mu:"));
    assert!(!event.event_type.is_empty());
}
