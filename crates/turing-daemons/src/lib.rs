//! Process topology contracts for private-local TuringOS daemons.

use std::io::{BufRead, BufReader, Write};
#[cfg(unix)]
use std::os::unix::net::UnixListener;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use serde_json::{Value, json};
use turing_economy::{CandidateRoute, MarketRouter, MarketRouterMode, PriceSignal};
use turing_git_tape::append::Append;
use turing_pput::WorkerPromptShield;
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
}

pub fn run_daemon(contract: DaemonContract) -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [serve, socket_flag, socket] if serve == "--serve" && socket_flag == "--socket" => {
            let runtime = DaemonRuntime {
                contract,
                micro_git: None,
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
        Some("market.shadow.suggest") if runtime.contract.role == "turing-marketd" => {
            market_shadow_suggest_response(request, id)
        }
        Some("pput.prompt.validate") if runtime.contract.role == "turing-pputd" => {
            pput_prompt_validate_response(request, id)
        }
        Some("projection.build") if runtime.contract.role == "turing-viewd" => {
            projection_build_response(request, id)
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
