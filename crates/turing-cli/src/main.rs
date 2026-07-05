use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use serde_json::{Value, json};
use turing_approval::{
    APPROVAL_PAYLOAD_SCHEMA_ID, ApprovalCard, ApprovalPayload, AuthorityKeySet, DisplayCopy,
    HardwareSigningBackend, InMemoryTestSigningBackend, OsKeyringSigningBackend, SignatureRoute,
    SigningBackend,
};
use turing_contracts::envelope::HeadSet;
use turing_contracts::jcs;
use turing_git_tape::append::Append;
use turing_projection::{
    CommandSpec, OperatorHeads, OperatorToolManifest, OperatorTurnTrace, OperatorViewSnapshot,
    TypedVerb,
};
use turing_qualification::{run_new_project_agent_economy_demo, run_rescue_agent_economy_demo};
use turing_replay::Reconstruction;

/// The env var an operator can set so bare `turing status`/`panoview`/`doctor` resolve a real
/// MicroTape instead of failing closed (F1: default-command honesty).
const MICRO_GIT_ENV: &str = "TURING_MICRO_GIT";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let words: Vec<&str> = args.iter().map(String::as_str).collect();

    if words.first() == Some(&"jcs") {
        return match run_jcs_command(&words) {
            Ok(()) => ExitCode::SUCCESS,
            Err(message) => {
                write_stderr(&message);
                ExitCode::from(2)
            }
        };
    }

    match dispatch(&words) {
        Ok(message) => {
            write_stdout(&message);
            ExitCode::SUCCESS
        }
        Err(message) => {
            write_stderr(&message);
            ExitCode::from(2)
        }
    }
}

/// Write `text` plus a trailing newline to stdout. A broken pipe (the reader closed early —
/// e.g. `turing panoview | head`) is treated as a quiet, successful exit rather than the panic
/// `println!`/`writeln!` would raise on a stdout write failure.
fn write_stdout(text: &str) {
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    if let Err(error) = writeln!(handle, "{text}")
        && error.kind() != io::ErrorKind::BrokenPipe
    {
        write_stderr(&format!("turing: failed to write stdout: {error}"));
    }
}

/// Write `text` plus a trailing newline to stderr, with the same broken-pipe tolerance as
/// [`write_stdout`].
fn write_stderr(text: &str) {
    let stderr = io::stderr();
    let mut handle = stderr.lock();
    let _ = writeln!(handle, "{text}");
}

fn run_jcs_command(args: &[&str]) -> Result<(), String> {
    match args {
        ["jcs", "canonicalize"] => {
            let mut input = String::new();
            io::stdin()
                .read_to_string(&mut input)
                .map_err(|error| format!("jcs canonicalize failed to read stdin: {error}"))?;
            let value = jcs::parse_strict(&input)
                .map_err(|error| format!("jcs canonicalize failed: {error}"))?;
            let bytes = jcs::canonicalize(&value)
                .map_err(|error| format!("jcs canonicalize failed: {error}"))?;
            io::stdout()
                .write_all(&bytes)
                .map_err(|error| format!("jcs canonicalize failed to write stdout: {error}"))?;
            Ok(())
        }
        ["jcs", "canonicalize", "--batch"] => {
            let mut input = String::new();
            io::stdin()
                .read_to_string(&mut input)
                .map_err(|error| format!("jcs canonicalize batch failed to read stdin: {error}"))?;

            let mut case_index = 0usize;
            let mut output = String::new();
            for raw_line in input.lines() {
                let line = raw_line.trim_end_matches('\r');
                if line.trim().is_empty() || line.trim_start().starts_with('#') {
                    continue;
                }
                case_index += 1;
                let value = jcs::parse_strict(line).map_err(|error| {
                    format!("jcs canonicalize batch failed at case {case_index}: {error}")
                })?;
                let bytes = jcs::canonicalize(&value).map_err(|error| {
                    format!("jcs canonicalize batch failed at case {case_index}: {error}")
                })?;
                output.push_str(&format!("{case_index}\t{}\n", lower_hex(&bytes)));
            }
            io::stdout().write_all(output.as_bytes()).map_err(|error| {
                format!("jcs canonicalize batch failed to write stdout: {error}")
            })?;
            Ok(())
        }
        _ => Err(format!(
            "unknown turing jcs command: {:?}. supported: jcs canonicalize [--batch]",
            args
        )),
    }
}

fn lower_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

fn dispatch(args: &[&str]) -> Result<String, String> {
    match args {
        [] | ["--help"] | ["help"] => Ok(operator_help()),
        ["help", "commands"] => Ok(operator_commands_help()),
        ["help", _topic] => Ok(operator_help()),
        ["status", "--help"] => Ok(status_help()),
        // F1 default-command honesty: bare `status` (with or without --json) never silently
        // runs the synthetic economy demo. It resolves TURING_MICRO_GIT / a configured project
        // default, else fails closed with the 3-line pattern. `--demo` stays an explicit,
        // backward-compatible escape hatch (kept for existing FCE certification scenarios).
        ["status"] => match resolve_default_micro_git() {
            Some(path) => render_operator_status(SnapshotInput::MicroGit(&path)),
            None => Err(no_tape_configured_error("status")),
        },
        ["status", "--json"] => match resolve_default_micro_git() {
            Some(path) => render_operator_snapshot_json(SnapshotInput::MicroGit(&path)),
            None => Err(no_tape_configured_error("status")),
        },
        ["status", "--json", "--demo"] => render_operator_snapshot_json(SnapshotInput::Demo),
        ["status", "--micro-git", repo] => render_operator_status(SnapshotInput::MicroGit(repo)),
        ["status", "--micro-git", repo, "--json"] | ["status", "--json", "--micro-git", repo] => {
            render_operator_snapshot_json(SnapshotInput::MicroGit(repo))
        }
        ["status", "--micro-bundle", bundle] => {
            render_operator_status(SnapshotInput::MicroBundle(bundle))
        }
        ["status", "--micro-bundle", bundle, "--json"]
        | ["status", "--json", "--micro-bundle", bundle] => {
            render_operator_snapshot_json(SnapshotInput::MicroBundle(bundle))
        }
        ["panoview", "--help"] => Ok(panoview_help()),
        ["panoview"] => match resolve_default_micro_git() {
            Some(path) => render_operator_panoview(SnapshotInput::MicroGit(&path), false),
            None => Err(no_tape_configured_error("panoview")),
        },
        ["panoview", "--ascii"] => match resolve_default_micro_git() {
            Some(path) => render_operator_panoview(SnapshotInput::MicroGit(&path), true),
            None => Err(no_tape_configured_error("panoview")),
        },
        ["panoview", "--json"] => match resolve_default_micro_git() {
            Some(path) => render_operator_snapshot_json(SnapshotInput::MicroGit(&path)),
            None => Err(no_tape_configured_error("panoview")),
        },
        ["panoview", "--json", "--demo"] => render_operator_snapshot_json(SnapshotInput::Demo),
        ["panoview", "--micro-git", repo] => {
            render_operator_panoview(SnapshotInput::MicroGit(repo), false)
        }
        ["panoview", "--micro-git", repo, "--ascii"]
        | ["panoview", "--ascii", "--micro-git", repo] => {
            render_operator_panoview(SnapshotInput::MicroGit(repo), true)
        }
        ["panoview", "--micro-git", repo, "--json"]
        | ["panoview", "--json", "--micro-git", repo] => {
            render_operator_snapshot_json(SnapshotInput::MicroGit(repo))
        }
        ["panoview", "--micro-bundle", bundle] => {
            render_operator_panoview(SnapshotInput::MicroBundle(bundle), false)
        }
        ["panoview", "--micro-bundle", bundle, "--ascii"]
        | ["panoview", "--ascii", "--micro-bundle", bundle] => {
            render_operator_panoview(SnapshotInput::MicroBundle(bundle), true)
        }
        ["panoview", "--micro-bundle", bundle, "--json"]
        | ["panoview", "--json", "--micro-bundle", bundle] => {
            render_operator_snapshot_json(SnapshotInput::MicroBundle(bundle))
        }
        // Demo becomes an explicit, honestly-labeled subcommand (F1): same render path, but the
        // header line says plainly that this is a synthetic fixture, not the operator's tape.
        ["demo", "--help"] => Ok(demo_help()),
        ["demo", "status"] => render_operator_status_demo(),
        ["demo", "status", "--json"] => render_operator_snapshot_json(SnapshotInput::Demo),
        ["demo", "panoview"] => render_operator_panoview_demo(false),
        ["demo", "panoview", "--ascii"] => render_operator_panoview_demo(true),
        ["demo", "panoview", "--json"] => render_operator_snapshot_json(SnapshotInput::Demo),
        ["demo", "replay"] => demo_replay_verify(),
        ["doctor", "--help"] => Ok(doctor_help()),
        ["doctor", rest @ ..] => run_doctor(rest),
        ["explain", "--help"] => Ok(explain_help()),
        ["explain"] => {
            render_operator_explain(TypedVerb::EXPLAIN_BLOCKER, SnapshotInput::Demo, None)
        }
        ["explain", "blocker"] => {
            render_operator_explain(TypedVerb::EXPLAIN_BLOCKER, SnapshotInput::Demo, None)
        }
        ["explain", "event"] => {
            render_operator_explain(TypedVerb::EXPLAIN_EVENT, SnapshotInput::Demo, None)
        }
        ["explain", "event", event_id] => render_operator_explain(
            TypedVerb::EXPLAIN_EVENT,
            SnapshotInput::Demo,
            Some(event_id),
        ),
        ["explain", "--micro-git", repo] => render_operator_explain(
            TypedVerb::EXPLAIN_BLOCKER,
            SnapshotInput::MicroGit(repo),
            None,
        ),
        ["explain", "--micro-bundle", bundle] => render_operator_explain(
            TypedVerb::EXPLAIN_BLOCKER,
            SnapshotInput::MicroBundle(bundle),
            None,
        ),
        ["explain", "blocker", "--micro-git", repo] => render_operator_explain(
            TypedVerb::EXPLAIN_BLOCKER,
            SnapshotInput::MicroGit(repo),
            None,
        ),
        ["explain", "blocker", "--micro-bundle", bundle] => render_operator_explain(
            TypedVerb::EXPLAIN_BLOCKER,
            SnapshotInput::MicroBundle(bundle),
            None,
        ),
        ["explain", "event", "--micro-git", repo] => render_operator_explain(
            TypedVerb::EXPLAIN_EVENT,
            SnapshotInput::MicroGit(repo),
            None,
        ),
        ["explain", "event", "--micro-bundle", bundle] => render_operator_explain(
            TypedVerb::EXPLAIN_EVENT,
            SnapshotInput::MicroBundle(bundle),
            None,
        ),
        ["explain", "event", event_id, "--micro-git", repo] => render_operator_explain(
            TypedVerb::EXPLAIN_EVENT,
            SnapshotInput::MicroGit(repo),
            Some(event_id),
        ),
        ["explain", "event", event_id, "--micro-bundle", bundle] => render_operator_explain(
            TypedVerb::EXPLAIN_EVENT,
            SnapshotInput::MicroBundle(bundle),
            Some(event_id),
        ),
        ["ask", "--help"] => Ok(ask_help()),
        ["ask", utterance @ ..] => render_operator_ask(&utterance.join(" ")),
        ["operator"] => run_operator_console(),
        ["boot", "--project", project] => boot_project(project),
        ["boot", "--project", project, "--micro-git", micro_git] => {
            boot_project_with_micro_git(project, micro_git)
        }
        ["replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("replay verify failed: {error}"))?;
            Ok(format!(
                "replay: verified tape_tip={} accepted_head={} qualification=private-local",
                report.tape_tip, report.accepted_head
            ))
        }
        ["replay", "--verify", "--micro-git", repo] => replay_verify_real(repo),
        ["market", "replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("market replay failed: {error}"))?;
            Ok(format!(
                "market replay: verified status={} market_settled_count={} price_not_truth=true",
                report.market_projection_status, report.market_settled_count
            ))
        }
        ["pput", "replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("pput replay failed: {error}"))?;
            Ok(format!(
                "pput replay: verified progress={} hidden_from_worker_prompt=true",
                report.pput_progress
            ))
        }
        ["audit", "invariants"] => {
            let new_project = run_new_project_agent_economy_demo()
                .map_err(|error| format!("invariant audit failed: {error}"))?;
            let rescue = run_rescue_agent_economy_demo()
                .map_err(|error| format!("invariant audit failed: {error}"))?;
            Ok(format!(
                "audit invariants: pass accepted_head={} failure_preserved_head={}",
                new_project.accepted_head, rescue.accepted_head_after_failure
            ))
        }
        ["audit", "invariants", "--micro-git", repo] => audit_invariants_real(repo),
        ["audit", "market"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("market audit failed: {error}"))?;
            Ok(format!(
                "audit market: pass settled={} accepted_head_not_market_settlement=true",
                report.market_settled_count
            ))
        }
        ["audit", "pput"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("pput audit failed: {error}"))?;
            Ok(format!(
                "audit pput: pass progress={} no_pput_prompt_leakage={}",
                report.pput_progress, report.no_pput_prompt_leakage
            ))
        }
        ["handoff", "generate", "--output", output] => generate_handoff(output),
        [
            "approval",
            "preview",
            "--approval-id",
            approval_id,
            "--authority-epoch",
            authority_epoch,
            "--action",
            action,
            "--subject",
            subject,
            "--risk",
            risk,
            "--evidence-digest",
            evidence_digest,
            "--signature-route",
            signature_route,
        ] => approval_preview(
            approval_id,
            authority_epoch,
            action,
            subject,
            risk,
            evidence_digest,
            signature_route,
        ),
        [
            "approval",
            "sign",
            "--key-id",
            key_id,
            "--approval-id",
            approval_id,
            "--authority-epoch",
            authority_epoch,
            "--action",
            action,
            "--subject",
            subject,
            "--risk",
            risk,
            "--evidence-digest",
            evidence_digest,
            "--signature-route",
            signature_route,
        ] => approval_sign(
            key_id,
            approval_id,
            authority_epoch,
            action,
            subject,
            risk,
            evidence_digest,
            signature_route,
            false,
        ),
        [
            "approval",
            "sign",
            "--key-id",
            key_id,
            "--approval-id",
            approval_id,
            "--authority-epoch",
            authority_epoch,
            "--action",
            action,
            "--subject",
            subject,
            "--risk",
            risk,
            "--evidence-digest",
            evidence_digest,
            "--signature-route",
            signature_route,
            "--allow-test-signature",
        ] => approval_sign(
            key_id,
            approval_id,
            authority_epoch,
            action,
            subject,
            risk,
            evidence_digest,
            signature_route,
            true,
        ),
        _ => Err(unknown_command_error(args)),
    }
}

/// The closed-form 3-line error for any input `dispatch` does not recognize: what failed, why,
/// and the exact next command — never the historical ~500-char grammar dump (that full grammar
/// is still available, but only on request, under `turing help commands`).
fn unknown_command_error(args: &[&str]) -> String {
    format!(
        "Unknown command: {}\nturing does not recognize this input.\nRun: turing help commands   (or: turing --help)",
        args.join(" ")
    )
}

/// `TURING_MICRO_GIT`, else a `.turingos/project.json` `micro_git` field configured by `turing
/// boot --project <path> --micro-git <path>` in the current directory — the F1 default-command
/// resolution order for bare `status`/`panoview`/`doctor`. Returns `None` if neither is set, so
/// the caller can fail closed instead of silently running the demo.
fn resolve_default_micro_git() -> Option<String> {
    if let Ok(value) = std::env::var(MICRO_GIT_ENV) {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Some(trimmed.to_string());
        }
    }
    let config_path = Path::new(".turingos").join("project.json");
    let text = std::fs::read_to_string(config_path).ok()?;
    let value: Value = serde_json::from_str(&text).ok()?;
    let micro_git = value.get("micro_git")?.as_str()?;
    if micro_git.is_empty() {
        return None;
    }
    Some(micro_git.to_string())
}

/// The F1 3-line failure pattern for a `verb` that needs a tape but has none configured: what's
/// missing, why, and the exact next command (the demo escape hatch first, the real-tape flag
/// second) — never a silent demo run and never a raw errno.
fn no_tape_configured_error(verb: &str) -> String {
    format!(
        "No tape configured.\nturing {verb} doesn't know which tape to read.\nRun: turing demo {verb}   (or: turing {verb} --micro-git <path>)"
    )
}

fn operator_help() -> String {
    let verbs = CommandSpec::all()
        .iter()
        .map(|spec| spec.verb.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    format!(
        "Operator Console v1\ncontracts: operator_view_snapshot.v1 typed_command.v1 operator_intent.v1 operator_tool_manifest.v1 operator_turn_trace.v1\ncommands: status [--micro-git <path>|--micro-bundle <path>] [--json] | panoview [--micro-git <path>|--micro-bundle <path>] [--json] | explain blocker|event [--micro-git <path>|--micro-bundle <path>] | ask <utterance> | operator | demo status|panoview|replay | doctor [--ci] [--micro-git <path>] | help\nfixed verbs: {verbs}\nstatus ceiling: IMPLEMENTER_ADDRESSED until a real external human signature exists\nper-subcommand help: turing <status|panoview|explain|ask|demo|doctor> --help\nfull grammar: turing help commands"
    )
}

fn operator_commands_help() -> String {
    let rows = CommandSpec::all()
        .iter()
        .map(|spec| {
            format!(
                "verb={} side_effect_class={} approval_required={} writes_truth={} confirmation_route={} source_heads={} expected_receipt={}",
                spec.verb.as_str(),
                spec.side_effect_class.as_str(),
                spec.approval_required,
                spec.writes_truth,
                spec.confirmation_route.as_str(),
                spec.source_heads.join(","),
                spec.expected_receipt
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    format!(
        "Operator Console v1 topic=commands\ncontract=operator_tool_manifest.v1 item_contract=typed_command.v1\n{rows}\nstatus_ceiling=IMPLEMENTER_ADDRESSED\nfull_grammar: {}",
        full_cli_grammar()
    )
}

/// The complete CLI invocation grammar. Historically this string was dumped on every parse
/// error (~500 chars); it now lives in exactly one reachable place (`turing help commands`) so
/// operators can still find it without every mistake reading like a stack trace (F2).
fn full_cli_grammar() -> &'static str {
    "status [--micro-git <path>|--micro-bundle <path>] [--json] | panoview [--micro-git <path>|--micro-bundle <path>] [--json] | explain blocker|event [event_id] [--micro-git <path>|--micro-bundle <path>] | ask <utterance> | operator | demo status|panoview|replay [--json] | doctor [--ci] [--micro-git <path>|--micro-bundle <path>] | help commands | boot --project <path> [--micro-git <path>] | approval preview --approval-id <id> --authority-epoch <n> --action <action> --subject <id> --risk <risk> --evidence-digest <sha256> --signature-route <none|os-keyring|hardware-future> | approval sign --key-id <id> --approval-id <id> --authority-epoch <n> --action <action> --subject <id> --risk <risk> --evidence-digest <sha256> --signature-route os-keyring | approval sign ... --signature-route in-memory-test --allow-test-signature | replay --verify [--micro-git <path>] | market replay --verify | pput replay --verify | audit invariants [--micro-git <path>]|market|pput | handoff generate --output <path>"
}

fn status_help() -> String {
    "turing status — read-only operator heartbeat (heads + snapshot hash) of one MicroTape.\n\
     \n\
     Usage: turing status [--micro-git <path> | --micro-bundle <path>] [--json]\n\
     \n\
     With no path, turing status resolves TURING_MICRO_GIT or a project-configured default\n\
     (see: turing boot --project <path> --micro-git <path>); if neither is set it fails\n\
     closed and prints the next command to run.\n\
     \n\
     Examples:\n  \
     turing status --micro-git ./my-project\n  \
     turing status --micro-git ./my-project --json\n  \
     turing demo status   (synthetic fixture tape — never your real tape)"
        .to_string()
}

fn panoview_help() -> String {
    "turing panoview — read-only multi-lane view (heads, evidence, warnings, safe commands).\n\
     \n\
     Usage: turing panoview [--micro-git <path> | --micro-bundle <path>] [--json] [--ascii]\n\
     \n\
     Same resolution order as turing status: TURING_MICRO_GIT, then a project-configured\n\
     default, else it fails closed and prints the next command to run.\n\
     \n\
     If the tape carries capsule-dispatch events, panoview also renders a per-item\n\
     work_items view: closed glyph+label per stage (authorized/pending execution/awaiting\n\
     receipt/receipt matched/accepted), a claimed-vs-accepted header, and a roll-up\n\
     sentence. --ascii selects the plain-ASCII glyph column instead of unicode.\n\
     \n\
     Examples:\n  \
     turing panoview --micro-git ./my-project\n  \
     turing panoview --micro-git ./my-project --ascii\n  \
     turing demo panoview   (synthetic fixture tape — never your real tape)"
        .to_string()
}

fn explain_help() -> String {
    "turing explain — typed_command.v1 explanation of a blocker or a specific tape event.\n\
     \n\
     Usage: turing explain blocker|event [event_id] [--micro-git <path> | --micro-bundle <path>]\n\
     \n\
     Examples:\n  \
     turing explain blocker --micro-git ./my-project\n  \
     turing explain event mu:aaaa... --micro-git ./my-project"
        .to_string()
}

fn ask_help() -> String {
    "turing ask — route a natural-language utterance to a typed_command.v1 (advisory only;\n\
     never dispatches, never writes truth).\n\
     \n\
     Usage: turing ask <utterance>\n\
     \n\
     Example: turing ask \"what is blocking this\""
        .to_string()
}

fn demo_help() -> String {
    "turing demo — the synthetic economy demo fixture, explicitly labeled as a demo.\n\
     \n\
     Usage: turing demo status|panoview|replay [--json]\n\
     \n\
     This mints a private-local demo Tape every run; it is never the operator's real tape.\n\
     For a real tape, use: turing status --micro-git <path> (or configure a default —\n\
     see: turing boot --project <path> --micro-git <path>)."
        .to_string()
}

fn doctor_help() -> String {
    "turing doctor — checks the configured/passed tape and reports PASS/FAIL per check.\n\
     \n\
     Usage: turing doctor [--ci] [--micro-git <path> | --micro-bundle <path>]\n\
     \n\
     Checks: (1) binary + dependency availability (git on PATH), (2) replay verify of the\n\
     real tape via turing-replay::replay_tape. Any FAIL exits nonzero and names the failing\n\
     check with its typed corruption detail.\n\
     \n\
     --ci: no color, one machine-parseable `check=<name> status=<PASS|FAIL> detail=<...>`\n\
     line per check.\n\
     \n\
     With no path, turing doctor resolves TURING_MICRO_GIT or a project-configured default,\n\
     same as turing status.\n\
     \n\
     Example: turing doctor --micro-git ./my-project --ci"
        .to_string()
}

#[derive(Debug, Clone, Copy)]
enum SnapshotInput<'a> {
    Demo,
    MicroGit(&'a str),
    MicroBundle(&'a str),
}

fn operator_snapshot(input: SnapshotInput<'_>) -> Result<OperatorViewSnapshot, String> {
    match input {
        SnapshotInput::Demo => demo_snapshot(),
        SnapshotInput::MicroGit(path) => micro_git_snapshot(path),
        SnapshotInput::MicroBundle(path) => micro_bundle_snapshot(path),
    }
}

fn demo_snapshot() -> Result<OperatorViewSnapshot, String> {
    let report = run_new_project_agent_economy_demo()
        .map_err(|error| format!("operator snapshot replay failed: {error}"))?;
    let heads = OperatorHeads::new(
        report.tape_tip,
        report.authorization_head,
        report.accepted_head,
    )
    .map_err(|error| format!("operator snapshot heads invalid: {error}"))?;
    let project_root = std::env::current_dir()
        .map_err(|error| format!("cannot read current dir: {error}"))?
        .display()
        .to_string();
    // No per-item work_items derivation for the synthetic demo tape (deliberate scope
    // decision, F3): `run_new_project_agent_economy_demo` mints and immediately drops a
    // private tempdir, so there is no repo left on disk to walk after it returns, and its
    // internal `ProjectionEvent` record uses a `subject_id` that isn't a stable capsule_id
    // across steps (a `WorkCapsuleBuilt`/`WorkerReceiptImported` pair share "wc_hello_cli",
    // but the `CandidateAccepted` step's subject is "cand_hello_cli" — a different string).
    // Wiring real per-item derivation into the demo would mean reshaping
    // `turing-qualification`'s shared demo builder, out of this atom's scope. The demo stays
    // a legacy-shaped snapshot (`work_items: None`), which is exactly the fallback the F3
    // contract asks renderers to honor.
    OperatorViewSnapshot::from_deterministic_replay(
        project_root,
        "qualification_demo_micro_tape",
        "turing replay --verify",
        heads,
        Vec::new(),
    )
    .map_err(|error| format!("operator snapshot failed: {error}"))
}

fn micro_git_snapshot(path: &str) -> Result<OperatorViewSnapshot, String> {
    let micro_repo = canonicalize_micro_git(path)?;
    micro_git_snapshot_from_repo(
        &micro_repo,
        micro_repo.display().to_string(),
        format!("turing status --micro-git {}", micro_repo.display()),
    )
}

fn micro_bundle_snapshot(path: &str) -> Result<OperatorViewSnapshot, String> {
    let (bundle, scratch_path, _scratch) = materialize_bundle_scratch(path)?;
    micro_git_snapshot_from_repo(
        &scratch_path,
        format!("bundle:{}", bundle.display()),
        format!("turing status --micro-bundle {}", bundle.display()),
    )
}

/// Resolve `--micro-git <path>` without leaking a raw errno (F2): a bad path becomes the
/// 3-line pattern, never `format!("{error}")` of a `std::io::Error` like "os error 2".
fn canonicalize_micro_git(path: &str) -> Result<PathBuf, String> {
    std::fs::canonicalize(path).map_err(|_| {
        format!(
            "Can't find a tape at {path}.\n{path} does not exist or isn't readable as a MicroTape.\nRun: turing status --micro-git <valid-path>   (or: turing demo status)"
        )
    })
}

/// Resolve `--micro-bundle <path>`, same no-raw-errno rule as [`canonicalize_micro_git`].
fn canonicalize_micro_bundle(path: &str) -> Result<PathBuf, String> {
    std::fs::canonicalize(path).map_err(|_| {
        format!(
            "Can't find a tape bundle at {path}.\n{path} does not exist or isn't readable.\nRun: turing status --micro-bundle <valid-path>   (or: turing demo status)"
        )
    })
}

/// Materialize a `--micro-bundle` into a scratch MicroTape repo. Returns the canonicalized
/// bundle path (for display), the scratch repo path, and the [`BundleScratch`] guard — the
/// caller must keep the guard alive for as long as the scratch path is read (its `Drop` removes
/// the directory).
fn materialize_bundle_scratch(path: &str) -> Result<(PathBuf, PathBuf, BundleScratch), String> {
    let bundle = canonicalize_micro_bundle(path)?;
    let scratch = BundleScratch::new()?;
    run_git(
        &["init", "--object-format=sha256", "-q", scratch.path_str()?],
        None,
    )?;
    run_git(
        &[
            "fetch",
            "-q",
            bundle
                .to_str()
                .ok_or_else(|| format!("non-UTF-8 bundle path {}", bundle.display()))?,
            "refs/*:refs/*",
        ],
        Some(scratch.path()),
    )?;
    let scratch_path = scratch.path().to_path_buf();
    Ok((bundle, scratch_path, scratch))
}

fn micro_git_snapshot_from_repo(
    micro_repo: &Path,
    source_micro_repo: String,
    rebuild_command: String,
) -> Result<OperatorViewSnapshot, String> {
    let head_set = open_guarded_heads(micro_repo)?;
    // Real per-item derivation (F3): walk the whole guarded tape once and fold it into
    // work_items. A tape with no capsule-dispatch-shaped events (e.g. the plain 2-event
    // default HCI fixture) derives an empty Vec, which `from_guarded_heads` turns into
    // `None` — the exact legacy shape existing callers already exercise.
    let raw_events = read_all_tape_events(micro_repo, &head_set.tape_tip)?;
    let work_items = turing_projection::derive_work_items(&raw_events);
    let heads = OperatorHeads::new(
        head_set.tape_tip,
        head_set.authorization_head,
        head_set.accepted_head,
    )
    .map_err(|error| format!("operator snapshot heads invalid: {error}"))?;
    let project_root = std::env::current_dir()
        .map_err(|error| format!("cannot read current dir: {error}"))?
        .display()
        .to_string();
    OperatorViewSnapshot::from_guarded_heads(
        project_root,
        source_micro_repo,
        rebuild_command,
        heads,
        work_items,
    )
    .map_err(|error| format!("operator snapshot failed: {error}"))
}

/// Walk every event on the guarded tape (genesis → `tape_tip`) and return it as a
/// [`turing_projection::RawTapeEvent`] — the read-only input [`turing_projection::
/// derive_work_items`] folds over. Same non-merge-chain walk `turing-daemons`'
/// `load_tape_envelopes` uses (`commit_parents` / `committed_body_bytes`); duplicated here
/// rather than adding a `turing-cli` → `turing-daemons` dependency for one helper.
fn read_all_tape_events(
    repo: &Path,
    tape_tip: &str,
) -> Result<Vec<turing_projection::RawTapeEvent>, String> {
    let mut cursor = normalize_mu_oid(tape_tip);
    let mut event_ids = Vec::new();
    loop {
        event_ids.push(cursor.clone());
        let parents = turing_git_tape::append::commit_parents(repo, &cursor)
            .map_err(|error| format!("cannot read tape parents for {cursor}: {error}"))?;
        match parents.as_slice() {
            [] => break,
            [parent] => cursor = normalize_mu_oid(parent),
            many => {
                return Err(format!(
                    "tape event {cursor} is a merge commit with {} parents",
                    many.len()
                ));
            }
        }
    }
    event_ids.reverse();

    event_ids
        .into_iter()
        .map(|event_id| {
            let bytes = turing_git_tape::append::committed_body_bytes(repo, &event_id)
                .map_err(|error| format!("cannot read committed body for {event_id}: {error}"))?;
            let value: Value = serde_json::from_slice(&bytes)
                .map_err(|error| format!("committed body {event_id} is not JSON: {error}"))?;
            let envelope = turing_contracts::envelope::MicroEventEnvelope::from_jcs_value(&value)
                .map_err(|error| {
                    format!("committed body {event_id} is not a MicroEventEnvelope: {error}")
                })?;
            Ok(turing_projection::RawTapeEvent {
                event_type: envelope.event_type,
                payload: envelope.payload,
            })
        })
        .collect()
}

/// `mu:`-prefix a bare hex OID (`commit_parents` returns bare hex; a `HeadSet.tape_tip` is
/// already `mu:`-prefixed) — idempotent either way.
fn normalize_mu_oid(id: &str) -> String {
    if id.starts_with("mu:") {
        id.to_string()
    } else {
        format!("mu:{id}")
    }
}

/// Open a MicroTape at `repo` and read its guarded coherent [`HeadSet`] — the shared, friendly-
/// error path used by status/panoview/explain, `replay --verify --micro-git`, `audit invariants
/// --micro-git`, and `turing doctor`'s `tape_resolved` check. Never a raw errno; every failure
/// names the next command (F2).
fn open_guarded_heads(repo: &Path) -> Result<HeadSet, String> {
    let tape = Append::open(repo).map_err(|error| {
        format!(
            "Can't open the tape at {}.\n{error}\nRun: turing doctor --micro-git {}",
            repo.display(),
            repo.display()
        )
    })?;
    tape.head_set_guarded()
        .map_err(|error| {
            format!(
                "The tape at {} looks torn or unreadable.\n{error}\nRun: turing doctor --micro-git {}",
                repo.display(),
                repo.display()
            )
        })?
        .ok_or_else(|| {
            format!(
                "This tape has never been initialized.\nNo operator heads exist yet at {}.\nRun: turing boot --project {}",
                repo.display(),
                repo.display()
            )
        })
}

/// Open a MicroTape at `repo` and replay it end-to-end via [`turing_replay::replay_tape`] — the
/// shared real-tape path for `replay --verify --micro-git`, `audit invariants --micro-git`, and
/// `turing doctor`'s `replay_verify` check. A corrupt tape fails closed with the typed
/// [`turing_replay::ReplayError`] detail, never a raw errno.
fn replay_guarded(repo: &Path) -> Result<Reconstruction, String> {
    let heads = open_guarded_heads(repo)?;
    turing_replay::replay_tape(repo, &heads.tape_tip).map_err(|error| {
        format!(
            "The tape at {} does not replay cleanly.\n{error}\nRun: turing doctor --micro-git {}",
            repo.display(),
            repo.display()
        )
    })
}

struct BundleScratch {
    path: PathBuf,
}

impl BundleScratch {
    fn new() -> Result<Self, String> {
        let pid = std::process::id();
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|error| format!("system clock error: {error}"))?
            .as_nanos();
        let path = std::env::temp_dir().join(format!("turingos-hci-bundle-{pid}-{nanos}"));
        std::fs::create_dir(&path).map_err(|error| {
            format!(
                "failed to create bundle scratch {}: {error}",
                path.display()
            )
        })?;
        Ok(BundleScratch { path })
    }

    fn path(&self) -> &Path {
        &self.path
    }

    fn path_str(&self) -> Result<&str, String> {
        self.path
            .to_str()
            .ok_or_else(|| format!("non-UTF-8 scratch path {}", self.path.display()))
    }
}

impl Drop for BundleScratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

fn run_git(args: &[&str], cwd: Option<&Path>) -> Result<(), String> {
    let mut command = std::process::Command::new("git");
    command.args(args);
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    let output = command
        .output()
        .map_err(|error| format!("failed to execute git {:?}: {error}", args))?;
    if output.status.success() {
        return Ok(());
    }
    Err(format!(
        "git {:?} failed: {}",
        args,
        String::from_utf8_lossy(&output.stderr).trim()
    ))
}

fn render_operator_status(input: SnapshotInput<'_>) -> Result<String, String> {
    let snapshot = operator_snapshot(input)?;
    Ok(format!(
        "operator_view_snapshot.v1 heartbeat source_kind={} micro_repo={} operator_state={} tape_tip={} authorization_head={} accepted_head={} can_write_truth={} status_ceiling=IMPLEMENTER_ADDRESSED snapshot_hash={}",
        snapshot.source.source_kind,
        snapshot.source.micro_repo,
        snapshot.operator_state.as_str(),
        snapshot.heads.tape_tip,
        snapshot
            .heads
            .authorization_head
            .as_deref()
            .unwrap_or("null"),
        snapshot.heads.accepted_head,
        snapshot.source.can_write_truth,
        snapshot.snapshot_hash
    ))
}

fn render_operator_snapshot_json(input: SnapshotInput<'_>) -> Result<String, String> {
    let snapshot = operator_snapshot(input)?;
    serde_json::to_string(&snapshot)
        .map_err(|error| format!("operator snapshot JSON serialization failed: {error}"))
}

/// The header every `turing demo` text render carries (F1): plainly, unmissably, this is a
/// synthetic fixture, not the operator's real tape.
fn demo_header() -> &'static str {
    "DEMO FIXTURE: a synthetic economy demo tape, minted fresh this run — never your real MicroTape."
}

fn render_operator_status_demo() -> Result<String, String> {
    let body = render_operator_status(SnapshotInput::Demo)?;
    Ok(format!("{}\n{body}", demo_header()))
}

fn render_operator_panoview_demo(ascii: bool) -> Result<String, String> {
    let body = render_operator_panoview(SnapshotInput::Demo, ascii)?;
    Ok(format!("{}\n{body}", demo_header()))
}

fn demo_replay_verify() -> Result<String, String> {
    let report = run_new_project_agent_economy_demo()
        .map_err(|error| format!("demo replay failed: {error}"))?;
    Ok(format!(
        "{}\nreplay: verified tape_tip={} accepted_head={} qualification=private-local",
        demo_header(),
        report.tape_tip,
        report.accepted_head
    ))
}

/// `turing replay --verify --micro-git <path>`: the same replay-verify contract as the demo
/// command, but against the operator's real tape (F4).
fn replay_verify_real(path: &str) -> Result<String, String> {
    let repo = canonicalize_micro_git(path)?;
    let reconstruction = replay_guarded(&repo)?;
    Ok(format!(
        "replay: verified tape_tip={} accepted_head={} source=guarded_micro_tape_read",
        reconstruction.head_set().tape_tip,
        reconstruction.head_set().accepted_head
    ))
}

/// `turing audit invariants --micro-git <path>`: replay a single real tape end-to-end and
/// confirm it produced a coherent accepted-state sequence (F4).
fn audit_invariants_real(path: &str) -> Result<String, String> {
    let repo = canonicalize_micro_git(path)?;
    let reconstruction = replay_guarded(&repo)?;
    Ok(format!(
        "audit invariants: pass accepted_head={} source=guarded_micro_tape_read event_count={}",
        reconstruction.head_set().accepted_head,
        reconstruction.event_count()
    ))
}

fn render_operator_panoview(input: SnapshotInput<'_>, ascii: bool) -> Result<String, String> {
    let snapshot = operator_snapshot(input)?;
    let mut out = String::new();
    out.push_str("operator_view_snapshot.v1 panoview\n");
    out.push_str(&format!(
        "source={} micro_repo={} rebuild={} can_write_truth={}\n",
        snapshot.source.source_kind,
        snapshot.source.micro_repo,
        snapshot.source.rebuild_command,
        snapshot.source.can_write_truth
    ));
    out.push_str("heads:\n");
    out.push_str(&format!("  tape_tip={}\n", snapshot.heads.tape_tip));
    out.push_str(&format!(
        "  authorization_head={}\n",
        snapshot
            .heads
            .authorization_head
            .as_deref()
            .unwrap_or("null")
    ));
    out.push_str(&format!(
        "  accepted_head={}\n",
        snapshot.heads.accepted_head
    ));
    out.push_str("lanes:\n");
    for lane in &snapshot.lanes {
        let label = match lane.name.as_str() {
            "append" => "tape_tip",
            "authorization" => "authorization_head",
            "accepted" => "accepted_head",
            other => other,
        };
        out.push_str(&format!(
            "  {}={} meaning={}\n",
            label,
            lane.head.as_deref().unwrap_or("null"),
            lane.meaning
        ));
    }
    out.push_str("evidence:\n");
    for evidence in &snapshot.evidence {
        out.push_str(&format!("  - {evidence}\n"));
    }
    out.push_str("failures:\n");
    if snapshot.failures.is_empty() {
        out.push_str("  - none in snapshot\n");
    }
    out.push_str("warnings:\n");
    for warning in &snapshot.warnings {
        out.push_str(&format!(
            "  - {} severity={} message={}\n",
            warning.code, warning.severity, warning.message
        ));
    }
    out.push_str("safe commands:\n");
    for command in &snapshot.safe_commands {
        out.push_str(&format!(
            "  {} approval_required={} side_effect_class={} writes_truth={} confirmation_route={}\n",
            command.verb.as_str(),
            command.approval_required,
            command.side_effect_class.as_str(),
            command.writes_truth,
            command.confirmation_route.as_str()
        ));
    }
    // PER-ITEM SNAPSHOT CONTRACT (design spec §2): only rendered when the builder actually
    // derived per-item state. A legacy snapshot (`work_items: None` — no capsule-dispatch
    // events on the source tape, or the demo path, which deliberately skips derivation)
    // renders none of this, byte-identical to before this atom.
    if let Some(work_items) = &snapshot.work_items {
        out.push_str(&render_work_items(work_items, ascii));
    }
    Ok(out.trim_end().to_string())
}

/// Render the additive `work_items` block: the two-numbers header (spec 2.2), a spatial
/// split between not-yet-accepted and accepted lanes (2.3), one glyph line per item (2.1),
/// and the roll-up sentence (2.4). `ascii` selects the closed enum's ASCII column and an
/// ASCII-safe arrow/separator instead of unicode — the label is always printed either way,
/// so no information is lost in either mode (color is never emitted at all by this CLI, so
/// `NO_COLOR` is honored trivially: there is no color to suppress).
fn render_work_items(items: &[turing_projection::WorkItem], ascii: bool) -> String {
    let claimed_complete = items.iter().filter(|item| item.claimed_complete).count();
    let accepted = items
        .iter()
        .filter(|item| item.stage == turing_projection::WorkItemStage::Accepted)
        .count();
    let no_receipt = items
        .iter()
        .filter(|item| item.claimed_complete && item.receipt.is_none())
        .count();
    let arrow = if ascii { "->" } else { "\u{2192}" };
    let dot = if ascii { " * " } else { " \u{b7} " };

    let mut out = String::new();
    out.push_str("work_items:\n");
    out.push_str(&format!(
        "  CLAIMED COMPLETE: {claimed_complete}    ACCEPTED WORLD STATE: {accepted}"
    ));
    if no_receipt > 0 {
        let plural = if no_receipt == 1 {
            "claim has"
        } else {
            "claims have"
        };
        out.push_str(&format!("    {arrow} {no_receipt} {plural} no receipt"));
    }
    out.push('\n');

    let roll_up: Vec<String> = turing_projection::WorkItemStage::all()
        .into_iter()
        .filter_map(|stage| {
            let count = items.iter().filter(|item| item.stage == stage).count();
            (count > 0).then(|| format!("{count} {}", stage.as_str().replace('_', " ")))
        })
        .collect();
    out.push_str(&format!("  Plan: {}\n", roll_up.join(dot)));

    // Spatial split (spec 2.3): not-yet-accepted work in its own lane, separated by a
    // dotted rule from accepted state. `Vec::partition` preserves each side's relative
    // (tape) order.
    let (accepted_items, pending_items): (Vec<_>, Vec<_>) = items
        .iter()
        .partition(|item| item.stage == turing_projection::WorkItemStage::Accepted);
    if !pending_items.is_empty() {
        out.push_str("  not yet accepted:\n");
        for item in &pending_items {
            out.push_str(&render_work_item_line(item, ascii, dot));
        }
    }
    if !pending_items.is_empty() && !accepted_items.is_empty() {
        out.push_str(&format!("  {}\n", ".".repeat(20)));
    }
    if !accepted_items.is_empty() {
        out.push_str("  accepted:\n");
        for item in &accepted_items {
            out.push_str(&render_work_item_line(item, ascii, dot));
        }
    }
    out
}

/// One item's collapsed one-line summary (spec 2.5: "the collapsed line IS the product" —
/// it must be trustworthy on its own, never a bare heading requiring expansion).
fn render_work_item_line(item: &turing_projection::WorkItem, ascii: bool, dot: &str) -> String {
    let glyph = if ascii {
        item.stage.ascii_glyph()
    } else {
        item.stage.glyph()
    };
    let mut line = format!(
        "    {glyph} {label} id={} title={:?} claimed_complete={}",
        item.id,
        item.title,
        item.claimed_complete,
        label = item.stage.label(),
    );
    if let Some(receipt) = &item.receipt {
        line.push_str(&format!("{dot}receipt {} matched", receipt.receipt_id));
    } else if item.claimed_complete {
        line.push_str(&format!("{dot}no receipt on tape"));
    }
    if let Some(reason) = &item.blocked_reason {
        line.push_str(&format!("{dot}BLOCKED: {reason}"));
    }
    line.push('\n');
    line
}

fn render_operator_explain(
    verb: TypedVerb,
    input: SnapshotInput<'_>,
    event_id: Option<&str>,
) -> Result<String, String> {
    let snapshot = operator_snapshot(input)?;
    let spec = CommandSpec::get(verb).ok_or_else(|| "unknown explain verb".to_string())?;
    let event_text = event_id
        .map(|id| format!(" event_id={id}"))
        .unwrap_or_default();
    Ok(format!(
        "typed_command.v1 verb={}{} source_kind={} operator_view_snapshot.v1={} source_heads={} evidence_count={} replay={} blocker_policy=human_signature_required approval_required={} writes_truth={} exact_post_approval_state=NeedsApproval_or_AwaitingReceipt",
        spec.verb.as_str(),
        event_text,
        snapshot.source.source_kind,
        snapshot.snapshot_hash,
        spec.source_heads.join(","),
        snapshot.evidence.len(),
        spec.replay_command,
        spec.approval_required,
        spec.writes_truth
    ))
}

fn render_operator_ask(utterance: &str) -> Result<String, String> {
    let verb = route_utterance(utterance);
    let spec = CommandSpec::get(verb).ok_or_else(|| "unknown routed verb".to_string())?;
    let _trace = OperatorTurnTrace {
        schema_id: "operator_turn_trace.v1".to_string(),
        intent: turing_projection::OperatorIntent {
            schema_id: "operator_intent.v1".to_string(),
            utterance_digest: format!(
                "sha256:{}",
                turing_contracts::jcs::sha256_hex(utterance.as_bytes())
            ),
            selected_verb: verb,
            confidence_basis: "deterministic keyword router zh_en_v1".to_string(),
        },
        typed_command: spec.clone(),
        manifest: OperatorToolManifest::closed_v1(),
        advisory_confidence: "0.70".to_string(),
    };
    Ok(format!(
        "operator_turn_trace.v1 selected_verb={} typed_command.v1 approval_required={} writes_truth={} side_effect_class={} confirmation_route={} advisory_confidence=0.70 autonomous_dispatch=false",
        spec.verb.as_str(),
        spec.approval_required,
        spec.writes_truth,
        spec.side_effect_class.as_str(),
        spec.confirmation_route.as_str()
    ))
}

fn route_utterance(utterance: &str) -> TypedVerb {
    let lower = utterance.to_lowercase();
    if lower.contains("reject") && lower.contains("candidate") {
        TypedVerb::REJECT_CANDIDATE
    } else if lower.contains("dispatch") || lower.contains("worker") {
        TypedVerb::DISPATCH_WORKER
    } else if lower.contains("macro") && (lower.contains("auth") || lower.contains("authorization"))
    {
        TypedVerb::REQUEST_MACRO_AUTH
    } else if lower.contains("approve") && lower.contains("capsule") {
        TypedVerb::APPROVE_CAPSULE
    } else if lower.contains("approve")
        || lower.contains("批准")
        || lower.contains("接受")
        || lower.contains("candidate")
    {
        TypedVerb::APPROVE_CANDIDATE
    } else if lower.contains("blocker") || lower.contains("阻塞") {
        TypedVerb::EXPLAIN_BLOCKER
    } else if lower.contains("event") {
        TypedVerb::EXPLAIN_EVENT
    } else if lower.contains("observe") && lower.contains("capsule") {
        TypedVerb::OBSERVE_CAPSULE
    } else if lower.contains("status") || lower.contains("状态") {
        TypedVerb::VIEW_STATUS
    } else if lower.contains("panoview") || lower.contains("全景") {
        TypedVerb::VIEW_PANOVIEW
    } else if lower.contains("replay") {
        TypedVerb::REPLAY_VERIFY
    } else if lower.contains("audit") {
        TypedVerb::AUDIT_INVARIANTS
    } else if lower.contains("intent") {
        TypedVerb::PROPOSE_INTENT
    } else if lower.contains("goal") {
        TypedVerb::PROPOSE_GOAL
    } else if lower.contains("capsule") {
        TypedVerb::PROPOSE_CAPSULE
    } else {
        TypedVerb::HELP
    }
}

fn run_operator_console() -> Result<String, String> {
    let mut output = String::from("Operator Console v1 interactive wrapper\n");
    let mut buffer = String::new();
    use std::io::Read;
    std::io::stdin()
        .read_to_string(&mut buffer)
        .map_err(|error| format!("failed to read operator stdin: {error}"))?;
    for line in buffer.lines() {
        match line.trim() {
            "" => {}
            "quit" | "exit" => {
                output.push_str("operator console exit\n");
                break;
            }
            "status" => {
                output.push_str(&render_operator_status(SnapshotInput::Demo)?);
                output.push('\n');
            }
            "panoview" => {
                output.push_str(&render_operator_panoview(SnapshotInput::Demo, false)?);
                output.push('\n');
            }
            "help" => {
                output.push_str(&operator_help());
                output.push('\n');
            }
            other => {
                output.push_str(&render_operator_ask(other)?);
                output.push('\n');
            }
        }
    }
    Ok(output.trim_end().to_string())
}

fn approval_preview(
    approval_id: &str,
    authority_epoch: &str,
    action: &str,
    subject: &str,
    risk: &str,
    evidence_digest: &str,
    signature_route: &str,
) -> Result<String, String> {
    let card = build_approval_card(
        approval_id,
        authority_epoch,
        action,
        subject,
        risk,
        evidence_digest,
        signature_route,
    )?;
    let surfaces = card
        .byte_surfaces()
        .map_err(|error| format!("invalid approval card: {error}"))?;
    let snapshot = operator_snapshot(SnapshotInput::Demo)?;
    let source_head_values = format!(
        "tape_tip:{},authorization_head:{},accepted_head:{}",
        snapshot.heads.tape_tip,
        snapshot
            .heads
            .authorization_head
            .as_deref()
            .unwrap_or("null"),
        snapshot.heads.accepted_head
    );
    Ok(format!(
        "approval preview: approval_id={} action={} target={} subject={} risk={} source_heads=tape_tip,authorization_head,accepted_head source_head_values={} evidence_digest_count={} approval_required=true expiry=not_present nonce=not_present side_effect_class=sovereign_mutation post_approval_state=NeedsApproval_or_AwaitingReceipt authority_epoch={} signature_route={:?} visible_card_hash={} signed_payload_hash={} writes_micro_truth=false",
        approval_id,
        action,
        subject,
        subject,
        risk,
        source_head_values,
        card.payload().evidence_digests.len(),
        card.payload().authority_epoch,
        card.payload().signature_route,
        surfaces.visible_card_hash,
        surfaces.visible_card_hash,
    ))
}

#[allow(clippy::too_many_arguments)]
fn approval_sign(
    key_id: &str,
    approval_id: &str,
    authority_epoch: &str,
    action: &str,
    subject: &str,
    risk: &str,
    evidence_digest: &str,
    signature_route: &str,
    allow_test_signature: bool,
) -> Result<String, String> {
    let card = build_approval_card(
        approval_id,
        authority_epoch,
        action,
        subject,
        risk,
        evidence_digest,
        signature_route,
    )?;
    let (signature, trusted_keys) = match card.payload().signature_route {
        SignatureRoute::OsKeyring => {
            let signer = OsKeyringSigningBackend::new(key_id);
            let signature = signer.sign(&card);
            let trusted_keys = signer
                .authority_key_record(card.payload().authority_epoch)
                .map(AuthorityKeySet::from_record);
            (signature, trusted_keys)
        }
        SignatureRoute::InMemoryTest => {
            if !allow_test_signature {
                return Err(
                    "in-memory-test signing requires --allow-test-signature and is test-only"
                        .to_string(),
                );
            }
            let signer = InMemoryTestSigningBackend::new(key_id);
            let signature = signer.sign(&card);
            let trusted_keys = signer
                .authority_key_record(card.payload().authority_epoch)
                .map(AuthorityKeySet::from_record);
            (signature, trusted_keys)
        }
        SignatureRoute::HardwareFuture => {
            let signer = HardwareSigningBackend::slot(key_id);
            let signature = signer.sign(&card);
            let trusted_keys = signer
                .authority_key_record(card.payload().authority_epoch)
                .map(AuthorityKeySet::from_record);
            (signature, trusted_keys)
        }
        SignatureRoute::LocalFileDev => {
            return Err("approval sign does not expose local-file dev signing".to_string());
        }
        SignatureRoute::None => {
            return Err("approval sign requires a signing route, got none".to_string());
        }
    };
    let signature = signature.map_err(|error| format!("approval signing failed: {error}"))?;
    let trusted_keys =
        trusted_keys.map_err(|error| format!("approval authority key lookup failed: {error}"))?;
    match card.payload().signature_route {
        SignatureRoute::OsKeyring => OsKeyringSigningBackend::new(key_id)
            .verify(&card, &signature, &trusted_keys)
            .map_err(|error| format!("approval verification failed: {error}"))?,
        SignatureRoute::InMemoryTest => InMemoryTestSigningBackend::verifier(key_id)
            .verify(&card, &signature, &trusted_keys)
            .map_err(|error| format!("approval verification failed: {error}"))?,
        SignatureRoute::HardwareFuture => HardwareSigningBackend::slot(key_id)
            .verify(&card, &signature, &trusted_keys)
            .map_err(|error| format!("approval verification failed: {error}"))?,
        SignatureRoute::LocalFileDev => unreachable!(),
        SignatureRoute::None => unreachable!(),
    }
    let test_signature_only =
        matches!(card.payload().signature_route, SignatureRoute::InMemoryTest);
    Ok(format!(
        "approval signature: approval_id={} key_id={} authority_epoch={} signature_route={:?} test_signature_only={} signed_payload_hash={} public_key_fingerprint={} verifying_key={} signature={} writes_micro_truth=false",
        approval_id,
        signature.key_id,
        signature.authority_epoch,
        signature.signature_route,
        test_signature_only,
        signature.signed_payload_hash,
        signature.public_key_fingerprint,
        signature.verifying_key,
        signature.signature,
    ))
}

fn build_approval_card(
    approval_id: &str,
    authority_epoch: &str,
    action: &str,
    subject: &str,
    risk: &str,
    evidence_digest: &str,
    signature_route: &str,
) -> Result<ApprovalCard, String> {
    let authority_epoch = authority_epoch
        .parse::<u64>()
        .map_err(|error| format!("invalid authority epoch {authority_epoch:?}: {error}"))?;
    let signature_route = parse_signature_route(signature_route)?;
    Ok(ApprovalCard::new(
        ApprovalPayload {
            schema_id: APPROVAL_PAYLOAD_SCHEMA_ID.to_string(),
            approval_id: approval_id.to_string(),
            authority_epoch,
            action: action.to_string(),
            subject_id: subject.to_string(),
            evidence_digests: vec![evidence_digest.to_string()],
            risk_class: risk.to_string(),
            signature_route,
        },
        DisplayCopy {
            title_zh: "主权授权预览".to_string(),
            body_en: "Review this approval card before signing or dispatch.".to_string(),
        },
    ))
}

fn parse_signature_route(value: &str) -> Result<SignatureRoute, String> {
    match value {
        "none" => Ok(SignatureRoute::None),
        "os-keyring" => Ok(SignatureRoute::OsKeyring),
        "local-file-dev" => Ok(SignatureRoute::LocalFileDev),
        "in-memory-test" => Ok(SignatureRoute::InMemoryTest),
        "hardware-future" => Ok(SignatureRoute::HardwareFuture),
        other => Err(format!("unknown signature route {other:?}")),
    }
}

fn boot_project(project: &str) -> Result<String, String> {
    let project_root = canonicalize_project(project)?;
    write_boot_metadata(&project_root, None)
}

/// `turing boot --project <path> --micro-git <path>`: boots the project AND records a
/// configured default MicroTape, so a bare `turing status`/`panoview`/`doctor` run later from
/// this same directory resolves it instead of failing closed (F1 "configured default").
fn boot_project_with_micro_git(project: &str, micro_git: &str) -> Result<String, String> {
    let project_root = canonicalize_project(project)?;
    let micro_git_path = canonicalize_micro_git(micro_git)?;
    write_boot_metadata(&project_root, Some(micro_git_path.display().to_string()))
}

fn canonicalize_project(project: &str) -> Result<PathBuf, String> {
    std::fs::canonicalize(project).map_err(|_| {
        format!(
            "Can't find a project directory at {project}.\n{project} does not exist or isn't readable.\nRun: turing boot --project <valid-path>"
        )
    })
}

fn write_boot_metadata(project_root: &Path, micro_git: Option<String>) -> Result<String, String> {
    let state_dir = project_root.join(".turingos");
    std::fs::create_dir_all(&state_dir)
        .map_err(|error| format!("failed to create {}: {error}", state_dir.display()))?;
    let metadata_path = state_dir.join("project.json");
    let metadata = json!({
        "schema_id": "operator_project.v1",
        "project_root": project_root.to_string_lossy(),
        "truth_source": "micro_tape",
        "can_write_micro_truth": false,
        "credential_material_included": false,
        "micro_git": micro_git,
    });
    let text = serde_json::to_string(&metadata)
        .map_err(|error| format!("failed to serialize project metadata: {error}"))?;
    std::fs::write(&metadata_path, text)
        .map_err(|error| format!("failed to write {}: {error}", metadata_path.display()))?;
    Ok(format!("boot: wrote {}", metadata_path.display()))
}

/// One named check `turing doctor` ran, and whether it passed.
struct DoctorCheck {
    name: &'static str,
    passed: bool,
    detail: String,
}

/// A tape repo `turing doctor` resolved to check — either a real `--micro-git` path or a
/// scratch repo materialized from `--micro-bundle`. The `_scratch` guard (when present) must
/// outlive every read of `path` (its `Drop` removes the scratch directory).
struct ResolvedTapeRepo {
    path: PathBuf,
    _scratch: Option<BundleScratch>,
}

/// `turing doctor [--ci] [--micro-git <path> | --micro-bundle <path>]`. Manual flag parsing
/// (order-independent) rather than combinatorial match arms, since doctor has two independent
/// optional flags.
fn run_doctor(args: &[&str]) -> Result<String, String> {
    let mut ci = false;
    let mut micro_git: Option<&str> = None;
    let mut micro_bundle: Option<&str> = None;
    let mut index = 0;
    while index < args.len() {
        match args[index] {
            "--ci" => {
                ci = true;
                index += 1;
            }
            "--micro-git" => {
                let value = args.get(index + 1).ok_or_else(|| {
                    "turing doctor --micro-git needs a path.\n--micro-git was given with no value.\nRun: turing doctor --micro-git <path>"
                        .to_string()
                })?;
                micro_git = Some(value);
                index += 2;
            }
            "--micro-bundle" => {
                let value = args.get(index + 1).ok_or_else(|| {
                    "turing doctor --micro-bundle needs a path.\n--micro-bundle was given with no value.\nRun: turing doctor --micro-bundle <path>"
                        .to_string()
                })?;
                micro_bundle = Some(value);
                index += 2;
            }
            other => {
                return Err(format!(
                    "Unknown doctor flag: {other}.\nturing doctor does not recognize this flag.\nRun: turing doctor --help"
                ));
            }
        }
    }
    doctor_report(micro_git, micro_bundle, ci)
}

fn resolve_doctor_repo(
    micro_git: Option<&str>,
    micro_bundle: Option<&str>,
) -> Result<ResolvedTapeRepo, String> {
    if let Some(path) = micro_git {
        let canon = canonicalize_micro_git(path)?;
        return Ok(ResolvedTapeRepo {
            path: canon,
            _scratch: None,
        });
    }
    if let Some(bundle_path) = micro_bundle {
        let (_bundle, scratch_path, scratch) = materialize_bundle_scratch(bundle_path)?;
        return Ok(ResolvedTapeRepo {
            path: scratch_path,
            _scratch: Some(scratch),
        });
    }
    match resolve_default_micro_git() {
        Some(path) => {
            let canon = canonicalize_micro_git(&path)?;
            Ok(ResolvedTapeRepo {
                path: canon,
                _scratch: None,
            })
        }
        None => Err(no_tape_configured_error("doctor")),
    }
}

fn check_binary_deps() -> DoctorCheck {
    match std::process::Command::new("git").arg("--version").output() {
        Ok(output) if output.status.success() => DoctorCheck {
            name: "binary_deps",
            passed: true,
            detail: format!(
                "git available ({})",
                String::from_utf8_lossy(&output.stdout).trim()
            ),
        },
        Ok(output) => DoctorCheck {
            name: "binary_deps",
            passed: false,
            detail: format!(
                "git exited {} — turing needs a working git on PATH. Install git, then re-run: turing doctor",
                output.status
            ),
        },
        Err(_) => DoctorCheck {
            name: "binary_deps",
            passed: false,
            detail: "git is not on PATH — turing needs a working git binary. Install git, then re-run: turing doctor".to_string(),
        },
    }
}

/// Render every check as one named PASS/FAIL line. `--ci` emits a single machine-parseable
/// `check=<name> status=<PASS|FAIL> detail=<...>` line per check with no header and no
/// decoration; the interactive form keeps a FAIL line louder than a PASS line (anomaly louder
/// than checkmark).
fn render_doctor_checks(checks: &[DoctorCheck], ci: bool) -> String {
    let mut lines = Vec::new();
    if !ci {
        lines.push("turing doctor".to_string());
    }
    for check in checks {
        if ci {
            lines.push(format!(
                "check={} status={} detail={}",
                check.name,
                if check.passed { "PASS" } else { "FAIL" },
                check.detail.replace('\n', " ")
            ));
        } else if check.passed {
            lines.push(format!("PASS  {}: {}", check.name, check.detail));
        } else {
            lines.push(format!("FAIL  {}: {}", check.name, check.detail));
        }
    }
    lines.join("\n")
}

/// `turing doctor`'s two checks (F4): (1) binary + dependency availability, (2) a real replay
/// verify of the configured/passed tape via [`turing_replay::replay_tape`]. Any FAIL exits
/// nonzero (mapped through `Err`) and names the failing check with its typed corruption detail.
fn doctor_report(
    micro_git: Option<&str>,
    micro_bundle: Option<&str>,
    ci: bool,
) -> Result<String, String> {
    let mut checks = vec![check_binary_deps()];
    let repo = resolve_doctor_repo(micro_git, micro_bundle)?;

    match open_guarded_heads(&repo.path) {
        Ok(heads) => {
            checks.push(DoctorCheck {
                name: "tape_resolved",
                passed: true,
                detail: repo.path.display().to_string(),
            });
            match turing_replay::replay_tape(&repo.path, &heads.tape_tip) {
                Ok(reconstruction) => checks.push(DoctorCheck {
                    name: "replay_verify",
                    passed: true,
                    detail: format!(
                        "tape_tip={} accepted_head={} event_count={}",
                        reconstruction.head_set().tape_tip,
                        reconstruction.head_set().accepted_head,
                        reconstruction.event_count()
                    ),
                }),
                Err(error) => checks.push(DoctorCheck {
                    name: "replay_verify",
                    passed: false,
                    detail: error.to_string(),
                }),
            }
        }
        Err(message) => checks.push(DoctorCheck {
            name: "tape_resolved",
            passed: false,
            detail: message,
        }),
    }

    let total = checks.len();
    let failed = checks.iter().filter(|check| !check.passed).count();
    let report = render_doctor_checks(&checks, ci);
    if failed == 0 {
        Ok(format!("{report}\ndoctor: PASS ({total}/{total} checks)"))
    } else {
        Err(format!(
            "{report}\ndoctor: FAIL ({failed}/{total} checks failed)\nturing doctor found a problem with this tape — see the FAIL line above.\nRun: turing explain blocker --micro-git {}   (or fix it, then re-run: turing doctor --micro-git {})",
            repo.path.display(),
            repo.path.display()
        ))
    }
}

fn generate_handoff(output: &str) -> Result<String, String> {
    let report = run_new_project_agent_economy_demo()
        .map_err(|error| format!("handoff qualification failed: {error}"))?;
    let path = Path::new(output);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|error| format!("failed to create handoff directory: {error}"))?;
    }
    let authorization_head = report
        .authorization_head
        .clone()
        .unwrap_or_else(|| "null".to_string());
    let text = format!(
        r#"# Agent Economy Runtime Handoff

Status: generated private-local qualification handoff.

## Head Evidence

- tape_tip: {tape_tip}
- authorization_head: {authorization_head}
- accepted_head: {accepted_head}

## Projection Evidence

- market projection hash: {market_projection_hash}
- wallet projection hash: {wallet_projection_hash}
- PPUT projection hash: {pput_projection_hash}
- disposable projection hash: {projection_rebuild_hash}

## Replay And Audit Commands

```bash
cargo test --workspace
bash demo/demo_agent_economy_e2e.sh
bash demo/demo_rescue_agent_economy.sh
scripts/install-local.sh --prefix /tmp/turingos-local --profile debug
turing approval preview --approval-id ap_preview --authority-epoch 1 --action capsule_approve --subject wc_latest --risk P2 --evidence-digest sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --signature-route none
turing approval sign --key-id operator-local-key --approval-id ap_sign --authority-epoch 1 --action capsule_approve --subject wc_latest --risk P2 --evidence-digest sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb --signature-route os-keyring
turing replay --verify
turing market replay --verify
turing pput replay --verify
turing audit invariants
turing audit market
turing audit pput
turingd --check
turing-execd --check
turing-marketd --check
turing-pputd --check
turing-viewd --check
turing-mcp --check
```

## Known Risks

- Generated evidence is from a temporary private-local qualification Tape.
- `turingd` has Unix socket JSON-RPC health/read-only heads, configured `--micro-git` head
  reads, goal submission, capsule dispatch approval/rejection, preserve-only append,
  predicate-routed candidate verify/write with an expanded CandidateAccepted predicate pack
  covering capsule/macro/worker/scope/budget/provenance/replay, minimal OS-keyring atom
  authorization, read-only ApprovalCard preview/sign UX, and read-only persistent project status.
  hardware-future route fails closed until a real hardware backend is wired.
- `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, and `turing-viewd` have
  minimal sidecar RPCs for grant authorization, fake worker dispatch, resource manifests, shadow
  budget suggestion, prompt shielding, disposable projection building, and read-only project
  status. `turing-viewd` also supports derived project-scoped projection snapshot write with
  `can_write_truth=false`; `turing-marketd` supports derived project-scoped market projection
  snapshot write with `price_not_truth=true` and wallet projection snapshot write with
  `credential_material_included=false`; `turing-pputd` supports hidden project-scoped
  PPUT projection snapshot write with `hidden_from_worker_prompt=true` and `raw_formula_exposed=false`.
  All sidecar snapshot writes are derived-only and cannot own truth.
"#,
        tape_tip = report.tape_tip,
        authorization_head = authorization_head,
        accepted_head = report.accepted_head,
        market_projection_hash = report.market_projection_hash,
        wallet_projection_hash = report.wallet_projection_hash,
        pput_projection_hash = report.pput_projection_hash,
        projection_rebuild_hash = report.projection_rebuild_hash,
    );
    std::fs::write(path, text).map_err(|error| format!("failed to write handoff: {error}"))?;
    Ok(format!("handoff: wrote {}", path.display()))
}
