//! Process topology contracts for private-local TuringOS daemons.

use std::io::{BufRead, BufReader, Write};
#[cfg(unix)]
use std::os::unix::net::UnixListener;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use serde_json::{Value, json};
use turing_approval::{
    ApprovalCard, ApprovalPayload, DisplayCopy, OsKeyringSigningBackend,
    SignatureRoute as ApprovalSignatureRoute, SigningBackend,
};
use turing_contracts::envelope::HeadEffect;
use turing_contracts::envelope::PredicateProduct;
use turing_contracts::failure::{FailureClass, FailureNodePayload};
use turing_contracts::goal::GoalState;
use turing_contracts::jcs;
use turing_contracts::registry;
use turing_economy::{
    AmmSwapExecuted, CandidateRoute, EconomyEvent, MarketCreated, MarketReplay, MarketRouter,
    MarketRouterMode, MarketSettled, PositionMinted, PriceSignal, RewardDistributed,
};
use turing_execd::capability::{
    ActionClass, Budget, CapabilityGrant, CapabilityScope, NetworkScope, Risk, RiskClass,
    SignatureRoute, ToolRequest,
};
use turing_execd::{FakeWorker, WorkerRunRequest};
use turing_git_tape::append::{Append, AppendRequest, HeadMoved};
use turing_pput::{CostEvent, PputProjection, Split, WorkerPromptShield};
use turing_predicate::{PredicateCheck, PredicateKernel};
use turing_projection::{ProjectionBuilder, ProjectionEvent, ProjectionSource};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DaemonContract {
    pub role: &'static str,
    pub can_move_accepted_head: bool,
}

impl DaemonContract {
    #[must_use]
    pub fn check_line(self) -> String {
        format!(
            "role={} can_move_accepted_head={} single_loop_subroutine=true",
            self.role, self.can_move_accepted_head
        )
    }
}

#[derive(Debug, Clone)]
struct DaemonRuntime {
    contract: DaemonContract,
    micro_git: Option<PathBuf>,
    project_root: Option<PathBuf>,
}

pub fn run_daemon(contract: DaemonContract) -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [serve, socket_flag, socket] if serve == "--serve" && socket_flag == "--socket" => {
            let runtime = DaemonRuntime {
                contract,
                micro_git: None,
                project_root: None,
            };
            match serve_unix_socket(runtime, socket) {
                Ok(()) => ExitCode::SUCCESS,
                Err(error) => {
                    eprintln!("{} serve failed: {error}", contract.role);
                    ExitCode::from(2)
                }
            }
        }
        [serve, socket_flag, socket, micro_git_flag, micro_git]
            if serve == "--serve"
                && socket_flag == "--socket"
                && micro_git_flag == "--micro-git" =>
        {
            let runtime = DaemonRuntime {
                contract,
                micro_git: Some(PathBuf::from(micro_git)),
                project_root: None,
            };
            match serve_unix_socket(runtime, socket) {
                Ok(()) => ExitCode::SUCCESS,
                Err(error) => {
                    eprintln!("{} serve failed: {error}", contract.role);
                    ExitCode::from(2)
                }
            }
        }
        [serve, socket_flag, socket, project_flag, project]
            if serve == "--serve" && socket_flag == "--socket" && project_flag == "--project" =>
        {
            let runtime = DaemonRuntime {
                contract,
                micro_git: None,
                project_root: Some(PathBuf::from(project)),
            };
            match serve_unix_socket(runtime, socket) {
                Ok(()) => ExitCode::SUCCESS,
                Err(error) => {
                    eprintln!("{} serve failed: {error}", contract.role);
                    ExitCode::from(2)
                }
            }
        }
        [
            serve,
            socket_flag,
            socket,
            micro_git_flag,
            micro_git,
            project_flag,
            project,
        ] if serve == "--serve"
            && socket_flag == "--socket"
            && micro_git_flag == "--micro-git"
            && project_flag == "--project" =>
        {
            let runtime = DaemonRuntime {
                contract,
                micro_git: Some(PathBuf::from(micro_git)),
                project_root: Some(PathBuf::from(project)),
            };
            match serve_unix_socket(runtime, socket) {
                Ok(()) => ExitCode::SUCCESS,
                Err(error) => {
                    eprintln!("{} serve failed: {error}", contract.role);
                    ExitCode::from(2)
                }
            }
        }
        [flag] if flag == "--check" => {
            println!("{}", contract.check_line());
            ExitCode::SUCCESS
        }
        [cmd] if cmd == "move-accepted-head" => {
            if contract.can_move_accepted_head {
                println!(
                    "accepted_head movement is routed through turingd predicate/approval gate"
                );
                ExitCode::SUCCESS
            } else {
                eprintln!("{} cannot move accepted_head", contract.role);
                ExitCode::from(2)
            }
        }
        _ => {
            eprintln!("unknown {} command", contract.role);
            ExitCode::from(2)
        }
    }
}

#[cfg(unix)]
fn serve_unix_socket(runtime: DaemonRuntime, socket: &str) -> std::io::Result<()> {
    let path = Path::new(socket);
    if path.exists() {
        std::fs::remove_file(path)?;
    }
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let listener = UnixListener::bind(path)?;
    for stream in listener.incoming() {
        let mut stream = stream?;
        let mut line = String::new();
        BufReader::new(stream.try_clone()?).read_line(&mut line)?;
        let request: Value = serde_json::from_str(line.trim()).unwrap_or_else(|_| {
            json!({
                "id": Value::Null,
                "method": "__malformed__",
            })
        });
        let shutdown = request.get("method").and_then(Value::as_str) == Some("daemon.shutdown");
        let response = jsonrpc_response(&runtime, &request);
        writeln!(stream, "{response}")?;
        if shutdown {
            break;
        }
    }
    Ok(())
}

#[cfg(not(unix))]
fn serve_unix_socket(_runtime: DaemonRuntime, _socket: &str) -> std::io::Result<()> {
    Err(std::io::Error::other(
        "Unix sockets are required for private-local daemon tests",
    ))
}

fn jsonrpc_response(runtime: &DaemonRuntime, request: &Value) -> Value {
    let id = request.get("id").cloned().unwrap_or(Value::Null);
    match request.get("method").and_then(Value::as_str) {
        Some("daemon.check") => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "role": runtime.contract.role,
                "can_move_accepted_head": runtime.contract.can_move_accepted_head,
                "single_loop_subroutine": true,
            }
        }),
        Some("heads.read") => read_heads_response(runtime, id),
        Some("project.status") => project_status_response(runtime, id),
        Some("event.append_preserve") if runtime.contract.role == "turingd" => {
            append_preserve_response(runtime, request, id)
        }
        Some("candidate.verify_write") if runtime.contract.role == "turingd" => {
            candidate_verify_write_response(runtime, request, id)
        }
        Some("approval.authorize_atom") if runtime.contract.role == "turingd" => {
            approval_authorize_atom_response(runtime, request, id)
        }
        Some("goal.submit") if runtime.contract.role == "turingd" => {
            goal_submit_response(runtime, request, id)
        }
        Some("capsule.approve") if runtime.contract.role == "turingd" => {
            capsule_approve_response(runtime, request, id)
        }
        Some("capsule.reject") if runtime.contract.role == "turingd" => {
            capsule_reject_response(runtime, request, id)
        }
        Some("grant.authorize") if runtime.contract.role == "turing-execd" => {
            grant_authorize_response(request, id)
        }
        Some("dispatch.request") if runtime.contract.role == "turing-execd" => {
            dispatch_request_response(request, id)
        }
        Some("mcp.resources.list") if runtime.contract.role == "turing-mcp" => {
            mcp_resources_list_response(id)
        }
        Some("market.shadow.suggest") if runtime.contract.role == "turing-marketd" => {
            market_shadow_suggest_response(request, id)
        }
        Some("market.snapshot.write") if runtime.contract.role == "turing-marketd" => {
            market_snapshot_write_response(runtime, request, id)
        }
        Some("pput.prompt.validate") if runtime.contract.role == "turing-pputd" => {
            pput_prompt_validate_response(request, id)
        }
        Some("pput.snapshot.write") if runtime.contract.role == "turing-pputd" => {
            pput_snapshot_write_response(runtime, request, id)
        }
        Some("projection.build") if runtime.contract.role == "turing-viewd" => {
            projection_build_response(request, id)
        }
        Some("projection.snapshot.write") if runtime.contract.role == "turing-viewd" => {
            projection_snapshot_write_response(runtime, request, id)
        }
        Some("daemon.shutdown") => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "shutdown": true,
            }
        }),
        Some(method) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": -32601,
                "message": format!("unknown method {method}"),
            }
        }),
        None => json!({
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": -32600,
                "message": "invalid request",
            }
        }),
    }
}

fn append_preserve_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return jsonrpc_error(
            id,
            -32000,
            "event.append_preserve requires --micro-git".to_string(),
        );
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let event_type = match required_str(params, "event_type") {
        Ok(event_type) => event_type,
        Err(message) => return invalid_params(id, message),
    };
    let writer_id = match required_str(params, "writer_id") {
        Ok(writer_id) => writer_id,
        Err(message) => return invalid_params(id, message),
    };
    let payload = match params.get("payload") {
        Some(payload) => payload.clone(),
        None => return invalid_params(id, "payload is required"),
    };
    let Some(row) = registry::registry(&event_type) else {
        return jsonrpc_error(id, -32000, format!("unknown event_type {event_type:?}"));
    };
    if row.head_effect != HeadEffect::Preserve {
        return jsonrpc_error(
            id,
            -32000,
            format!("event_type {event_type:?} is not a PRESERVE event"),
        );
    }

    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };
    let receipt =
        match tape.append(AppendRequest::new(&event_type, writer_id, payload).predicate_pass()) {
            Ok(receipt) => receipt,
            Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
        };
    let accepted_head_moved = matches!(receipt.head_moved, HeadMoved::AcceptedHead);
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "event_type": event_type,
            "event_id": receipt.event_id,
            "head_effect": "PRESERVE",
            "accepted_head_moved": accepted_head_moved,
            "can_move_accepted_head": false,
            "head_set": {
                "tape_tip": receipt.tape_tip_after,
                "authorization_head": receipt.authorization_head_after,
                "accepted_head": receipt.accepted_head_after,
            }
        }
    })
}

fn goal_submit_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return jsonrpc_error(id, -32000, "goal.submit requires --micro-git".to_string());
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let writer_id = match required_str(params, "writer_id") {
        Ok(writer_id) => writer_id,
        Err(message) => return invalid_params(id, message),
    };
    let goal = match params.get("goal").map(parse_goal_state) {
        Some(Ok(goal)) => goal,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "goal object is required"),
    };
    let goal_id = goal.goal_id.clone();
    let goal_bytes = match goal.to_jcs_bytes() {
        Ok(bytes) => bytes,
        Err(error) => return invalid_params(id, format!("goal canonicalization failed: {error}")),
    };
    let goal_digest = format!("sha256:{}", jcs::sha256_hex(&goal_bytes));
    let goal_value = serde_json::to_value(&goal).expect("GoalState serializes to JSON");

    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };
    let receipt = match tape.append(
        AppendRequest::new(
            "GoalStateProposed",
            writer_id,
            json!({
                "goal_state": goal_value,
                "goal_digest": goal_digest,
                "submitted_via": "goal.submit",
            }),
        )
        .predicate_pass(),
    ) {
        Ok(receipt) => receipt,
        Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
    };

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "event_type": "GoalStateProposed",
            "event_id": receipt.event_id,
            "goal_id": goal_id,
            "goal_digest": goal_digest,
            "head_effect": "PRESERVE",
            "accepted_head_moved": matches!(receipt.head_moved, HeadMoved::AcceptedHead),
            "head_set": {
                "tape_tip": receipt.tape_tip_after,
                "authorization_head": receipt.authorization_head_after,
                "accepted_head": receipt.accepted_head_after,
            }
        }
    })
}

fn capsule_reject_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return jsonrpc_error(
            id,
            -32000,
            "capsule.reject requires --micro-git".to_string(),
        );
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let writer_id = match required_str(params, "writer_id") {
        Ok(writer_id) => writer_id,
        Err(message) => return invalid_params(id, message),
    };
    let capsule_id = match required_str(params, "capsule_id") {
        Ok(capsule_id) => capsule_id,
        Err(message) => return invalid_params(id, message),
    };
    let capsule_digest = match required_digest(params, "capsule_digest") {
        Ok(digest) => digest,
        Err(message) => return invalid_params(id, message),
    };
    let observation_digest = match required_digest(params, "observation_digest") {
        Ok(digest) => digest,
        Err(message) => return invalid_params(id, message),
    };
    let detail = match optional_str(params, "detail") {
        Ok(detail) => detail,
        Err(message) => return invalid_params(id, message),
    };
    let failure = FailureNodePayload::new(
        FailureClass::SteerRejected,
        capsule_digest,
        observation_digest,
        detail,
    );

    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };
    let receipt = match tape.append(
        AppendRequest::new(
            "FailureNode",
            writer_id,
            serde_json::to_value(&failure).expect("FailureNodePayload serializes"),
        )
        .predicate_fail(),
    ) {
        Ok(receipt) => receipt,
        Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
    };

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "event_type": "FailureNode",
            "event_id": receipt.event_id,
            "capsule_id": capsule_id,
            "failure_class": FailureClass::SteerRejected.as_registry_str(),
            "authorization_head_moved": matches!(receipt.head_moved, HeadMoved::AuthorizationHead),
            "accepted_head_moved": matches!(receipt.head_moved, HeadMoved::AcceptedHead),
            "head_set": {
                "tape_tip": receipt.tape_tip_after,
                "authorization_head": receipt.authorization_head_after,
                "accepted_head": receipt.accepted_head_after,
            }
        }
    })
}

fn capsule_approve_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return jsonrpc_error(
            id,
            -32000,
            "capsule.approve requires --micro-git".to_string(),
        );
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let key_id = match required_str(params, "key_id") {
        Ok(key_id) => key_id,
        Err(message) => return invalid_params(id, message),
    };
    let payload = match params.get("payload").map(|payload| {
        parse_approval_payload_for_action(payload, "capsule_approve", "capsule.approve")
    }) {
        Some(Ok(payload)) => payload,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "payload object is required"),
    };
    let display_copy = match params.get("display_copy").map(parse_display_copy) {
        Some(Ok(display_copy)) => display_copy,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "display_copy object is required"),
    };
    let card = ApprovalCard::new(payload, display_copy);
    let surfaces = match card.byte_surfaces() {
        Ok(surfaces) => surfaces,
        Err(error) => return invalid_params(id, format!("invalid approval card: {error}")),
    };
    let signer = OsKeyringSigningBackend::new(key_id);
    let signature = match signer.sign(&card) {
        Ok(signature) => signature,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("approval signing failed: {error}"));
        }
    };

    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };
    let capsule_id = card.payload().subject_id.clone();
    let receipt = match tape.append(
        AppendRequest::new(
            "WorkerDispatchAuthorized",
            "writer:approval",
            json!({
                "approval_id": card.payload().approval_id,
                "capsule_id": capsule_id,
                "action": card.payload().action,
                "risk_class": card.payload().risk_class,
                "evidence_digests": card.payload().evidence_digests,
                "visible_card_hash": surfaces.visible_card_hash,
                "signed_payload_hash": signature.signed_payload_hash,
                "signature": signature.signature,
                "signature_route": approval_signature_route_str(signature.signature_route),
                "key_id": signature.key_id,
                "authority_epoch": signature.authority_epoch,
            }),
        )
        .predicate_pass(),
    ) {
        Ok(receipt) => receipt,
        Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
    };

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "event_type": "WorkerDispatchAuthorized",
            "event_id": receipt.event_id,
            "capsule_id": capsule_id,
            "authorization_head_moved": matches!(receipt.head_moved, HeadMoved::AuthorizationHead),
            "accepted_head_moved": matches!(receipt.head_moved, HeadMoved::AcceptedHead),
            "visible_card_hash": surfaces.visible_card_hash,
            "signed_payload_hash": signature.signed_payload_hash,
            "signature_route": approval_signature_route_str(signature.signature_route),
            "head_set": {
                "tape_tip": receipt.tape_tip_after,
                "authorization_head": receipt.authorization_head_after,
                "accepted_head": receipt.accepted_head_after,
            }
        }
    })
}

fn approval_authorize_atom_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return jsonrpc_error(
            id,
            -32000,
            "approval.authorize_atom requires --micro-git".to_string(),
        );
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let key_id = match required_str(params, "key_id") {
        Ok(key_id) => key_id,
        Err(message) => return invalid_params(id, message),
    };
    let payload = match params.get("payload").map(|payload| {
        parse_approval_payload_for_action(payload, "atom_authorize", "approval.authorize_atom")
    }) {
        Some(Ok(payload)) => payload,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "payload object is required"),
    };
    let display_copy = match params.get("display_copy").map(parse_display_copy) {
        Some(Ok(display_copy)) => display_copy,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "display_copy object is required"),
    };
    let card = ApprovalCard::new(payload, display_copy);
    let surfaces = match card.byte_surfaces() {
        Ok(surfaces) => surfaces,
        Err(error) => return invalid_params(id, format!("invalid approval card: {error}")),
    };
    let signer = OsKeyringSigningBackend::new(key_id);
    let signature = match signer.sign(&card) {
        Ok(signature) => signature,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("approval signing failed: {error}"));
        }
    };

    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };
    let receipt = match tape.append(
        AppendRequest::new(
            "AtomAuthorized",
            "writer:approval",
            json!({
                "approval_id": card.payload().approval_id,
                "subject_id": card.payload().subject_id,
                "action": card.payload().action,
                "risk_class": card.payload().risk_class,
                "evidence_digests": card.payload().evidence_digests,
                "visible_card_hash": surfaces.visible_card_hash,
                "signed_payload_hash": signature.signed_payload_hash,
                "signature": signature.signature,
                "signature_route": approval_signature_route_str(signature.signature_route),
                "key_id": signature.key_id,
                "authority_epoch": signature.authority_epoch,
            }),
        )
        .predicate_pass(),
    ) {
        Ok(receipt) => receipt,
        Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
    };

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "event_type": "AtomAuthorized",
            "event_id": receipt.event_id,
            "authorization_head_moved": matches!(receipt.head_moved, HeadMoved::AuthorizationHead),
            "accepted_head_moved": matches!(receipt.head_moved, HeadMoved::AcceptedHead),
            "visible_card_hash": surfaces.visible_card_hash,
            "signed_payload_hash": signature.signed_payload_hash,
            "signature_route": approval_signature_route_str(signature.signature_route),
            "head_set": {
                "tape_tip": receipt.tape_tip_after,
                "authorization_head": receipt.authorization_head_after,
                "accepted_head": receipt.accepted_head_after,
            }
        }
    })
}

fn candidate_verify_write_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return jsonrpc_error(
            id,
            -32000,
            "candidate.verify_write requires --micro-git".to_string(),
        );
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let writer_id = match required_str(params, "writer_id") {
        Ok(writer_id) => writer_id,
        Err(message) => return invalid_params(id, message),
    };
    let candidate_payload = match params.get("candidate_payload") {
        Some(payload) => payload.clone(),
        None => return invalid_params(id, "candidate_payload is required"),
    };
    let checks = match parse_predicate_checks(params) {
        Ok(checks) => checks,
        Err(message) => return invalid_params(id, message),
    };
    let checks = enforce_candidate_predicate_pack(checks, &candidate_payload);

    let report = match PredicateKernel.run("CandidateAccepted", checks) {
        Ok(report) => report,
        Err(error) => return jsonrpc_error(id, -32000, format!("predicate failed: {error}")),
    };
    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };

    let (write_event_type, failure_class, receipt) = if report.product == PredicateProduct::Pass {
        match tape.append(
            AppendRequest::new("CandidateAccepted", writer_id, candidate_payload).predicate_pass(),
        ) {
            Ok(receipt) => ("CandidateAccepted", None, receipt),
            Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
        }
    } else {
        let failure = match params.get("failure").map(parse_failure_payload) {
            Some(Ok(payload)) => payload,
            Some(Err(message)) => return invalid_params(id, message),
            None => return invalid_params(id, "failure object is required on predicate FAIL"),
        };
        match tape.append(
            AppendRequest::new(
                "FailureNode",
                writer_id,
                serde_json::to_value(&failure).expect("FailureNodePayload serializes"),
            )
            .predicate_fail(),
        ) {
            Ok(receipt) => ("FailureNode", Some(FailureClass::SemanticFailure), receipt),
            Err(error) => return jsonrpc_error(id, -32000, format!("append failed: {error}")),
        }
    };

    let accepted_head_moved = matches!(receipt.head_moved, HeadMoved::AcceptedHead);
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "write_event_type": write_event_type,
            "event_id": receipt.event_id,
            "predicate_product": predicate_product_str(report.product),
            "predicate_report_hash": report.report_hash,
            "failed_predicates": report.failed_predicates,
            "reject_class": report.reject_class,
            "failure_class": failure_class.map(FailureClass::as_registry_str),
            "accepted_head_moved": accepted_head_moved,
            "head_set": {
                "tape_tip": receipt.tape_tip_after,
                "authorization_head": receipt.authorization_head_after,
                "accepted_head": receipt.accepted_head_after,
            }
        }
    })
}

fn grant_authorize_response(request: &Value, id: Value) -> Value {
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let grant = match params.get("grant").map(parse_grant) {
        Some(Ok(grant)) => grant,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "grant object is required"),
    };
    let tool_request = match params.get("request").map(parse_tool_request) {
        Some(Ok(request)) => request,
        Some(Err(message)) => return invalid_params(id, message),
        None => return invalid_params(id, "request object is required"),
    };

    match grant.authorize(&tool_request) {
        Ok(()) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "authorized": true,
                "receipt_type": "ToolCallAuthorized",
                "can_move_accepted_head": false,
                "head_effect": "PRESERVE",
            }
        }),
        Err(error) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "authorized": false,
                "receipt_type": "ToolCallDenied",
                "denial": error.to_string(),
                "can_move_accepted_head": false,
                "head_effect": "PRESERVE",
            }
        }),
    }
}

fn dispatch_request_response(request: &Value, id: Value) -> Value {
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let worker_kind = match required_str(params, "worker_kind") {
        Ok(worker_kind) => worker_kind,
        Err(message) => return invalid_params(id, message),
    };
    if worker_kind != "Fake" {
        return invalid_params(
            id,
            format!("dispatch.request supports Fake worker_kind, got {worker_kind:?}"),
        );
    }
    let worker_id = match required_str(params, "worker_id") {
        Ok(worker_id) => worker_id,
        Err(message) => return invalid_params(id, message),
    };
    let capsule_id = match required_str(params, "capsule_id") {
        Ok(capsule_id) => capsule_id,
        Err(message) => return invalid_params(id, message),
    };
    let grant_id = match required_str(params, "grant_id") {
        Ok(grant_id) => grant_id,
        Err(message) => return invalid_params(id, message),
    };

    let worker = FakeWorker::new(worker_id);
    let receipt = match worker.run(WorkerRunRequest {
        capsule_id,
        grant_id,
    }) {
        Ok(receipt) => receipt,
        Err(error) => return jsonrpc_error(id, -32000, format!("dispatch failed: {error}")),
    };

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "receipt_type": "WorkerDispatched",
            "schema_id": receipt.schema_id,
            "receipt_id": receipt.receipt_id,
            "capsule_id": receipt.capsule_id,
            "worker_id": receipt.worker_id,
            "grant_id": receipt.grant_id,
            "exit_code": receipt.exit_code,
            "timeout_class": receipt.timeout_class,
            "stdout_hash": receipt.stdout_hash,
            "stderr_hash": receipt.stderr_hash,
            "done_json_hash": receipt.done_json_hash,
            "observer_measurement_hash": receipt.observer_measurement_hash,
            "provenance": "FULL",
            "credential_material_absent": receipt.credential_material_absent,
            "micro_refs_moved": receipt.micro_refs_moved,
            "can_move_accepted_head": false,
            "head_effect": "PRESERVE",
        }
    })
}

fn mcp_resources_list_response(id: Value) -> Value {
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "schema_id": "mcp_resource_manifest.v1",
            "read_only_resources": [
                "heads.read",
                "projection.build",
                "market.shadow.suggest",
                "pput.prompt.validate"
            ],
            "typed_commands": [
                "goal.submit",
                "capsule.approve",
                "capsule.reject",
                "dispatch.request"
            ],
            "can_write_truth": false,
            "credential_material_included": false,
        }
    })
}

fn market_shadow_suggest_response(request: &Value, id: Value) -> Value {
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let routes = match parse_routes(params) {
        Ok(routes) => routes,
        Err(message) => return invalid_params(id, message),
    };
    let signals = match parse_signals(params) {
        Ok(signals) => signals,
        Err(message) => return invalid_params(id, message),
    };
    let price_signal_hash = match required_str(params, "price_signal_hash") {
        Ok(value) => value,
        Err(message) => return invalid_params(id, message),
    };
    let pput_prior_hash = match required_str(params, "pput_prior_hash") {
        Ok(value) => value,
        Err(message) => return invalid_params(id, message),
    };

    match MarketRouter::new(MarketRouterMode::Shadow).suggest(
        &routes,
        &signals,
        &price_signal_hash,
        &pput_prior_hash,
    ) {
        Ok(suggestion) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "schema_id": suggestion.schema_id,
                "mode": "Shadow",
                "route_id": suggestion.route_id,
                "market_id": suggestion.market_id,
                "price_signal_hash": suggestion.price_signal_hash,
                "pput_prior_hash": suggestion.pput_prior_hash,
                "diversity_policy_hash": suggestion.diversity_policy_hash,
                "max_tokens": suggestion.max_tokens,
                "emits_authorization": suggestion.emits_authorization,
                "can_move_accepted_head": suggestion.can_move_accepted_head,
                "head_effect": suggestion.head_effect,
            }
        }),
        Err(error) => jsonrpc_error(
            id,
            -32000,
            format!("market shadow suggestion failed: {error}"),
        ),
    }
}

fn market_snapshot_write_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(project_root) = &runtime.project_root else {
        return jsonrpc_error(
            id,
            -32000,
            "market.snapshot.write requires --project".to_string(),
        );
    };
    let project_root = match std::fs::canonicalize(project_root) {
        Ok(path) => path,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot resolve project root: {error}"));
        }
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let events = match parse_economy_events(params) {
        Ok(events) => events,
        Err(message) => return invalid_params(id, message),
    };
    let replay = match MarketReplay::from_tape_events(&events) {
        Ok(replay) => replay,
        Err(error) => return jsonrpc_error(id, -32000, format!("market replay failed: {error}")),
    };

    let state_dir = project_root.join(".turingos");
    if let Err(error) = std::fs::create_dir_all(&state_dir) {
        return jsonrpc_error(
            id,
            -32000,
            format!("cannot create {}: {error}", state_dir.display()),
        );
    }
    let snapshot_path = state_dir.join("market_projection.json");
    let mut markets = serde_json::Map::new();
    for (market_id, market) in &replay.markets {
        markets.insert(
            market_id.clone(),
            json!({
                "market_id": market.market_id,
                "pool_y": market.pool_y,
                "pool_n": market.pool_n,
                "status": market.status,
                "settlement_result": market.settlement_result,
            }),
        );
    }
    let mut snapshot = json!({
        "schema_id": "market_projection_snapshot.v1",
        "source": replay.source,
        "market_count": replay.markets.len(),
        "markets": markets,
        "price_not_truth": true,
        "truth_source": "micro_tape",
        "emits_authorization": false,
        "can_move_accepted_head": false,
        "head_effect": "PRESERVE",
    });
    let preimage = match jcs::canonicalize(&snapshot) {
        Ok(bytes) => bytes,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("market projection canonicalization failed: {error}"),
            );
        }
    };
    let market_projection_hash = format!("sha256:{}", jcs::sha256_hex(&preimage));
    snapshot
        .as_object_mut()
        .expect("snapshot is object")
        .insert(
            "market_projection_hash".to_string(),
            Value::String(market_projection_hash.clone()),
        );
    let text = match serde_json::to_string(&snapshot) {
        Ok(text) => text,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("market snapshot serialization failed: {error}"),
            );
        }
    };
    if let Err(error) = std::fs::write(&snapshot_path, text) {
        return jsonrpc_error(
            id,
            -32000,
            format!("cannot write {}: {error}", snapshot_path.display()),
        );
    }

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "schema_id": "market_projection_snapshot.v1",
            "source": snapshot["source"],
            "market_count": snapshot["market_count"],
            "price_not_truth": snapshot["price_not_truth"],
            "emits_authorization": snapshot["emits_authorization"],
            "can_move_accepted_head": snapshot["can_move_accepted_head"],
            "head_effect": snapshot["head_effect"],
            "market_projection_hash": market_projection_hash,
            "snapshot_path": snapshot_path.to_string_lossy(),
        }
    })
}

fn pput_prompt_validate_response(request: &Value, id: Value) -> Value {
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let prompt = match params.get("prompt").and_then(Value::as_str) {
        Some(prompt) => prompt,
        None => return invalid_params(id, "prompt string is required"),
    };
    match WorkerPromptShield::validate(prompt) {
        Ok(()) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "hidden_evaluator": true,
                "worker_prompt_visible": true,
                "contains_pput_formula": false,
            }
        }),
        Err(error) => jsonrpc_error(id, -32000, format!("worker prompt leakage: {error}")),
    }
}

fn pput_snapshot_write_response(runtime: &DaemonRuntime, request: &Value, id: Value) -> Value {
    let Some(project_root) = &runtime.project_root else {
        return jsonrpc_error(
            id,
            -32000,
            "pput.snapshot.write requires --project".to_string(),
        );
    };
    let project_root = match std::fs::canonicalize(project_root) {
        Ok(path) => path,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot resolve project root: {error}"));
        }
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let cost_events = match parse_cost_events(params) {
        Ok(events) => events,
        Err(message) => return invalid_params(id, message),
    };
    let projection = match PputProjection::from_tape_events(&cost_events) {
        Ok(projection) => projection,
        Err(error) => return jsonrpc_error(id, -32000, format!("PPUT replay failed: {error}")),
    };

    let state_dir = project_root.join(".turingos");
    if let Err(error) = std::fs::create_dir_all(&state_dir) {
        return jsonrpc_error(
            id,
            -32000,
            format!("cannot create {}: {error}", state_dir.display()),
        );
    }
    let snapshot_path = state_dir.join("pput_projection.json");
    let mut snapshot = json!({
        "schema_id": "pput_projection_snapshot.v1",
        "source": projection.source,
        "cost_event_count": cost_events.len(),
        "total_tokens": projection.total_tokens,
        "total_wall_time_ms": projection.total_wall_time_ms,
        "hidden_evaluator": true,
        "hidden_from_worker_prompt": true,
        "raw_formula_exposed": false,
        "heldout_ids_exposed": false,
        "can_move_accepted_head": false,
        "head_effect": "PRESERVE",
    });
    let preimage = match jcs::canonicalize(&snapshot) {
        Ok(bytes) => bytes,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("PPUT projection canonicalization failed: {error}"),
            );
        }
    };
    let pput_projection_hash = format!("sha256:{}", jcs::sha256_hex(&preimage));
    snapshot
        .as_object_mut()
        .expect("snapshot is object")
        .insert(
            "pput_projection_hash".to_string(),
            Value::String(pput_projection_hash.clone()),
        );
    let text = match serde_json::to_string(&snapshot) {
        Ok(text) => text,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("PPUT snapshot serialization failed: {error}"),
            );
        }
    };
    if let Err(error) = std::fs::write(&snapshot_path, text) {
        return jsonrpc_error(
            id,
            -32000,
            format!("cannot write {}: {error}", snapshot_path.display()),
        );
    }

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "schema_id": "pput_projection_snapshot.v1",
            "source": snapshot["source"],
            "cost_event_count": snapshot["cost_event_count"],
            "total_tokens": snapshot["total_tokens"],
            "total_wall_time_ms": snapshot["total_wall_time_ms"],
            "hidden_evaluator": snapshot["hidden_evaluator"],
            "hidden_from_worker_prompt": snapshot["hidden_from_worker_prompt"],
            "raw_formula_exposed": snapshot["raw_formula_exposed"],
            "heldout_ids_exposed": snapshot["heldout_ids_exposed"],
            "can_move_accepted_head": snapshot["can_move_accepted_head"],
            "head_effect": snapshot["head_effect"],
            "pput_projection_hash": pput_projection_hash,
            "snapshot_path": snapshot_path.to_string_lossy(),
        }
    })
}

fn projection_build_response(request: &Value, id: Value) -> Value {
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let Some(events) = params.get("events") else {
        return invalid_params(id, "events array is required");
    };
    let events: Vec<ProjectionEvent> = match serde_json::from_value(events.clone()) {
        Ok(events) => events,
        Err(error) => return invalid_params(id, format!("invalid projection events: {error}")),
    };

    match ProjectionBuilder::from_source(ProjectionSource::MicroTape(events)).build() {
        Ok(projection) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "schema_id": projection.schema_id,
                "source": projection.source,
                "event_count": projection.event_count,
                "market_event_count": projection.market_event_count,
                "pput_event_count": projection.pput_event_count,
                "can_write_truth": projection.can_write_truth,
                "projection_hash": projection.projection_hash,
            }
        }),
        Err(error) => jsonrpc_error(id, -32000, format!("projection build failed: {error}")),
    }
}

fn projection_snapshot_write_response(
    runtime: &DaemonRuntime,
    request: &Value,
    id: Value,
) -> Value {
    let Some(project_root) = &runtime.project_root else {
        return jsonrpc_error(
            id,
            -32000,
            "projection.snapshot.write requires --project".to_string(),
        );
    };
    let project_root = match std::fs::canonicalize(project_root) {
        Ok(path) => path,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot resolve project root: {error}"));
        }
    };
    let params = match request.get("params") {
        Some(params) => params,
        None => return invalid_params(id, "params object is required"),
    };
    let Some(events) = params.get("events") else {
        return invalid_params(id, "events array is required");
    };
    let events: Vec<ProjectionEvent> = match serde_json::from_value(events.clone()) {
        Ok(events) => events,
        Err(error) => return invalid_params(id, format!("invalid projection events: {error}")),
    };
    let projection =
        match ProjectionBuilder::from_source(ProjectionSource::MicroTape(events)).build() {
            Ok(projection) => projection,
            Err(error) => {
                return jsonrpc_error(id, -32000, format!("projection build failed: {error}"));
            }
        };
    let state_dir = project_root.join(".turingos");
    if let Err(error) = std::fs::create_dir_all(&state_dir) {
        return jsonrpc_error(
            id,
            -32000,
            format!("cannot create {}: {error}", state_dir.display()),
        );
    }
    let snapshot_path = state_dir.join("projection.json");
    let snapshot = json!({
        "schema_id": "projection_snapshot.v1",
        "source": projection.source,
        "event_count": projection.event_count,
        "market_event_count": projection.market_event_count,
        "pput_event_count": projection.pput_event_count,
        "can_write_truth": projection.can_write_truth,
        "projection_hash": projection.projection_hash,
    });
    let text = match serde_json::to_string(&snapshot) {
        Ok(text) => text,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("projection snapshot serialization failed: {error}"),
            );
        }
    };
    if let Err(error) = std::fs::write(&snapshot_path, text) {
        return jsonrpc_error(
            id,
            -32000,
            format!("cannot write {}: {error}", snapshot_path.display()),
        );
    }

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "schema_id": "projection_snapshot.v1",
            "source": snapshot["source"],
            "event_count": snapshot["event_count"],
            "market_event_count": snapshot["market_event_count"],
            "pput_event_count": snapshot["pput_event_count"],
            "can_write_truth": snapshot["can_write_truth"],
            "projection_hash": snapshot["projection_hash"],
            "snapshot_path": snapshot_path.to_string_lossy(),
        }
    })
}

fn parse_predicate_checks(params: &Value) -> Result<Vec<PredicateCheck>, String> {
    let checks = params
        .get("checks")
        .and_then(Value::as_array)
        .ok_or_else(|| "checks array is required".to_string())?;
    checks
        .iter()
        .map(|check| {
            let check_id = required_str(check, "check_id")?;
            let passed = required_bool(check, "passed")?;
            if passed {
                Ok(PredicateCheck::pass(check_id))
            } else {
                Ok(PredicateCheck::fail(
                    check_id,
                    optional_str(check, "reject_class")?
                        .unwrap_or_else(|| "SEMANTIC_FAILURE".to_string()),
                ))
            }
        })
        .collect()
}

fn enforce_candidate_predicate_pack(
    mut checks: Vec<PredicateCheck>,
    candidate_payload: &Value,
) -> Vec<PredicateCheck> {
    for required in [
        "capsule_contract",
        "macro_anchor",
        "worker_receipt",
        "scope.allowed",
        "budget.within_limit",
        "provenance.checked",
        "replay.ready",
    ] {
        if !checks.iter().any(|check| check.check_id == required) {
            checks.push(PredicateCheck::fail(
                required,
                "PREDICATE_PACK_MISSING_REQUIRED_CHECK",
            ));
        }
    }
    let macro_anchor_ok = candidate_payload
        .get("macro_anchor_id")
        .and_then(Value::as_str)
        .is_some_and(|id| id.starts_with("macro:"));
    if !macro_anchor_ok {
        checks.push(PredicateCheck::fail(
            "macro_anchor",
            "MACRO_ANCHOR_ID_MUST_USE_MACRO_PREFIX",
        ));
    }
    let worker_receipt_ok = candidate_payload
        .get("worker_receipt_id")
        .and_then(Value::as_str)
        .is_some_and(|id| id.starts_with("rcp_"));
    if !worker_receipt_ok {
        checks.push(PredicateCheck::fail(
            "worker_receipt",
            "WORKER_RECEIPT_ID_REQUIRED",
        ));
    }
    checks
}

fn parse_failure_payload(value: &Value) -> Result<FailureNodePayload, String> {
    let candidate_digest = required_digest(value, "candidate_digest")?;
    let observation_digest = required_digest(value, "observation_digest")?;
    let detail = optional_str(value, "detail")?;
    Ok(FailureNodePayload::new(
        FailureClass::SemanticFailure,
        candidate_digest,
        observation_digest,
        detail,
    ))
}

fn parse_goal_state(value: &Value) -> Result<GoalState, String> {
    let goal: GoalState = serde_json::from_value(value.clone())
        .map_err(|error| format!("invalid GoalState JSON: {error}"))?;
    goal.validate()
        .map_err(|error| format!("invalid GoalState: {error}"))?;
    Ok(goal)
}

fn parse_approval_payload_for_action(
    value: &Value,
    expected_action: &str,
    method_name: &str,
) -> Result<ApprovalPayload, String> {
    let signature_route = parse_approval_signature_route(&required_str(value, "signature_route")?)?;
    if signature_route != ApprovalSignatureRoute::OsKeyring {
        return Err(format!("{method_name} requires signature_route OsKeyring"));
    }
    let action = required_str(value, "action")?;
    if action != expected_action {
        return Err(format!("{method_name} requires action {expected_action}"));
    }
    Ok(ApprovalPayload {
        schema_id: required_str(value, "schema_id")?,
        approval_id: required_str(value, "approval_id")?,
        authority_epoch: required_u64(value, "authority_epoch")?,
        action,
        subject_id: required_str(value, "subject_id")?,
        evidence_digests: required_digest_array(value, "evidence_digests")?,
        risk_class: required_str(value, "risk_class")?,
        signature_route,
    })
}

fn parse_display_copy(value: &Value) -> Result<DisplayCopy, String> {
    Ok(DisplayCopy {
        title_zh: required_str(value, "title_zh")?,
        body_en: required_str(value, "body_en")?,
    })
}

fn parse_grant(value: &Value) -> Result<CapabilityGrant, String> {
    let budget = value
        .get("budget")
        .ok_or_else(|| "grant.budget object is required".to_string())?;
    let scope = value
        .get("scope")
        .ok_or_else(|| "grant.scope object is required".to_string())?;
    let risk = value
        .get("risk")
        .ok_or_else(|| "grant.risk object is required".to_string())?;

    Ok(CapabilityGrant {
        grant_id: required_str(value, "grant_id")?,
        capsule_id: required_str(value, "capsule_id")?,
        agent_id: required_str(value, "agent_id")?,
        market_id: optional_str(value, "market_id")?,
        budget: Budget {
            max_tokens: required_u64(budget, "max_tokens")?,
            max_wall_time_ms: required_u64(budget, "max_wall_time_ms")?,
            max_tool_calls: required_u64(budget, "max_tool_calls")?,
            max_mutated_files: required_u64(budget, "max_mutated_files")?,
        },
        scope: CapabilityScope {
            allowed_paths: required_string_array(scope, "allowed_paths")?,
            forbidden_paths: required_string_array(scope, "forbidden_paths")?,
            allowed_tools: required_string_array(scope, "allowed_tools")?,
            network: parse_network(&required_str(scope, "network")?)?,
        },
        risk: Risk {
            risk_class: parse_risk_class(&required_str(risk, "risk_class")?)?,
            human_before_dispatch: required_bool(risk, "human_before_dispatch")?,
            human_before_accept: required_bool(risk, "human_before_accept")?,
            human_before_merge: required_bool(risk, "human_before_merge")?,
        },
        authorization_event: optional_str(value, "authorization_event")?,
        signature_route: parse_signature_route(&required_str(value, "signature_route")?)?,
    })
}

fn parse_tool_request(value: &Value) -> Result<ToolRequest, String> {
    Ok(ToolRequest {
        tool: required_str(value, "tool")?,
        path: optional_str(value, "path")?,
        action: parse_action_class(&required_str(value, "action")?)?,
        mutates: required_bool(value, "mutates")?,
        requested_tool_call_index: required_u64(value, "requested_tool_call_index")?,
        mutated_files_after: required_u64(value, "mutated_files_after")?,
        needs_network: required_bool(value, "needs_network")?,
    })
}

fn parse_network(raw: &str) -> Result<NetworkScope, String> {
    match raw {
        "Denied" => Ok(NetworkScope::Denied),
        "Allowlist" => Ok(NetworkScope::Allowlist),
        other => Err(format!("unknown network scope {other:?}")),
    }
}

fn parse_risk_class(raw: &str) -> Result<RiskClass, String> {
    match raw {
        "P0" => Ok(RiskClass::P0),
        "P1" => Ok(RiskClass::P1),
        "P2" => Ok(RiskClass::P2),
        "P3" => Ok(RiskClass::P3),
        other => Err(format!("unknown risk class {other:?}")),
    }
}

fn parse_signature_route(raw: &str) -> Result<SignatureRoute, String> {
    match raw {
        "None" => Ok(SignatureRoute::None),
        "OsKeyring" => Ok(SignatureRoute::OsKeyring),
        "HardwareFuture" => Ok(SignatureRoute::HardwareFuture),
        other => Err(format!("unknown signature route {other:?}")),
    }
}

fn parse_approval_signature_route(raw: &str) -> Result<ApprovalSignatureRoute, String> {
    match raw {
        "None" => Ok(ApprovalSignatureRoute::None),
        "OsKeyring" => Ok(ApprovalSignatureRoute::OsKeyring),
        "HardwareFuture" => Ok(ApprovalSignatureRoute::HardwareFuture),
        other => Err(format!("unknown approval signature route {other:?}")),
    }
}

fn approval_signature_route_str(route: ApprovalSignatureRoute) -> &'static str {
    match route {
        ApprovalSignatureRoute::None => "None",
        ApprovalSignatureRoute::OsKeyring => "OsKeyring",
        ApprovalSignatureRoute::HardwareFuture => "HardwareFuture",
    }
}

fn parse_action_class(raw: &str) -> Result<ActionClass, String> {
    match raw {
        "FileRead" => Ok(ActionClass::FileRead),
        "FileWrite" => Ok(ActionClass::FileWrite),
        "Command" => Ok(ActionClass::Command),
        "IrreversibleMacro" => Ok(ActionClass::IrreversibleMacro),
        other => Err(format!("unknown action class {other:?}")),
    }
}

fn parse_routes(params: &Value) -> Result<Vec<CandidateRoute>, String> {
    let routes = params
        .get("routes")
        .and_then(Value::as_array)
        .ok_or_else(|| "routes array is required".to_string())?;
    routes
        .iter()
        .map(|route| {
            Ok(CandidateRoute {
                route_id: required_str(route, "route_id")?,
                market_id: required_str(route, "market_id")?,
                expected_failure_domain: required_str(route, "expected_failure_domain")?,
                requested_tokens: required_u64(route, "requested_tokens")?,
            })
        })
        .collect()
}

fn parse_economy_events(params: &Value) -> Result<Vec<EconomyEvent>, String> {
    let events = params
        .get("events")
        .and_then(Value::as_array)
        .ok_or_else(|| "events array is required".to_string())?;
    events.iter().map(parse_economy_event).collect()
}

fn parse_economy_event(value: &Value) -> Result<EconomyEvent, String> {
    let Some(event_type) = value.get("event_type").and_then(Value::as_str) else {
        return serde_json::from_value(value.clone())
            .map_err(|error| format!("invalid economy event: {error}"));
    };
    match event_type {
        "MarketCreated" => serde_json::from_value::<MarketCreated>(value.clone())
            .map(EconomyEvent::MarketCreated)
            .map_err(|error| format!("invalid MarketCreated: {error}")),
        "PositionMinted" => serde_json::from_value::<PositionMinted>(value.clone())
            .map(EconomyEvent::PositionMinted)
            .map_err(|error| format!("invalid PositionMinted: {error}")),
        "AMMSwapExecuted" => serde_json::from_value::<AmmSwapExecuted>(value.clone())
            .map(EconomyEvent::AmmSwapExecuted)
            .map_err(|error| format!("invalid AMMSwapExecuted: {error}")),
        "MarketSettled" => serde_json::from_value::<MarketSettled>(value.clone())
            .map(EconomyEvent::MarketSettled)
            .map_err(|error| format!("invalid MarketSettled: {error}")),
        "RewardDistributed" => serde_json::from_value::<RewardDistributed>(value.clone())
            .map(EconomyEvent::RewardDistributed)
            .map_err(|error| format!("invalid RewardDistributed: {error}")),
        other => Err(format!("unknown economy event_type {other:?}")),
    }
}

fn parse_cost_events(params: &Value) -> Result<Vec<CostEvent>, String> {
    let events = params
        .get("cost_events")
        .and_then(Value::as_array)
        .ok_or_else(|| "cost_events array is required".to_string())?;
    events.iter().map(parse_cost_event).collect()
}

fn parse_cost_event(value: &Value) -> Result<CostEvent, String> {
    let schema_id = required_str(value, "schema_id")?;
    if schema_id != "cost_event.v1" {
        return Err(format!("unsupported cost event schema_id {schema_id:?}"));
    }
    let event_type = required_str(value, "event_type")?;
    if event_type != "CostEvent" {
        return Err(format!("unsupported cost event_type {event_type:?}"));
    }
    let head_effect = required_str(value, "head_effect")?;
    if head_effect != "PRESERVE" {
        return Err(format!(
            "CostEvent head_effect must be PRESERVE, got {head_effect:?}"
        ));
    }
    let prompt_tokens = required_u64(value, "prompt_tokens")?;
    let completion_tokens = required_u64(value, "completion_tokens")?;
    let tool_tokens = required_u64(value, "tool_tokens")?;
    let tool_stdout_tokens = required_u64(value, "tool_stdout_tokens")?;
    let total_tokens = required_u64(value, "total_tokens")?;
    let computed_total = prompt_tokens
        .checked_add(completion_tokens)
        .and_then(|count| count.checked_add(tool_tokens))
        .and_then(|count| count.checked_add(tool_stdout_tokens))
        .ok_or_else(|| "CostEvent token total overflow".to_string())?;
    if total_tokens != computed_total {
        return Err(format!(
            "CostEvent total_tokens {total_tokens} does not match counted total {computed_total}"
        ));
    }
    let counted_in_total = required_bool(value, "counted_in_total")?;
    if !counted_in_total {
        return Err("CostEvent counted_in_total must be true".to_string());
    }

    Ok(CostEvent {
        schema_id,
        event_type,
        head_effect,
        run_id: required_str(value, "run_id")?,
        problem_id: required_str(value, "problem_id")?,
        split: parse_pput_split(&required_str(value, "split")?)?,
        agent_id: required_str(value, "agent_id")?,
        branch_id: required_str(value, "branch_id")?,
        capsule_id: required_str(value, "capsule_id")?,
        prompt_tokens,
        completion_tokens,
        tool_tokens,
        tool_stdout_tokens,
        total_tokens,
        wall_time_ms: required_u64(value, "wall_time_ms")?,
        tool_stdout_hash: required_digest(value, "tool_stdout_hash")?,
        counted_in_total,
    })
}

fn parse_pput_split(raw: &str) -> Result<Split, String> {
    match raw {
        "adaptation" | "Adaptation" => Ok(Split::Adaptation),
        "meta_validation" | "MetaValidation" => Ok(Split::MetaValidation),
        "heldout" | "Heldout" => Ok(Split::Heldout),
        "dogfood" | "Dogfood" => Ok(Split::Dogfood),
        other => Err(format!("unknown PPUT split {other:?}")),
    }
}

fn parse_signals(params: &Value) -> Result<Vec<PriceSignal>, String> {
    let signals = params
        .get("signals")
        .and_then(Value::as_array)
        .ok_or_else(|| "signals array is required".to_string())?;
    signals
        .iter()
        .map(|signal| {
            Ok(PriceSignal {
                market_id: required_str(signal, "market_id")?,
                yes_price: required_str(signal, "yes_price")?,
                no_price: required_str(signal, "no_price")?,
                truth_status: required_str(signal, "truth_status")?,
            })
        })
        .collect()
}

fn read_heads_response(runtime: &DaemonRuntime, id: Value) -> Value {
    let Some(repo) = &runtime.micro_git else {
        return json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "source": "micro_tape",
                "can_write_truth": false,
                "tape_tip": Value::Null,
                "authorization_head": Value::Null,
                "accepted_head": Value::Null,
            }
        });
    };

    let tape = match Append::open(repo) {
        Ok(tape) => tape,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot open micro tape: {error}"));
        }
    };

    match tape.head_set_guarded() {
        Ok(Some(heads)) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "source": "micro_tape",
                "can_write_truth": false,
                "tape_tip": heads.tape_tip,
                "authorization_head": heads.authorization_head,
                "accepted_head": heads.accepted_head,
            }
        }),
        Ok(None) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "source": "micro_tape",
                "can_write_truth": false,
                "tape_tip": Value::Null,
                "authorization_head": Value::Null,
                "accepted_head": Value::Null,
            }
        }),
        Err(error) => jsonrpc_error(id, -32000, format!("cannot read coherent heads: {error}")),
    }
}

fn project_status_response(runtime: &DaemonRuntime, id: Value) -> Value {
    let Some(project_root) = &runtime.project_root else {
        return jsonrpc_error(id, -32000, "project.status requires --project".to_string());
    };
    let project_root = match std::fs::canonicalize(project_root) {
        Ok(path) => path,
        Err(error) => {
            return jsonrpc_error(id, -32000, format!("cannot resolve project root: {error}"));
        }
    };
    let metadata_path = project_root.join(".turingos").join("project.json");
    let text = match std::fs::read_to_string(&metadata_path) {
        Ok(text) => text,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("cannot read {}: {error}", metadata_path.display()),
            );
        }
    };
    let metadata: Value = match serde_json::from_str(&text) {
        Ok(metadata) => metadata,
        Err(error) => {
            return jsonrpc_error(
                id,
                -32000,
                format!("invalid project metadata JSON: {error}"),
            );
        }
    };
    let schema_id = match required_str(&metadata, "schema_id") {
        Ok(value) => value,
        Err(message) => return jsonrpc_error(id, -32000, message),
    };
    let declared_root = match required_str(&metadata, "project_root") {
        Ok(value) => value,
        Err(message) => return jsonrpc_error(id, -32000, message),
    };
    let truth_source = match required_str(&metadata, "truth_source") {
        Ok(value) => value,
        Err(message) => return jsonrpc_error(id, -32000, message),
    };
    let can_write_micro_truth = match required_bool(&metadata, "can_write_micro_truth") {
        Ok(value) => value,
        Err(message) => return jsonrpc_error(id, -32000, message),
    };
    let credential_material_included =
        match required_bool(&metadata, "credential_material_included") {
            Ok(value) => value,
            Err(message) => return jsonrpc_error(id, -32000, message),
        };
    let canonical_root = project_root.to_string_lossy().to_string();
    if schema_id != "operator_project.v1" {
        return jsonrpc_error(id, -32000, format!("unsupported schema_id {schema_id:?}"));
    }
    if declared_root != canonical_root {
        return jsonrpc_error(
            id,
            -32000,
            "project metadata root does not match --project".to_string(),
        );
    }
    if truth_source != "micro_tape" || can_write_micro_truth || credential_material_included {
        return jsonrpc_error(
            id,
            -32000,
            "project metadata violates private-local authority boundary".to_string(),
        );
    }

    json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "role": runtime.contract.role,
            "schema_id": schema_id,
            "source": "operator_project_metadata",
            "project_root": canonical_root,
            "metadata_path": metadata_path.to_string_lossy(),
            "truth_source": truth_source,
            "can_write_micro_truth": can_write_micro_truth,
            "credential_material_included": credential_material_included,
            "can_move_accepted_head": runtime.contract.can_move_accepted_head,
        }
    })
}

fn required_digest(value: &Value, key: &str) -> Result<String, String> {
    let digest = required_str(value, key)?;
    let Some(hex) = digest.strip_prefix("sha256:") else {
        return Err(format!("{key} must be sha256:<64 hex>"));
    };
    if hex.len() != 64 || !hex.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(format!("{key} must be sha256:<64 hex>"));
    }
    Ok(digest)
}

fn required_digest_array(value: &Value, key: &str) -> Result<Vec<String>, String> {
    let array = value
        .get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| format!("{key} array is required"))?;
    array
        .iter()
        .enumerate()
        .map(|(index, item)| {
            let digest = item
                .as_str()
                .ok_or_else(|| format!("{key}[{index}] must be a string"))?;
            let Some(hex) = digest.strip_prefix("sha256:") else {
                return Err(format!("{key}[{index}] must be sha256:<64 hex>"));
            };
            if hex.len() != 64 || !hex.bytes().all(|byte| byte.is_ascii_hexdigit()) {
                return Err(format!("{key}[{index}] must be sha256:<64 hex>"));
            }
            Ok(digest.to_string())
        })
        .collect()
}

fn predicate_product_str(product: PredicateProduct) -> &'static str {
    match product {
        PredicateProduct::Pass => "PASS",
        PredicateProduct::Fail => "FAIL",
        PredicateProduct::NotRun => "NOT_RUN",
    }
}

fn required_bool(value: &Value, key: &str) -> Result<bool, String> {
    value
        .get(key)
        .and_then(Value::as_bool)
        .ok_or_else(|| format!("{key} boolean is required"))
}

fn optional_str(value: &Value, key: &str) -> Result<Option<String>, String> {
    match value.get(key) {
        Some(Value::Null) | None => Ok(None),
        Some(Value::String(raw)) => Ok(Some(raw.clone())),
        Some(_) => Err(format!("{key} string or null is required")),
    }
}

fn required_string_array(value: &Value, key: &str) -> Result<Vec<String>, String> {
    let array = value
        .get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| format!("{key} array is required"))?;
    array
        .iter()
        .map(|item| {
            item.as_str()
                .map(ToString::to_string)
                .ok_or_else(|| format!("{key} items must be strings"))
        })
        .collect()
}

fn required_str(value: &Value, key: &str) -> Result<String, String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(ToString::to_string)
        .ok_or_else(|| format!("{key} string is required"))
}

fn required_u64(value: &Value, key: &str) -> Result<u64, String> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("{key} unsigned integer is required"))
}

fn invalid_params(id: Value, message: impl Into<String>) -> Value {
    jsonrpc_error(id, -32602, message.into())
}

fn jsonrpc_error(id: Value, code: i64, message: String) -> Value {
    json!({
        "jsonrpc": "2.0",
        "id": id,
        "error": {
            "code": code,
            "message": message,
        }
    })
}
