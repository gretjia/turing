//! Process topology contracts for private-local TuringOS daemons.

use std::io::{BufRead, BufReader, Write};
#[cfg(unix)]
use std::os::unix::net::UnixListener;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use serde_json::{Value, json};
use turing_git_tape::append::Append;

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
