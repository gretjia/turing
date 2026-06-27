//! Process topology contracts for private-local TuringOS daemons.

use std::io::{BufRead, BufReader, Write};
#[cfg(unix)]
use std::os::unix::net::UnixListener;
use std::path::Path;
use std::process::ExitCode;

use serde_json::{Value, json};

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

pub fn run_daemon(contract: DaemonContract) -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [serve, socket_flag, socket] if serve == "--serve" && socket_flag == "--socket" => {
            match serve_unix_socket(contract, socket) {
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
fn serve_unix_socket(contract: DaemonContract, socket: &str) -> std::io::Result<()> {
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
        let response = jsonrpc_response(contract, &request);
        writeln!(stream, "{response}")?;
        if shutdown {
            break;
        }
    }
    Ok(())
}

#[cfg(not(unix))]
fn serve_unix_socket(_contract: DaemonContract, _socket: &str) -> std::io::Result<()> {
    Err(std::io::Error::other(
        "Unix sockets are required for private-local daemon tests",
    ))
}

fn jsonrpc_response(contract: DaemonContract, request: &Value) -> Value {
    let id = request.get("id").cloned().unwrap_or(Value::Null);
    match request.get("method").and_then(Value::as_str) {
        Some("daemon.check") => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": {
                "role": contract.role,
                "can_move_accepted_head": contract.can_move_accepted_head,
                "single_loop_subroutine": true,
            }
        }),
        Some("heads.read") => json!({
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
