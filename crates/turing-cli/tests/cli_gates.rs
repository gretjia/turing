use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

use serde_json::json;
use turing_git_tape::{
    append::{Append, AppendRequest, CommittedReceipt},
    git,
};

fn turing() -> Command {
    Command::new(env!("CARGO_BIN_EXE_turing"))
}

const SAMPLE_EVENT_ID: &str = "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const REF_NAMES: [&str; 3] = [
    "refs/turingos/tape_tip",
    "refs/turingos/authorization_head",
    "refs/turingos/accepted_head",
];

#[derive(Debug, Clone, PartialEq, Eq)]
struct HeadTriplet(Vec<Option<String>>);

#[derive(Debug, Clone)]
struct OperatorCommandCase {
    label: &'static str,
    args: Vec<String>,
    stdin: Option<String>,
    expected: &'static str,
}

impl OperatorCommandCase {
    fn argv(label: &'static str, args: Vec<String>, expected: &'static str) -> Self {
        OperatorCommandCase {
            label,
            args,
            stdin: None,
            expected,
        }
    }

    fn stdin(
        label: &'static str,
        args: Vec<String>,
        stdin: impl Into<String>,
        expected: &'static str,
    ) -> Self {
        OperatorCommandCase {
            label,
            args,
            stdin: Some(stdin.into()),
            expected,
        }
    }
}

fn read_ref(repo: &Path, ref_name: &str) -> Option<String> {
    let output = Command::new("git")
        .args([
            "-C",
            repo.to_str().expect("UTF-8 repo path"),
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            ref_name,
        ])
        .output()
        .expect("git rev-parse ref");
    if !output.status.success() {
        assert!(
            output.stdout.is_empty(),
            "unexpected rev-parse failure for {ref_name}: {output:?}"
        );
        return None;
    }
    Some(
        String::from_utf8(output.stdout)
            .expect("rev-parse stdout UTF-8")
            .trim()
            .to_string(),
    )
}

fn read_heads(repo: &Path) -> HeadTriplet {
    HeadTriplet(
        REF_NAMES
            .iter()
            .map(|ref_name| read_ref(repo, ref_name))
            .collect(),
    )
}

fn run_operator_case(case: &OperatorCommandCase) -> String {
    let output = if let Some(stdin) = &case.stdin {
        let mut child = turing()
            .args(&case.args)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .spawn()
            .unwrap_or_else(|error| panic!("spawn {} failed: {error}", case.label));
        {
            use std::io::Write;
            child
                .stdin
                .as_mut()
                .expect("stdin")
                .write_all(stdin.as_bytes())
                .expect("write stdin");
        }
        child
            .wait_with_output()
            .unwrap_or_else(|error| panic!("wait {} failed: {error}", case.label))
    } else {
        turing()
            .args(&case.args)
            .output()
            .unwrap_or_else(|error| panic!("run {} failed: {error}", case.label))
    };
    assert!(
        output.status.success(),
        "{} failed: stdout={} stderr={}",
        case.label,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(
        stdout.contains(case.expected),
        "{} missing {:?}: {stdout}",
        case.label,
        case.expected
    );
    stdout
}

fn ask_case(
    label: &'static str,
    utterance: &'static str,
    expected: &'static str,
) -> OperatorCommandCase {
    OperatorCommandCase::argv(
        label,
        vec!["ask".to_string(), utterance.to_string()],
        expected,
    )
}

fn operator_command_matrix(repo: &Path, bundle: &Path) -> Vec<OperatorCommandCase> {
    let repo_arg = repo.to_str().expect("UTF-8 repo path").to_string();
    let bundle_arg = bundle.to_str().expect("UTF-8 bundle path").to_string();
    let digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    let mut cases = vec![
        OperatorCommandCase::argv("help", vec!["--help".to_string()], "Operator Console v1"),
        OperatorCommandCase::argv(
            "help commands",
            vec!["help".to_string(), "commands".to_string()],
            "operator_tool_manifest.v1",
        ),
        OperatorCommandCase::argv(
            "status micro-git",
            vec![
                "status".to_string(),
                "--micro-git".to_string(),
                repo_arg.clone(),
            ],
            "operator_view_snapshot.v1",
        ),
        OperatorCommandCase::argv(
            "panoview micro-git",
            vec![
                "panoview".to_string(),
                "--micro-git".to_string(),
                repo_arg.clone(),
            ],
            "guarded_micro_tape_read",
        ),
        OperatorCommandCase::argv(
            "explain blocker micro-git",
            vec![
                "explain".to_string(),
                "blocker".to_string(),
                "--micro-git".to_string(),
                repo_arg.clone(),
            ],
            "EXPLAIN_BLOCKER",
        ),
        OperatorCommandCase::argv(
            "explain event id micro-git",
            vec![
                "explain".to_string(),
                "event".to_string(),
                SAMPLE_EVENT_ID.to_string(),
                "--micro-git".to_string(),
                repo_arg,
            ],
            "EXPLAIN_EVENT",
        ),
        OperatorCommandCase::argv(
            "status micro-bundle",
            vec![
                "status".to_string(),
                "--micro-bundle".to_string(),
                bundle_arg.clone(),
            ],
            "guarded_micro_tape_read",
        ),
        OperatorCommandCase::argv(
            "panoview micro-bundle",
            vec![
                "panoview".to_string(),
                "--micro-bundle".to_string(),
                bundle_arg.clone(),
            ],
            "guarded_micro_tape_read",
        ),
        OperatorCommandCase::argv(
            "explain event micro-bundle",
            vec![
                "explain".to_string(),
                "event".to_string(),
                "--micro-bundle".to_string(),
                bundle_arg,
            ],
            "EXPLAIN_EVENT",
        ),
        OperatorCommandCase::stdin(
            "operator stdin script",
            vec!["operator".to_string()],
            format!("status\npanoview\nexplain event {SAMPLE_EVENT_ID}\nquit\n"),
            "EXPLAIN_EVENT",
        ),
        OperatorCommandCase::argv(
            "approval preview",
            vec![
                "approval".to_string(),
                "preview".to_string(),
                "--approval-id".to_string(),
                "ap_m6_p4_preview".to_string(),
                "--authority-epoch".to_string(),
                "7".to_string(),
                "--action".to_string(),
                "capsule_approve".to_string(),
                "--subject".to_string(),
                "wc_m6_p4".to_string(),
                "--risk".to_string(),
                "P2".to_string(),
                "--evidence-digest".to_string(),
                digest.to_string(),
                "--signature-route".to_string(),
                "none".to_string(),
            ],
            "writes_micro_truth=false",
        ),
    ];
    cases.extend([
        ask_case("ask view status", "status", "VIEW_STATUS"),
        ask_case("ask view panoview", "panoview", "VIEW_PANOVIEW"),
        ask_case("ask explain event", "event details", "EXPLAIN_EVENT"),
        ask_case("ask explain blocker", "blocker", "EXPLAIN_BLOCKER"),
        ask_case("ask replay verify", "replay verify", "REPLAY_VERIFY"),
        ask_case(
            "ask audit invariants",
            "audit invariants",
            "AUDIT_INVARIANTS",
        ),
        ask_case("ask propose intent", "intent proposal", "PROPOSE_INTENT"),
        ask_case("ask propose goal", "goal proposal", "PROPOSE_GOAL"),
        ask_case("ask propose capsule", "capsule proposal", "PROPOSE_CAPSULE"),
        ask_case("ask approve capsule", "approve capsule", "APPROVE_CAPSULE"),
        ask_case("ask dispatch worker", "dispatch worker", "DISPATCH_WORKER"),
        ask_case("ask observe capsule", "observe capsule", "OBSERVE_CAPSULE"),
        ask_case(
            "ask reject candidate",
            "reject candidate",
            "REJECT_CANDIDATE",
        ),
        ask_case(
            "ask request macro auth",
            "request macro authorization",
            "REQUEST_MACRO_AUTH",
        ),
        ask_case(
            "ask approve candidate",
            "approve candidate",
            "APPROVE_CANDIDATE",
        ),
        ask_case("ask help", "help", "HELP"),
    ]);
    cases
}

#[cfg(unix)]
struct ReadOnlyTree {
    original_modes: Vec<(PathBuf, u32)>,
}

#[cfg(unix)]
impl ReadOnlyTree {
    fn make(root: &Path) -> Self {
        let mut paths = Vec::new();
        collect_paths(root, &mut paths);
        let mut original_modes = Vec::new();
        for path in paths {
            let metadata = std::fs::symlink_metadata(&path).expect("metadata");
            if metadata.file_type().is_symlink() {
                continue;
            }
            let mode = metadata.permissions().mode();
            original_modes.push((path.clone(), mode));
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(mode & !0o222))
                .unwrap_or_else(|error| panic!("chmod readonly {}: {error}", path.display()));
        }
        ReadOnlyTree { original_modes }
    }
}

#[cfg(unix)]
impl Drop for ReadOnlyTree {
    fn drop(&mut self) {
        for (path, mode) in &self.original_modes {
            let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(*mode));
        }
    }
}

#[cfg(unix)]
fn collect_paths(path: &Path, out: &mut Vec<PathBuf>) {
    out.push(path.to_path_buf());
    if let Ok(metadata) = std::fs::symlink_metadata(path) {
        if metadata.is_dir() {
            for entry in std::fs::read_dir(path).expect("read dir") {
                collect_paths(&entry.expect("dir entry").path(), out);
            }
        }
    }
}

fn sample_micro_repo() -> (tempfile::TempDir, CommittedReceipt) {
    let dir = tempfile::tempdir().expect("temp dir");
    git::init_sha256(dir.path()).expect("sha256 git init");
    let tape = Append::open(dir.path()).expect("append open");
    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:hci-test",
                json!({"constitution_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}),
            )
            .predicate_pass(),
        )
        .expect("genesis append");
    let proposal = tape
        .append(
            AppendRequest::new(
                "GoalStateProposed",
                "writer:hci-test",
                json!({"goal_id":"goal_hci_real_tape","intent":"exercise operator HCI real MicroTape source"}),
            )
            .predicate_pass(),
        )
        .expect("proposal append");
    assert_eq!(proposal.accepted_head_after, genesis.event_id);
    (dir, proposal)
}

fn sample_micro_bundle() -> (tempfile::TempDir, std::path::PathBuf, CommittedReceipt) {
    let (repo, proposal) = sample_micro_repo();
    let bundle = repo.path().join("micro_tape.bundle");
    let output = Command::new("git")
        .args([
            "-C",
            repo.path().to_str().expect("UTF-8 path"),
            "bundle",
            "create",
            bundle.to_str().expect("UTF-8 bundle path"),
            "refs/turingos/tape_tip",
            "refs/turingos/accepted_head",
        ])
        .output()
        .expect("git bundle create");
    assert!(output.status.success(), "bundle create failed: {output:?}");
    (repo, bundle, proposal)
}

#[test]
fn help_lists_operator_console_commands() {
    let output = turing().arg("--help").output().expect("run help");
    assert!(output.status.success(), "help failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");

    for text in [
        "Operator Console v1",
        "status",
        "--micro-git",
        "panoview",
        "explain",
        "ask",
        "operator",
        "typed_command.v1",
        "operator_view_snapshot.v1",
    ] {
        assert!(stdout.contains(text), "help missing {text:?}: {stdout}");
    }
    assert!(!stdout.contains("human approved"));
    assert!(!stdout.contains("class closed"));
}

#[test]
fn help_commands_topic_lists_closed_typed_command_contract() {
    let help = turing().arg("--help").output().expect("run help");
    assert!(help.status.success(), "help failed: {help:?}");
    let default_stdout = String::from_utf8(help.stdout).expect("stdout UTF-8");

    let output = turing()
        .args(["help", "commands"])
        .output()
        .expect("run help commands");
    assert!(output.status.success(), "help commands failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");

    assert_ne!(stdout, default_stdout);
    assert!(stdout.contains("topic=commands"));
    assert!(stdout.contains("operator_tool_manifest.v1"));
    assert!(stdout.contains("typed_command.v1"));
    assert!(stdout.contains("VIEW_STATUS"));
    assert!(stdout.contains("APPROVE_CANDIDATE"));
    assert!(stdout.contains("writes_truth=false"));
}

#[test]
fn status_and_panoview_can_read_real_micro_git_heads() {
    let (repo, proposal) = sample_micro_repo();
    let repo_arg = repo.path().to_str().expect("UTF-8 path");

    let status = turing()
        .args(["status", "--micro-git", repo_arg])
        .output()
        .expect("run status real micro git");
    assert!(status.status.success(), "status failed: {status:?}");
    let stdout = String::from_utf8(status.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("operator_view_snapshot.v1"));
    assert!(stdout.contains("source_kind=guarded_micro_tape_read"));
    assert!(stdout.contains(&format!("tape_tip={}", proposal.event_id)));
    assert!(stdout.contains(&format!("accepted_head={}", proposal.accepted_head_after)));
    assert!(stdout.contains("can_write_truth=false"));

    let panoview = turing()
        .args(["panoview", "--micro-git", repo_arg])
        .output()
        .expect("run panoview real micro git");
    assert!(panoview.status.success(), "panoview failed: {panoview:?}");
    let stdout = String::from_utf8(panoview.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("source=guarded_micro_tape_read"));
    assert!(stdout.contains(&format!("tape_tip={}", proposal.event_id)));
    assert!(stdout.contains("authorization_head=null"));
    assert!(stdout.contains(&format!("accepted_head={}", proposal.accepted_head_after)));
    assert!(!stdout.contains("accepted head="));
}

#[test]
fn explain_can_use_real_micro_git_snapshot_hash() {
    let (repo, _proposal) = sample_micro_repo();
    let repo_arg = repo.path().to_str().expect("UTF-8 path");

    let output = turing()
        .args(["explain", "blocker", "--micro-git", repo_arg])
        .output()
        .expect("run explain real micro git");

    assert!(output.status.success(), "explain failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("typed_command.v1"));
    assert!(stdout.contains("source_kind=guarded_micro_tape_read"));
    assert!(stdout.contains("operator_view_snapshot.v1=sha256:"));
}

#[test]
fn status_can_read_micro_tape_bundle_directly() {
    let (_repo, bundle, proposal) = sample_micro_bundle();
    let bundle_arg = bundle.to_str().expect("UTF-8 path");

    let output = turing()
        .args(["status", "--micro-bundle", bundle_arg])
        .output()
        .expect("run status bundle");

    assert!(output.status.success(), "status bundle failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("source_kind=guarded_micro_tape_read"));
    assert!(stdout.contains(&format!("tape_tip={}", proposal.event_id)));
    assert!(stdout.contains(&format!("accepted_head={}", proposal.accepted_head_after)));
}

#[test]
fn operator_command_matrix_conserves_all_three_micro_tape_heads() {
    let (repo, bundle, _proposal) = sample_micro_bundle();
    let before = read_heads(repo.path());

    for case in operator_command_matrix(repo.path(), &bundle) {
        let stdout = run_operator_case(&case);
        assert!(
            !stdout.contains("writes_truth=true") && !stdout.contains("writes_micro_truth=true"),
            "{} claimed write authority: {stdout}",
            case.label
        );
        let after = read_heads(repo.path());
        assert_eq!(
            before, after,
            "{} moved a MicroTape head; before={before:?} after={after:?}",
            case.label
        );
    }
}

#[cfg(unix)]
#[test]
fn operator_command_matrix_passes_on_readonly_micro_tape_filesystem() {
    let (repo, bundle, _proposal) = sample_micro_bundle();
    let before = read_heads(repo.path());
    {
        let _readonly = ReadOnlyTree::make(repo.path());
        for case in operator_command_matrix(repo.path(), &bundle) {
            run_operator_case(&case);
            let after = read_heads(repo.path());
            assert_eq!(
                before, after,
                "{} moved a MicroTape head on a read-only fixture; before={before:?} after={after:?}",
                case.label
            );
        }
    }
    assert_eq!(
        before,
        read_heads(repo.path()),
        "readonly matrix changed heads after permissions restored"
    );
}

#[test]
fn status_panoview_and_explain_render_operator_snapshot_contract() {
    for (args, expected) in [
        (
            &["demo", "status"][..],
            vec![
                "DEMO FIXTURE",
                "operator_view_snapshot.v1",
                "operator_state=Healthy",
                "tape_tip=mu:",
                "authorization_head=",
                "accepted_head=mu:",
                "IMPLEMENTER_ADDRESSED",
            ],
        ),
        (
            &["demo", "panoview"][..],
            vec![
                "DEMO FIXTURE",
                "lanes:",
                "tape_tip=",
                "authorization_head=",
                "accepted_head=",
                "warnings:",
                "safe commands:",
                "VIEW_STATUS",
                "APPROVE_CANDIDATE approval_required",
            ],
        ),
        (
            &["explain", "blocker"][..],
            vec![
                "typed_command.v1",
                "EXPLAIN_BLOCKER",
                "evidence",
                "replay",
                "human_signature_required",
            ],
        ),
    ] {
        let output = turing().args(args).output().expect("run operator command");
        assert!(
            output.status.success(),
            "command {args:?} failed: {output:?}"
        );
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        for text in expected {
            assert!(
                stdout.contains(text),
                "command {args:?} missing {text:?}: {stdout}"
            );
        }
        assert!(!stdout.contains("production ready"));
        assert!(!stdout.contains("human ratified"));
        assert!(!stdout.contains("class closed"));
    }
}

#[test]
fn ask_routes_natural_language_to_advisory_turn_trace_only() {
    let output = turing()
        .args(["ask", "请批准这个 candidate"])
        .output()
        .expect("run ask");

    assert!(output.status.success(), "ask failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("operator_turn_trace.v1"));
    assert!(stdout.contains("APPROVE_CANDIDATE"));
    assert!(stdout.contains("approval_required=true"));
    assert!(stdout.contains("writes_truth=false"));
    assert!(stdout.contains("advisory_confidence="));
    assert!(stdout.contains("human_signature_required"));
    assert!(!stdout.contains("shell"));
    assert!(!stdout.contains("dispatch_executed"));
}

#[test]
fn ask_routes_closed_verbs_without_falling_back_to_help() {
    for (utterance, expected) in [
        ("replay verify the current view", "REPLAY_VERIFY"),
        ("audit invariants now", "AUDIT_INVARIANTS"),
        ("propose intent to rescue the issue", "PROPOSE_INTENT"),
        ("propose goal repair django", "PROPOSE_GOAL"),
        ("propose capsule for django fix", "PROPOSE_CAPSULE"),
        (
            "explain event mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "EXPLAIN_EVENT",
        ),
    ] {
        let output = turing()
            .args(["ask", utterance])
            .output()
            .expect("run ask route");
        assert!(
            output.status.success(),
            "ask {utterance:?} failed: {output:?}"
        );
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        assert!(
            stdout.contains(expected),
            "utterance {utterance:?} routed wrong: {stdout}"
        );
        assert!(
            !stdout.contains("selected_verb=HELP"),
            "utterance {utterance:?} fell back to HELP: {stdout}"
        );
        assert!(stdout.contains("writes_truth=false"));
    }
}

#[test]
fn ask_routes_reject_candidate_without_inventing_approval() {
    let output = turing()
        .args(["ask", "reject candidate cand1"])
        .output()
        .expect("run ask reject");

    assert!(output.status.success(), "ask reject failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("REJECT_CANDIDATE"));
    assert!(!stdout.contains("APPROVE_CANDIDATE"));
    assert!(stdout.contains("approval_required=true"));
    assert!(stdout.contains("writes_truth=false"));
}

#[test]
fn operator_interactive_wrapper_uses_same_snapshot_contract() {
    let mut child = turing()
        .arg("operator")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .spawn()
        .expect("spawn operator");
    {
        use std::io::Write;
        let stdin = child.stdin.as_mut().expect("stdin");
        writeln!(stdin, "status").expect("write status");
        writeln!(stdin, "help").expect("write help");
        writeln!(stdin, "quit").expect("write quit");
    }
    let output = child.wait_with_output().expect("operator output");

    assert!(output.status.success(), "operator failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("operator_view_snapshot.v1"));
    assert!(stdout.contains("typed_command.v1"));
    assert!(stdout.contains("VIEW_STATUS"));
    assert!(stdout.contains("HELP"));
    assert!(!stdout.contains("accepted because"));
}

#[test]
fn operator_interactive_routes_explain_event_without_help_fallback() {
    let mut child = turing()
        .arg("operator")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .spawn()
        .expect("spawn operator");
    {
        use std::io::Write;
        let stdin = child.stdin.as_mut().expect("stdin");
        writeln!(
            stdin,
            "explain event mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        .expect("write explain event");
        writeln!(stdin, "quit").expect("write quit");
    }
    let output = child.wait_with_output().expect("operator output");

    assert!(output.status.success(), "operator failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("EXPLAIN_EVENT"));
    assert!(!stdout.contains("selected_verb=HELP"));
}

#[test]
fn explain_event_can_target_event_id_with_replay_evidence() {
    let output = turing()
        .args([
            "explain",
            "event",
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ])
        .output()
        .expect("run explain event id");

    assert!(output.status.success(), "explain event failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("typed_command.v1"));
    assert!(stdout.contains("EXPLAIN_EVENT"));
    assert!(
        stdout.contains(
            "event_id=mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
    );
    assert!(stdout.contains("source_heads=tape_tip,authorization_head,accepted_head"));
    assert!(stdout.contains("replay="));
    assert!(stdout.contains("writes_truth=false"));
}

#[test]
fn replay_market_pput_and_audit_commands_are_executable() {
    for (args, expected) in [
        (&["replay", "--verify"][..], "replay: verified"),
        (
            &["market", "replay", "--verify"][..],
            "market replay: verified",
        ),
        (&["pput", "replay", "--verify"][..], "pput replay: verified"),
        (&["audit", "invariants"][..], "audit invariants: pass"),
        (&["audit", "market"][..], "audit market: pass"),
        (&["audit", "pput"][..], "audit pput: pass"),
    ] {
        let output = turing().args(args).output().expect("run turing command");
        assert!(
            output.status.success(),
            "command {args:?} failed: {output:?}"
        );
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        assert!(
            stdout.contains(expected),
            "stdout missing {expected:?}: {stdout}"
        );
        assert!(
            !stdout.contains("accepted because CI passed"),
            "CLI must not imply macro green is truth"
        );
    }
}

#[test]
fn unknown_command_fails_closed() {
    let output = turing()
        .arg("market-loop")
        .output()
        .expect("run unknown command");
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    // F2: the ~500-char grammar dump is gone from error output; every parse error is 3 lines
    // (what failed / why / the one next command), and the full grammar moves behind
    // `turing help commands` only.
    assert!(stderr.contains("Unknown command: market-loop"));
    assert!(stderr.contains("Run: turing help commands"));
    assert_eq!(stderr.trim_end().lines().count(), 3, "stderr: {stderr:?}");
    assert!(!stderr.contains("supported: status ["));
    assert!(!stderr.contains("os error"));
}

#[test]
fn bare_status_and_panoview_fail_closed_without_a_configured_tape() {
    // F1 default-command honesty: with no --micro-git/--micro-bundle, no TURING_MICRO_GIT, and
    // no configured project default, bare `status`/`panoview` must NOT silently run the
    // synthetic economy demo — they fail closed with the 3-line pattern and exit 2.
    let scratch_cwd = tempfile::tempdir().expect("scratch cwd");
    for args in [&["status"][..], &["panoview"][..]] {
        let output = turing()
            .args(args)
            .current_dir(scratch_cwd.path())
            .env_remove("TURING_MICRO_GIT")
            .output()
            .unwrap_or_else(|error| panic!("run {args:?} failed: {error}"));
        assert!(!output.status.success(), "{args:?} unexpectedly succeeded");
        assert_eq!(output.status.code(), Some(2), "{args:?} exit code");
        assert!(output.stdout.is_empty(), "{args:?} stdout: {output:?}");
        let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
        assert!(stderr.contains("No tape configured."));
        assert!(stderr.contains(&format!("turing demo {}", args[0])));
        assert!(stderr.contains(&format!("turing {} --micro-git <path>", args[0])));
        assert_eq!(stderr.trim_end().lines().count(), 3, "stderr: {stderr:?}");
    }
}

#[test]
fn bare_status_resolves_turing_micro_git_env_instead_of_the_demo() {
    let (repo, proposal) = sample_micro_repo();
    let output = turing()
        .arg("status")
        .env("TURING_MICRO_GIT", repo.path())
        .output()
        .expect("run status with TURING_MICRO_GIT");
    assert!(output.status.success(), "status failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("source_kind=guarded_micro_tape_read"));
    assert!(stdout.contains(&format!("tape_tip={}", proposal.event_id)));
    assert!(!stdout.contains("DEMO FIXTURE"));
}

#[test]
fn demo_subcommands_render_the_same_contract_with_an_honest_header() {
    for args in [
        &["demo", "status"][..],
        &["demo", "panoview"][..],
        &["demo", "replay"][..],
    ] {
        let output = turing()
            .args(args)
            .output()
            .unwrap_or_else(|error| panic!("run {args:?} failed: {error}"));
        assert!(output.status.success(), "{args:?} failed: {output:?}");
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        assert!(
            stdout.starts_with("DEMO FIXTURE"),
            "{args:?} missing demo header: {stdout}"
        );
        assert!(stdout.to_lowercase().contains("demo"));
    }
}

#[test]
fn per_subcommand_help_is_scoped_and_discoverable() {
    for (args, expected) in [
        (&["status", "--help"][..], "turing status"),
        (&["panoview", "--help"][..], "turing panoview"),
        (&["explain", "--help"][..], "turing explain"),
        (&["ask", "--help"][..], "turing ask"),
        (&["demo", "--help"][..], "turing demo"),
        (&["doctor", "--help"][..], "turing doctor"),
    ] {
        let output = turing()
            .args(args)
            .output()
            .unwrap_or_else(|error| panic!("run {args:?} failed: {error}"));
        assert!(output.status.success(), "{args:?} failed: {output:?}");
        let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
        assert!(stdout.contains(expected), "{args:?} stdout: {stdout}");
        assert!(stdout.contains("Usage:"), "{args:?} stdout: {stdout}");
    }

    // `ask --help` must not be swallowed by the `ask <utterance>` catch-all.
    let output = turing()
        .args(["ask", "--help"])
        .output()
        .expect("run ask --help");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(!stdout.contains("operator_turn_trace.v1"));
}

#[test]
fn doctor_passes_against_a_healthy_real_tape_and_supports_ci_mode() {
    let (repo, proposal) = sample_micro_repo();
    let repo_arg = repo.path().to_str().expect("UTF-8 repo path");

    let output = turing()
        .args(["doctor", "--micro-git", repo_arg])
        .output()
        .expect("run doctor");
    assert!(output.status.success(), "doctor failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("PASS  binary_deps"));
    assert!(stdout.contains("PASS  tape_resolved"));
    assert!(stdout.contains("PASS  replay_verify"));
    assert!(stdout.contains(&format!("accepted_head={}", proposal.accepted_head_after)));
    assert!(stdout.contains("doctor: PASS (3/3 checks)"));

    let ci_output = turing()
        .args(["doctor", "--micro-git", repo_arg, "--ci"])
        .output()
        .expect("run doctor --ci");
    assert!(
        ci_output.status.success(),
        "doctor --ci failed: {ci_output:?}"
    );
    let ci_stdout = String::from_utf8(ci_output.stdout).expect("stdout UTF-8");
    for line in ci_stdout.lines() {
        assert!(
            line.starts_with("check=") || line.starts_with("doctor:"),
            "unexpected --ci line: {line:?}"
        );
    }
    assert!(ci_stdout.contains("check=binary_deps status=PASS"));
    assert!(ci_stdout.contains("check=tape_resolved status=PASS"));
    assert!(ci_stdout.contains("check=replay_verify status=PASS"));
}

#[test]
fn doctor_fails_loud_and_nonzero_on_a_tampered_tape() {
    let (repo, _proposal) = sample_micro_repo();
    let repo_arg = repo.path().to_str().expect("UTF-8 repo path");

    // Tamper: point refs/turingos/tape_tip at a commit that is not a real MicroTape event (a
    // bare empty-tree commit) — the guarded HeadSet read fails closed on the incoherent ref
    // before replay ever gets a chance to run.
    let empty_tree = Command::new("git")
        .args([
            "-C",
            repo_arg,
            "hash-object",
            "-w",
            "-t",
            "tree",
            "/dev/null",
        ])
        .output()
        .expect("hash-object");
    assert!(
        empty_tree.status.success(),
        "hash-object failed: {empty_tree:?}"
    );
    let tree_oid = String::from_utf8(empty_tree.stdout).expect("UTF-8 oid");
    let tree_oid = tree_oid.trim();
    let bogus_commit = Command::new("git")
        .args([
            "-C",
            repo_arg,
            "commit-tree",
            tree_oid,
            "-m",
            "fix: tampered commit is not a MicroTape event",
        ])
        .output()
        .expect("commit-tree");
    assert!(
        bogus_commit.status.success(),
        "commit-tree failed: {bogus_commit:?}"
    );
    let bogus_oid = String::from_utf8(bogus_commit.stdout).expect("UTF-8 oid");
    let bogus_oid = bogus_oid.trim();
    let update_ref = Command::new("git")
        .args([
            "-C",
            repo_arg,
            "update-ref",
            "refs/turingos/tape_tip",
            bogus_oid,
        ])
        .output()
        .expect("update-ref");
    assert!(
        update_ref.status.success(),
        "update-ref failed: {update_ref:?}"
    );

    let output = turing()
        .args(["doctor", "--micro-git", repo_arg, "--ci"])
        .output()
        .expect("run doctor on tampered tape");
    assert!(
        !output.status.success(),
        "doctor unexpectedly passed: {output:?}"
    );
    assert_eq!(output.status.code(), Some(2));
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    // The guarded HeadSet read (Ring-2, SG-18) catches the torn/incoherent ref before replay
    // ever runs — an even earlier, stricter tamper detection than the replay fold itself.
    assert!(stderr.contains("check=binary_deps status=PASS"));
    assert!(stderr.contains("check=tape_resolved status=FAIL"));
    assert!(stderr.contains("doctor: FAIL"));
    assert!(!stderr.contains("os error"));
}

#[test]
fn replay_verify_and_audit_invariants_support_micro_git_against_a_real_tape() {
    let (repo, proposal) = sample_micro_repo();
    let repo_arg = repo.path().to_str().expect("UTF-8 repo path");

    let replay = turing()
        .args(["replay", "--verify", "--micro-git", repo_arg])
        .output()
        .expect("run replay --verify --micro-git");
    assert!(replay.status.success(), "replay failed: {replay:?}");
    let stdout = String::from_utf8(replay.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("replay: verified"));
    assert!(stdout.contains("source=guarded_micro_tape_read"));
    assert!(stdout.contains(&format!("accepted_head={}", proposal.accepted_head_after)));

    let audit = turing()
        .args(["audit", "invariants", "--micro-git", repo_arg])
        .output()
        .expect("run audit invariants --micro-git");
    assert!(audit.status.success(), "audit failed: {audit:?}");
    let stdout = String::from_utf8(audit.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("audit invariants: pass"));
    assert!(stdout.contains(&format!("accepted_head={}", proposal.accepted_head_after)));
}

/// E0.3 regression guard: `turing market replay --verify` / `turing audit market` must verify a
/// REAL tape when `--micro-git` is passed, and `market_settled_count` must be COMPUTED from that
/// tape — never the hardcoded `settled=1` literal `run_new_project_agent_economy_demo()` always
/// produces. This tape carries THREE markets (two settled, one still open) specifically so a
/// hardcoded "1" cannot accidentally pass the assertion.
#[test]
fn market_replay_and_audit_market_support_micro_git_against_a_real_tape() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("sha256 git init");
    let tape = Append::open(repo).expect("append open");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:cli-test",
            json!({"constitution_digest": "sha256:".to_string() + &"7".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");

    for (market_id, pool) in [("mkt_a", "100"), ("mkt_b", "100"), ("mkt_c", "100")] {
        tape.append(
            AppendRequest::new(
                "MarketCreated",
                "writer:cli-test",
                json!({
                    "schema_id": "market_created.v1",
                    "event_type": "MarketCreated",
                    "head_effect": "PRESERVE",
                    "market_id": market_id,
                    "initial_pool_y": pool,
                    "initial_pool_n": pool,
                    "k": "10000",
                    "truth_status": "statistical_signal_only"
                }),
            )
            .predicate_pass(),
        )
        .expect("append market created");
    }

    // An AMMSwapExecuted against mkt_a: E0.1/E0.2 regression guard, exercising the
    // registry-canonical "AMMSwapExecuted" cased event on the real replay path.
    tape.append(
        AppendRequest::new(
            "AMMSwapExecuted",
            "writer:cli-test",
            json!({
                "schema_id": "amm_swap_executed.v1",
                "market_id": "mkt_a",
                "trader_id": "agent_trader",
                "side": "BUY_YES",
                "pay_coin": "100",
                "d_y": "-50",
                "d_n": "100",
                "get_y": "150",
                "get_n": "0",
                "pool_y_before": "100",
                "pool_n_before": "100",
                "pool_y_after": "50",
                "pool_n_after": "200",
                "invariant_k_before": "10000",
                "invariant_k_after": "10000",
                "effective_price": "0.666666667"
            }),
        )
        .predicate_pass(),
    )
    .expect("append amm swap");

    for market_id in ["mkt_a", "mkt_b"] {
        tape.append(
            AppendRequest::new(
                "MarketSettled",
                "writer:cli-test",
                json!({
                    "schema_id": "market_settled.v1",
                    "market_id": market_id,
                    "result": "YES",
                    "settlement_event_id": "mu:".to_string() + &"9".repeat(64),
                    "price_not_truth_ack": true
                }),
            )
            .predicate_pass(),
        )
        .expect("append market settled");
    }
    // mkt_c is deliberately left open (no MarketSettled) so settled_count must be 2, not 3.

    let repo_arg = repo.to_str().expect("UTF-8 repo path");

    let replay = turing()
        .args(["market", "replay", "--verify", "--micro-git", repo_arg])
        .output()
        .expect("run market replay --verify --micro-git");
    assert!(replay.status.success(), "market replay failed: {replay:?}");
    let stdout = String::from_utf8(replay.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("market replay: verified"));
    assert!(stdout.contains("source=guarded_micro_tape_read"));
    assert!(stdout.contains("market_count=3"));
    assert!(
        stdout.contains("market_settled_count=2"),
        "expected computed settled count 2, got: {stdout}"
    );

    let audit = turing()
        .args(["audit", "market", "--micro-git", repo_arg])
        .output()
        .expect("run audit market --micro-git");
    assert!(audit.status.success(), "audit market failed: {audit:?}");
    let stdout = String::from_utf8(audit.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("audit market: pass"));
    assert!(stdout.contains("source=guarded_micro_tape_read"));
    assert!(
        stdout.contains("settled=2"),
        "expected computed settled count 2, got: {stdout}"
    );

    // Bare (no --micro-git) still runs the labeled demo, never the real tape above.
    let bare_replay = turing()
        .args(["market", "replay", "--verify"])
        .output()
        .expect("run bare market replay --verify");
    assert!(bare_replay.status.success());
    let bare_stdout = String::from_utf8(bare_replay.stdout).expect("stdout UTF-8");
    assert!(bare_stdout.contains("qualification=private-local"));
    assert!(!bare_stdout.contains("market_settled_count=2"));

    let bare_audit = turing()
        .args(["audit", "market"])
        .output()
        .expect("run bare audit market");
    assert!(bare_audit.status.success());
    let bare_audit_stdout = String::from_utf8(bare_audit.stdout).expect("stdout UTF-8");
    assert!(bare_audit_stdout.contains("qualification=private-local"));
    assert!(!bare_audit_stdout.contains("settled=2"));
}

#[test]
fn bad_micro_git_path_fails_closed_with_friendly_copy_not_raw_errno() {
    let output = turing()
        .args(["status", "--micro-git", "/does/not/exist/anywhere"])
        .output()
        .expect("run status with bad micro-git path");
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    assert!(stderr.contains("Can't find a tape at"));
    assert!(stderr.contains("Run: turing status --micro-git <valid-path>"));
    assert!(!stderr.contains("os error"));
    assert!(!stderr.contains("No such file or directory"));
}

#[test]
fn boot_with_micro_git_configures_a_default_bare_status_then_resolves() {
    let project = tempfile::tempdir().expect("temp project dir");
    let (repo, proposal) = sample_micro_repo();
    let repo_arg = repo.path().to_str().expect("UTF-8 repo path");

    let boot = turing()
        .args([
            "boot",
            "--project",
            project.path().to_str().expect("UTF-8 project path"),
            "--micro-git",
            repo_arg,
        ])
        .output()
        .expect("run boot with micro-git");
    assert!(boot.status.success(), "boot failed: {boot:?}");

    let status = turing()
        .arg("status")
        .current_dir(project.path())
        .env_remove("TURING_MICRO_GIT")
        .output()
        .expect("run bare status from booted project dir");
    assert!(status.status.success(), "status failed: {status:?}");
    let stdout = String::from_utf8(status.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("source_kind=guarded_micro_tape_read"));
    assert!(stdout.contains(&format!("tape_tip={}", proposal.event_id)));
}

#[test]
fn panoview_survives_a_reader_closing_the_pipe_early() {
    // F2: the historical bug was a `println!`-on-broken-pipe panic (the `turing panoview | head`
    // shape). Closing our read end right after spawn — before the child necessarily finishes
    // writing — reproduces the same "no reader left" condition without a shell pipe.
    let mut child = turing()
        .args(["demo", "panoview"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn demo panoview");
    drop(child.stdout.take().expect("stdout"));
    let output = child.wait_with_output().expect("wait for demo panoview");
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    assert!(
        !stderr.contains("panicked"),
        "process panicked on broken pipe: {stderr}"
    );
}

#[test]
fn jcs_canonicalize_writes_canonical_bytes_without_trailing_newline() {
    let mut child = turing()
        .args(["jcs", "canonicalize"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn jcs canonicalize");
    child
        .stdin
        .as_mut()
        .expect("stdin")
        .write_all(b"{\"b\":2,\"a\":\"h\xc3\xa9\",\"arr\":[true,null]}")
        .expect("write JSON");

    let output = child.wait_with_output().expect("run jcs canonicalize");

    assert!(
        output.status.success(),
        "jcs canonicalize failed: {output:?}"
    );
    assert_eq!(
        output.stdout,
        b"{\"a\":\"h\xc3\xa9\",\"arr\":[true,null],\"b\":2}"
    );
    assert!(
        output.stderr.is_empty(),
        "stderr: {:?}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn jcs_canonicalize_batch_emits_indexed_hex_lines() {
    let mut child = turing()
        .args(["jcs", "canonicalize", "--batch"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn jcs canonicalize batch");
    child
        .stdin
        .as_mut()
        .expect("stdin")
        .write_all(b"# ignored\n\n{\"b\":2,\"a\":1}\n{\"b\":0,\"a\":true}\n")
        .expect("write JSONL");

    let output = child
        .wait_with_output()
        .expect("run jcs canonicalize batch");

    assert!(
        output.status.success(),
        "jcs canonicalize batch failed: {output:?}"
    );
    assert!(
        output.stderr.is_empty(),
        "stderr: {:?}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(
        String::from_utf8(output.stdout).expect("stdout UTF-8"),
        "1\t7b2261223a312c2262223a327d\n2\t7b2261223a747275652c2262223a307d\n"
    );
}

#[test]
fn jcs_canonicalize_fails_closed_on_framing_violation() {
    let mut child = turing()
        .args(["jcs", "canonicalize"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn jcs canonicalize");
    child
        .stdin
        .as_mut()
        .expect("stdin")
        .write_all(b"{\"a\":1}\n")
        .expect("write JSON");

    let output = child.wait_with_output().expect("run jcs canonicalize");

    assert!(
        !output.status.success(),
        "framing violation must fail closed"
    );
    assert!(output.stdout.is_empty(), "stdout: {output:?}");
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    assert!(stderr.contains("jcs canonicalize failed"));
    assert!(stderr.contains("framing violation"));
}

#[test]
fn boot_project_writes_private_local_project_metadata() {
    let dir = tempfile::tempdir().expect("temp dir");

    let output = turing()
        .args([
            "boot",
            "--project",
            dir.path().to_str().expect("UTF-8 temp path"),
        ])
        .output()
        .expect("run boot project");

    assert!(output.status.success(), "boot failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("boot: wrote"));

    let metadata_path = dir.path().join(".turingos").join("project.json");
    let text = std::fs::read_to_string(metadata_path).expect("project metadata");
    assert!(text.contains(r#""schema_id":"operator_project.v1""#));
    assert!(text.contains(r#""project_root":"#));
    assert!(text.contains(r#""truth_source":"micro_tape""#));
    assert!(text.contains(r#""credential_material_included":false"#));
    assert!(text.contains(r#""can_write_micro_truth":false"#));
}

#[test]
fn approval_preview_renders_human_card_without_writing_truth() {
    let output = turing()
        .args([
            "approval",
            "preview",
            "--approval-id",
            "ap_cli_preview",
            "--authority-epoch",
            "7",
            "--action",
            "capsule_approve",
            "--subject",
            "wc_cli",
            "--risk",
            "P2",
            "--evidence-digest",
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "--signature-route",
            "none",
        ])
        .output()
        .expect("run approval preview");

    assert!(output.status.success(), "preview failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("approval preview:"));
    assert!(stdout.contains("approval_id=ap_cli_preview"));
    assert!(stdout.contains("action=capsule_approve"));
    assert!(stdout.contains("target=wc_cli"));
    assert!(stdout.contains("subject=wc_cli"));
    assert!(stdout.contains("risk=P2"));
    assert!(stdout.contains("source_heads=tape_tip,authorization_head,accepted_head"));
    assert!(stdout.contains("source_head_values=tape_tip:mu:"));
    assert!(stdout.contains("accepted_head:mu:"));
    assert!(stdout.contains("evidence_digest_count=1"));
    assert!(stdout.contains("approval_required=true"));
    assert!(stdout.contains("expiry=not_present"));
    assert!(stdout.contains("nonce=not_present"));
    assert!(stdout.contains("side_effect_class=sovereign_mutation"));
    assert!(stdout.contains("post_approval_state=NeedsApproval_or_AwaitingReceipt"));
    assert!(stdout.contains("signature_route=None"));
    assert!(stdout.contains("visible_card_hash=sha256:"));
    assert!(stdout.contains("writes_micro_truth=false"));
    assert!(!stdout.contains("signature="));
    assert!(!stdout.contains("credential"));
}

#[test]
fn approval_sign_in_memory_test_route_requires_explicit_test_flag() {
    let output = turing()
        .args([
            "approval",
            "sign",
            "--key-id",
            "operator-local-key",
            "--approval-id",
            "ap_cli_sign",
            "--authority-epoch",
            "7",
            "--action",
            "capsule_approve",
            "--subject",
            "wc_cli",
            "--risk",
            "P2",
            "--evidence-digest",
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "--signature-route",
            "in-memory-test",
        ])
        .output()
        .expect("run approval sign");

    assert!(
        !output.status.success(),
        "in-memory-test sign should require explicit flag"
    );
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    assert!(stderr.contains("--allow-test-signature"));
    assert!(stderr.contains("test-only"));
    assert!(!stderr.contains("signature=ed25519:"));
}

#[test]
fn approval_sign_emits_explicit_in_memory_test_signature_with_test_flag_only() {
    let output = turing()
        .args([
            "approval",
            "sign",
            "--key-id",
            "operator-local-key",
            "--approval-id",
            "ap_cli_sign",
            "--authority-epoch",
            "7",
            "--action",
            "capsule_approve",
            "--subject",
            "wc_cli",
            "--risk",
            "P2",
            "--evidence-digest",
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "--signature-route",
            "in-memory-test",
            "--allow-test-signature",
        ])
        .output()
        .expect("run approval sign");

    assert!(output.status.success(), "sign failed: {output:?}");
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("approval signature:"));
    assert!(stdout.contains("approval_id=ap_cli_sign"));
    assert!(stdout.contains("key_id=operator-local-key"));
    assert!(stdout.contains("signature_route=InMemoryTest"));
    assert!(stdout.contains("signed_payload_hash=sha256:"));
    assert!(stdout.contains("public_key_fingerprint=sha256:"));
    assert!(stdout.contains("verifying_key=ed25519-pub:"));
    assert!(stdout.contains("signature=ed25519:"));
    assert!(stdout.contains("test_signature_only=true"));
    assert!(stdout.contains("writes_micro_truth=false"));
    assert!(!stdout.contains("plaintext"));
    assert!(!stdout.contains("credential"));
}

#[test]
fn approval_sign_hardware_future_fails_closed_without_signature() {
    let output = turing()
        .args([
            "approval",
            "sign",
            "--key-id",
            "future-hsm-slot-0",
            "--approval-id",
            "ap_cli_hardware",
            "--authority-epoch",
            "7",
            "--action",
            "capsule_approve",
            "--subject",
            "wc_cli",
            "--risk",
            "P2",
            "--evidence-digest",
            "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "--signature-route",
            "hardware-future",
        ])
        .output()
        .expect("run hardware approval sign");

    assert!(!output.status.success(), "hardware sign should fail closed");
    let stderr = String::from_utf8(output.stderr).expect("stderr UTF-8");
    assert!(stderr.contains("hardware signing backend"));
    assert!(stderr.contains("reserved"));
    assert!(stderr.contains("unavailable"));
    assert!(!stderr.contains("signature=sha256:"));
    assert!(!stderr.contains("plaintext"));
    assert!(!stderr.contains("credential"));
}

#[test]
fn handoff_generate_writes_real_projection_hashes() {
    let dir = tempfile::tempdir().expect("temp dir");
    let output_path = dir.path().join("handoff.md");

    let output = turing()
        .args([
            "handoff",
            "generate",
            "--output",
            output_path.to_str().expect("UTF-8 temp path"),
        ])
        .output()
        .expect("run handoff generate");

    assert!(
        output.status.success(),
        "handoff generate failed: {output:?}"
    );
    let stdout = String::from_utf8(output.stdout).expect("stdout UTF-8");
    assert!(stdout.contains("handoff: wrote"));

    let text = std::fs::read_to_string(&output_path).expect("handoff file");
    for label in [
        "tape_tip: mu:",
        "authorization_head:",
        "accepted_head: mu:",
        "market projection hash: sha256:",
        "wallet projection hash: sha256:",
        "PPUT projection hash: sha256:",
        "cargo test --workspace",
        "scripts/install-local.sh",
        "turing approval preview",
        "turing approval sign",
        "hardware-future route fails closed",
        "projection snapshot write",
        "market projection",
        "price_not_truth=true",
        "wallet projection snapshot write",
        "credential_material_included=false",
        "PPUT projection snapshot write",
        "hidden_from_worker_prompt=true",
        "raw_formula_exposed=false",
        "derived-only and cannot own truth",
        "scope/budget/provenance/replay",
        "turing replay --verify",
        "Known Risks",
    ] {
        assert!(text.contains(label), "generated handoff missing {label:?}");
    }
    assert!(
        !text.contains("required final handoff field"),
        "generated handoff must replace placeholder language"
    );
}
