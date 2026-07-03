use serde_json::{Value, json};

use turing_git_tape::append::{Append, AppendRequest, committed_body_bytes};
use turing_git_tape::git;
use turing_witness::{
    CertificateClass, CounterMachineProgram, Instruction, MachineState, TerminalKind,
    emit_witness_execution, export_tc3_corpus, reduce_witness_tape,
};

fn h(hex: char) -> String {
    format!("sha256:{}", hex.to_string().repeat(64))
}

fn genesis(repo: &std::path::Path) {
    let tape = Append::open(repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": h('a')}),
        )
        .predicate_pass(),
    )
    .expect("genesis append");
}

fn body(repo: &std::path::Path, event_id: &str) -> Value {
    let bytes = committed_body_bytes(repo, event_id).expect("event body");
    serde_json::from_slice(&bytes).expect("event body JSON")
}

#[test]
fn budget_exhaustion_is_a_tape_terminal_reduced_from_budget_event() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");
    genesis(repo);

    let program = CounterMachineProgram::new(vec![Instruction::Inc {
        counter: 0,
        next_pc: 0,
    }])
    .expect("program loads");
    let certificate = json!({
        "class": CertificateClass::C1StaticHaltUnreachable.as_str(),
        "reachable_pcs": [0],
        "halt_pcs": [],
        "halt_reachable": false,
    });

    let run = emit_witness_execution(
        repo,
        "writer:tc3",
        "spin_static_halt_unreachable",
        &program,
        MachineState::new(0, vec![0, 0], false).unwrap(),
        3,
        Some(certificate),
    )
    .expect("budgeted execution emits");

    assert_eq!(run.terminal_kind, TerminalKind::BudgetExhausted);
    assert_eq!(run.terminal_event_type, "BudgetExhausted");
    assert_eq!(run.steps_executed, 3);
    assert_eq!(
        run.final_state,
        MachineState::new(0, vec![3, 0], false).unwrap()
    );
    assert_eq!(run.events.last().unwrap().event_type, "BudgetExhausted");

    let terminal = body(repo, &run.terminal_event_id);
    assert_eq!(terminal["event_schema_id"], json!("budget_exhausted.v1"));
    assert_eq!(
        terminal["payload"]["certificate"]["class"],
        json!("C1_STATIC_HALT_UNREACHABILITY")
    );

    let reduced = reduce_witness_tape(repo, &run.terminal_event_id).expect("reduce budget tape");
    assert_eq!(reduced.terminal_kind, TerminalKind::BudgetExhausted);
    assert_eq!(reduced.final_state, run.final_state);
    assert_eq!(reduced.steps_executed, run.steps_executed);
}

#[test]
fn tc3_export_writes_eight_bundles_manifest_and_seeded_fuzz() {
    let dir = tempfile::tempdir().expect("temp dir");

    let export = export_tc3_corpus(dir.path()).expect("tc3 export");

    assert_eq!(export.program_count, 8);
    assert_eq!(export.halting_program_count, 5);
    assert_eq!(export.nonhalting_program_count, 3);
    assert_eq!(
        export
            .runs
            .iter()
            .filter_map(|run| run.certificate_class)
            .collect::<Vec<_>>(),
        vec![
            CertificateClass::C1StaticHaltUnreachable,
            CertificateClass::C2StateRecurrence,
            CertificateClass::C3BudgetBounded,
        ]
    );

    let manifest: Value = serde_json::from_slice(
        &std::fs::read(dir.path().join("bundle_manifest.json")).expect("manifest bytes"),
    )
    .expect("manifest JSON");
    assert_eq!(manifest["program_count"], json!(8));
    assert_eq!(manifest["halting_program_count"], json!(5));
    assert_eq!(manifest["nonhalting_program_count"], json!(3));

    let sha_lines =
        std::fs::read_to_string(dir.path().join("bundle_sha256s.txt")).expect("bundle sha lines");
    assert_eq!(sha_lines.lines().count(), 8);
    for line in sha_lines.lines() {
        let (sha, rel) = line.split_once("  ").expect("sha line shape");
        assert_eq!(sha.len(), 64);
        assert!(dir.path().join(rel).is_file(), "missing bundle {rel}");
    }

    let fuzz_manifest: Value = serde_json::from_slice(
        &std::fs::read(dir.path().join("fuzz").join("fuzz_manifest.json"))
            .expect("fuzz manifest bytes"),
    )
    .expect("fuzz manifest JSON");
    assert_eq!(fuzz_manifest["seed"], json!(20260702));
    assert_eq!(fuzz_manifest["program_count"], json!(500));
    assert_eq!(fuzz_manifest["max_program_len"], json!(32));
    assert_eq!(fuzz_manifest["max_steps"], json!(4096));
}
