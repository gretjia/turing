//! FCE-R2 replay-determinism probe (Final Certification Eval, `09_FINAL_CERTIFICATION_EVALS.md`
//! "FCE-R2 - Replay determinism"): a tiny, real (no fixture JSON, no mocks) CLI wrapper around
//! the SAME production path `crates/turing-replay/tests/replay_determinism.rs` (SG-19) proves in
//! one process — split across INDEPENDENT OS-process invocations so an external harness (the
//! FCE-R2 Python scenario) can capture and byte-compare the canonical projection across
//! separate runs, instead of trusting a single process's in-memory `assert!`.
//!
//! What it does:
//! - `--build`: if `--repo` has no Tape yet, mint the SAME fixed 5-event deterministic sequence
//!   `replay_determinism.rs` uses (genesis SOVEREIGN_ACCEPT, a PROPOSAL, an AUTHORIZATION+PASS,
//!   a second SOVEREIGN_ACCEPT+PASS, a predicate-free OBSERVATION) via the ratified
//!   `turing-git-tape::Append` writer. If a Tape already exists at `--repo`, this is a no-op
//!   (idempotent) - re-running with `--build` against an already-built repo just replays it.
//! - Always: open `--repo`, read the live `tape_tip` ref, replay the frozen Tape via the
//!   production `turing_replay::replay_tape` fold, and write the canonical
//!   `turingos.jcs.v1` reconstruction bytes (`Reconstruction::to_jcs_bytes()`) to `--out`
//!   (or stdout if `--out` is omitted) - unmodified, so an external harness can sha256 the
//!   file directly and get the exact byte-identity SG-19 defines.
//!
//! This binary reads no clock, no randomness, no environment beyond its own argv and the frozen
//! Tape bytes on disk - the same determinism contract `turing_replay::replay_tape` documents.

use std::io::Write as _;
use std::path::PathBuf;
use std::process::ExitCode;

use turing_git_tape::append::{Append, AppendRequest};
use turing_git_tape::git;
use turing_replay::replay_tape;

fn main() -> ExitCode {
    let mut repo: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut build = false;

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--repo" => repo = args.next().map(PathBuf::from),
            "--out" => out = args.next().map(PathBuf::from),
            "--build" => build = true,
            other => {
                eprintln!("fce_r2_replay_probe: unknown argument {other:?}");
                return ExitCode::from(2);
            }
        }
    }

    let repo = match repo {
        Some(value) => value,
        None => {
            eprintln!("fce_r2_replay_probe: --repo <path> is required");
            return ExitCode::from(2);
        }
    };

    if let Err(message) = run(&repo, out.as_deref(), build) {
        eprintln!("fce_r2_replay_probe: {message}");
        return ExitCode::from(1);
    }
    ExitCode::SUCCESS
}

fn run(repo: &std::path::Path, out: Option<&std::path::Path>, build: bool) -> Result<(), String> {
    if !repo.join(".git").is_dir() {
        if !build {
            return Err(format!(
                "{} has no Tape (.git) yet and --build was not passed",
                repo.display()
            ));
        }
        std::fs::create_dir_all(repo)
            .map_err(|error| format!("create {}: {error}", repo.display()))?;
        git::init_sha256(repo)
            .map_err(|error| format!("git init --object-format=sha256: {error}"))?;
    }

    let tape = Append::open(repo).map_err(|error| format!("Append::open: {error}"))?;
    let tip = match tape
        .head_set()
        .map_err(|error| format!("head_set: {error}"))?
    {
        Some(head_set) => head_set.tape_tip,
        None => {
            if !build {
                return Err(format!(
                    "{} has an empty Tape and --build was not passed",
                    repo.display()
                ));
            }
            build_fixed_tape(&tape)?
        }
    };

    let reconstruction =
        replay_tape(repo, &tip).map_err(|error| format!("replay_tape: {error}"))?;
    let bytes = reconstruction
        .to_jcs_bytes()
        .map_err(|error| format!("to_jcs_bytes: {error}"))?;

    match out {
        Some(path) => {
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|error| format!("create {}: {error}", parent.display()))?;
            }
            std::fs::write(path, &bytes)
                .map_err(|error| format!("write {}: {error}", path.display()))?;
        }
        None => {
            std::io::stdout()
                .write_all(&bytes)
                .map_err(|error| format!("write stdout: {error}"))?;
        }
    }
    eprintln!("fce_r2_replay_probe: tape_tip={tip}");
    Ok(())
}

/// Mint the SAME fixed 5-event deterministic sequence as
/// `crates/turing-replay/tests/replay_determinism.rs::build_fixed_tape` (a genesis
/// SOVEREIGN_ACCEPT, a PROPOSAL, an AUTHORIZATION+PASS, a second SOVEREIGN_ACCEPT+PASS, and a
/// predicate-free OBSERVATION) via the ratified `Append` writer, and return the tip event id.
fn build_fixed_tape(tape: &Append) -> Result<String, String> {
    let steps: [(&'static str, serde_json::Value, bool); 5] = [
        (
            "SystemConstitutionAccepted",
            serde_json::json!({"constitution": "root", "n": 1}),
            true,
        ),
        (
            "GoalStateProposed",
            serde_json::json!({"goal": "ship m0", "n": 2}),
            true,
        ),
        (
            "AtomAuthorized",
            serde_json::json!({"atom": "fce_r2", "n": 3}),
            true,
        ),
        (
            "CandidateAccepted",
            serde_json::json!({"candidate": "replay", "n": 4}),
            true,
        ),
        (
            "PredicateEvaluated",
            serde_json::json!({"report": "not_run", "n": 5}),
            false,
        ),
    ];

    let mut last_event_id = String::new();
    for (event_type, payload, predicate_required) in steps {
        let mut request = AppendRequest::new(event_type, "writer:fce_r2_replay_probe", payload);
        if predicate_required {
            request = request.predicate_pass();
        }
        let receipt = tape
            .append(request)
            .map_err(|error| format!("append {event_type}: {error}"))?;
        last_event_id = receipt.event_id;
    }
    Ok(last_event_id)
}
