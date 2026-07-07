//! `rule110_witness <repo> [width] [steps]` — build a fresh native-SHA-256 Tape at
//! `<repo>` and run Rule 110 for `steps` generations over a `width`-wide fixed-zero-
//! boundary row (single seed `1` in the middle), with EVERY cell-update appended as a
//! governed tape event (see `c1b_governed_witness::run_rule110`). Prints:
//!   1. a JSON summary line (governed step/event counts, final heads),
//!   2. the ASCII spacetime diagram reconstructed LIVE from the run, and
//!   3. the ASCII spacetime diagram reconstructed PURELY FROM THE TAPE (independent
//!      read path), plus a PASS/FAIL line confirming the two are byte-identical.

use std::path::PathBuf;

use c1b_governed_witness::{
    reconstruct_rows_from_tape, render_ascii_diagram, rule110_predicate_selftest, run_rule110,
};

fn main() {
    let mut args = std::env::args().skip(1);
    let repo: PathBuf = args
        .next()
        .expect("usage: rule110_witness <repo> [width] [steps]")
        .into();
    let width: usize = args
        .next()
        .map(|s| s.parse().expect("width must be a number"))
        .unwrap_or(31);
    let steps: usize = args
        .next()
        .map(|s| s.parse().expect("steps must be a number"))
        .unwrap_or(16);

    if let Err(e) = rule110_predicate_selftest() {
        eprintln!("PREDICATE SELF-TEST FAILED: {e}");
        std::process::exit(1);
    }
    println!("predicate_selftest: PASS (forged proposals rejected for all 8 truth-table cases)");

    std::fs::create_dir_all(&repo).expect("create repo directory");
    turing_git_tape::git::init_sha256(&repo).expect("git init --object-format=sha256");

    let mut initial_row = vec![0u8; width];
    initial_row[width / 2] = 1;

    let report = run_rule110(&repo, "writer:c1b-rule110", initial_row, steps)
        .expect("governed Rule 110 run");

    println!(
        "{}",
        serde_json::json!({
            "rule": 110,
            "width": report.width,
            "steps": report.steps,
            "governed_cell_updates": report.governed_cell_updates,
            "governed_tape_events": report.governed_tape_events,
            "tape_tip": report.tape_tip,
            "accepted_head": report.accepted_head,
            "authorization_head": report.authorization_head,
            "repo": repo.display().to_string(),
        })
    );

    println!("\n--- ASCII spacetime diagram (live run) ---");
    print!("{}", render_ascii_diagram(&report.rows));

    let reconstructed = reconstruct_rows_from_tape(&repo, &report.tape_tip)
        .expect("reconstruct rows purely from tape");
    println!("\n--- ASCII spacetime diagram (reconstructed FROM TAPE ALONE) ---");
    print!("{}", render_ascii_diagram(&reconstructed));

    if reconstructed == report.rows {
        println!(
            "\ntape_reconstruction_check: PASS ({} generations, byte-identical to the live run)",
            reconstructed.len()
        );
    } else {
        eprintln!("\ntape_reconstruction_check: FAIL (tape-derived rows diverge from the live run)");
        std::process::exit(1);
    }
}
