use std::path::Path;
use std::process::ExitCode;

use serde_json::json;
use turing_approval::{
    APPROVAL_PAYLOAD_SCHEMA_ID, ApprovalCard, ApprovalPayload, DisplayCopy, HardwareSigningBackend,
    OsKeyringSigningBackend, SignatureRoute, SigningBackend,
};
use turing_qualification::{run_new_project_agent_economy_demo, run_rescue_agent_economy_demo};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let words: Vec<&str> = args.iter().map(String::as_str).collect();

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

fn dispatch(args: &[&str]) -> Result<String, String> {
    match args {
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
        ),
        _ => Err(format!(
            "unknown turing command: {:?}. supported: boot --project <path> | approval preview --approval-id <id> --authority-epoch <n> --action <action> --subject <id> --risk <risk> --evidence-digest <sha256> --signature-route <none|os-keyring|hardware-future> | approval sign --key-id <id> --approval-id <id> --authority-epoch <n> --action <action> --subject <id> --risk <risk> --evidence-digest <sha256> --signature-route os-keyring | replay --verify | market replay --verify | pput replay --verify | audit invariants|market|pput | handoff generate --output <path>",
            args
        )),
    }
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
    Ok(format!(
        "approval preview: approval_id={} action={} subject={} risk={} authority_epoch={} signature_route={:?} visible_card_hash={} signed_payload_hash={} writes_micro_truth=false",
        approval_id,
        action,
        subject,
        risk,
        card.payload().authority_epoch,
        card.payload().signature_route,
        surfaces.visible_card_hash,
        surfaces.visible_card_hash,
    ))
}

fn approval_sign(
    key_id: &str,
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
    let signature = match card.payload().signature_route {
        SignatureRoute::OsKeyring => OsKeyringSigningBackend::new(key_id).sign(&card),
        SignatureRoute::HardwareFuture => HardwareSigningBackend::slot(key_id).sign(&card),
        SignatureRoute::None => {
            return Err("approval sign requires a signing route, got none".to_string());
        }
    }
    .map_err(|error| format!("approval signing failed: {error}"))?;
    Ok(format!(
        "approval signature: approval_id={} key_id={} authority_epoch={} signature_route={:?} signed_payload_hash={} signature={} writes_micro_truth=false",
        approval_id,
        signature.key_id,
        signature.authority_epoch,
        signature.signature_route,
        signature.signed_payload_hash,
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
  status. Broader project-scoped mutable sidecar services remain pending.
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
