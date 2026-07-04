use std::io::{self, Read, Write};
use std::path::Path;
use std::process::ExitCode;

use serde_json::json;
use turing_approval::{
    APPROVAL_PAYLOAD_SCHEMA_ID, ApprovalCard, ApprovalPayload, AuthorityKeySet, DisplayCopy,
    HardwareSigningBackend, InMemoryTestSigningBackend, OsKeyringSigningBackend, SignatureRoute,
    SigningBackend,
};
use turing_contracts::jcs;
use turing_git_tape::append::Append;
use turing_projection::{
    CommandSpec, OperatorHeads, OperatorToolManifest, OperatorTurnTrace, OperatorViewSnapshot,
    TypedVerb,
};
use turing_qualification::{run_new_project_agent_economy_demo, run_rescue_agent_economy_demo};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let words: Vec<&str> = args.iter().map(String::as_str).collect();

    if words.first() == Some(&"jcs") {
        return match run_jcs_command(&words) {
            Ok(()) => ExitCode::SUCCESS,
            Err(message) => {
                eprintln!("{message}");
                ExitCode::from(2)
            }
        };
    }

    match dispatch(&words) {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(message) => {
            eprintln!("{message}");
            ExitCode::from(2)
        }
    }
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
        ["status"] => render_operator_status(SnapshotInput::Demo),
        ["status", "--micro-git", repo] => render_operator_status(SnapshotInput::MicroGit(repo)),
        ["status", "--micro-bundle", bundle] => {
            render_operator_status(SnapshotInput::MicroBundle(bundle))
        }
        ["panoview"] => render_operator_panoview(SnapshotInput::Demo),
        ["panoview", "--micro-git", repo] => {
            render_operator_panoview(SnapshotInput::MicroGit(repo))
        }
        ["panoview", "--micro-bundle", bundle] => {
            render_operator_panoview(SnapshotInput::MicroBundle(bundle))
        }
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
        ["ask", utterance @ ..] => render_operator_ask(&utterance.join(" ")),
        ["operator"] => run_operator_console(),
        ["boot", "--project", project] => boot_project(project),
        ["replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("replay verify failed: {error}"))?;
            Ok(format!(
                "replay: verified tape_tip={} accepted_head={} qualification=private-local",
                report.tape_tip, report.accepted_head
            ))
        }
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
        _ => Err(format!(
            "unknown turing command: {:?}. supported: status [--micro-git <path>|--micro-bundle <path>] | panoview [--micro-git <path>|--micro-bundle <path>] | explain blocker|event [event_id] [--micro-git <path>|--micro-bundle <path>] | ask <utterance> | operator | help commands | boot --project <path> | approval preview --approval-id <id> --authority-epoch <n> --action <action> --subject <id> --risk <risk> --evidence-digest <sha256> --signature-route <none|os-keyring|hardware-future> | approval sign --key-id <id> --approval-id <id> --authority-epoch <n> --action <action> --subject <id> --risk <risk> --evidence-digest <sha256> --signature-route os-keyring | approval sign ... --signature-route in-memory-test --allow-test-signature | replay --verify | market replay --verify | pput replay --verify | audit invariants|market|pput | handoff generate --output <path>",
            args
        )),
    }
}

fn operator_help() -> String {
    let verbs = CommandSpec::all()
        .iter()
        .map(|spec| spec.verb.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    format!(
        "Operator Console v1\ncontracts: operator_view_snapshot.v1 typed_command.v1 operator_intent.v1 operator_tool_manifest.v1 operator_turn_trace.v1\ncommands: status [--micro-git <path>|--micro-bundle <path>] | panoview [--micro-git <path>|--micro-bundle <path>] | explain blocker|event [--micro-git <path>|--micro-bundle <path>] | ask <utterance> | operator | help\nfixed verbs: {verbs}\nstatus ceiling: IMPLEMENTER_ADDRESSED until a real external human signature exists"
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
        "Operator Console v1 topic=commands\ncontract=operator_tool_manifest.v1 item_contract=typed_command.v1\n{rows}\nstatus_ceiling=IMPLEMENTER_ADDRESSED"
    )
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
    OperatorViewSnapshot::from_deterministic_replay(
        project_root,
        "qualification_demo_micro_tape",
        "turing replay --verify",
        heads,
    )
    .map_err(|error| format!("operator snapshot failed: {error}"))
}

fn micro_git_snapshot(path: &str) -> Result<OperatorViewSnapshot, String> {
    let micro_repo = std::fs::canonicalize(path)
        .map_err(|error| format!("failed to resolve micro git path {path:?}: {error}"))?;
    micro_git_snapshot_from_repo(
        &micro_repo,
        micro_repo.display().to_string(),
        format!("turing status --micro-git {}", micro_repo.display()),
    )
}

fn micro_bundle_snapshot(path: &str) -> Result<OperatorViewSnapshot, String> {
    let bundle = std::fs::canonicalize(path)
        .map_err(|error| format!("failed to resolve micro bundle path {path:?}: {error}"))?;
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
    micro_git_snapshot_from_repo(
        scratch.path(),
        format!("bundle:{}", bundle.display()),
        format!("turing status --micro-bundle {}", bundle.display()),
    )
}

fn micro_git_snapshot_from_repo(
    micro_repo: &Path,
    source_micro_repo: String,
    rebuild_command: String,
) -> Result<OperatorViewSnapshot, String> {
    let tape = Append::open(micro_repo)
        .map_err(|error| format!("cannot open micro tape {}: {error}", micro_repo.display()))?;
    let heads = tape
        .head_set_guarded()
        .map_err(|error| format!("guarded MicroTape head read failed: {error}"))?
        .ok_or_else(|| "micro tape is not booted; no operator heads are available".to_string())?;
    let heads = OperatorHeads::new(
        heads.tape_tip,
        heads.authorization_head,
        heads.accepted_head,
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
    )
    .map_err(|error| format!("operator snapshot failed: {error}"))
}

struct BundleScratch {
    path: std::path::PathBuf,
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
        "operator_view_snapshot.v1 heartbeat source_kind={} operator_state={} tape_tip={} authorization_head={} accepted_head={} can_write_truth={} status_ceiling=IMPLEMENTER_ADDRESSED snapshot_hash={}",
        snapshot.source.source_kind,
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

fn render_operator_panoview(input: SnapshotInput<'_>) -> Result<String, String> {
    let snapshot = operator_snapshot(input)?;
    let mut out = String::new();
    out.push_str("operator_view_snapshot.v1 panoview\n");
    out.push_str(&format!(
        "source={} rebuild={} can_write_truth={}\n",
        snapshot.source.source_kind,
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
    Ok(out.trim_end().to_string())
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
                output.push_str(&render_operator_panoview(SnapshotInput::Demo)?);
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
    let project_root = std::fs::canonicalize(project)
        .map_err(|error| format!("failed to resolve project path {project:?}: {error}"))?;
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
    });
    let text = serde_json::to_string(&metadata)
        .map_err(|error| format!("failed to serialize project metadata: {error}"))?;
    std::fs::write(&metadata_path, text)
        .map_err(|error| format!("failed to write {}: {error}", metadata_path.display()))?;
    Ok(format!("boot: wrote {}", metadata_path.display()))
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
