//! `tm_witness <repo> [program_id]` — build a fresh native-SHA-256 Tape at `<repo>` and
//! run one nontrivial two-counter Minsky-machine program (default `multiply_small`, from
//! the ALREADY-SHIPPED `turing-witness` crate's C1a fixture set) end-to-end through the
//! same governed append path. Prints a JSON summary line.

use std::path::PathBuf;

use c1b_governed_witness::run_tm_program;

fn main() {
    let mut args = std::env::args().skip(1);
    let repo: PathBuf = args
        .next()
        .expect("usage: tm_witness <repo> [program_id]")
        .into();
    let program_id = args.next().unwrap_or_else(|| "multiply_small".to_string());

    std::fs::create_dir_all(&repo).expect("create repo directory");
    turing_git_tape::git::init_sha256(&repo).expect("git init --object-format=sha256");

    let report =
        run_tm_program(&repo, "writer:c1b-tm", &program_id).expect("governed TM program run");

    println!(
        "{}",
        serde_json::json!({
            "program_id": report.program_id,
            "steps_executed_hint": report.steps_executed_hint,
            "final_state": report.final_state_summary,
            "governed_tape_events": report.governed_tape_events,
            "tape_tip": report.tape_tip,
            "accepted_head": report.accepted_head,
            "authorization_head": report.authorization_head,
            "repo": repo.display().to_string(),
        })
    );
}
