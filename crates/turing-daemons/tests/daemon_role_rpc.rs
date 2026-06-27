use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use serde_json::{Value, json};

#[test]
fn marketd_serves_shadow_suggestions_without_authority() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("marketd.sock");
    let mut child = spawn_daemon("turing-marketd", &socket);
    wait_for_socket(&socket, &mut child);

    let response = rpc(
        &socket,
        "market.shadow.suggest",
        json!({
            "routes": [
                {
                    "route_id": "route_low",
                    "market_id": "mkt_low",
                    "expected_failure_domain": "local_fake",
                    "requested_tokens": 64
                },
                {
                    "route_id": "route_high",
                    "market_id": "mkt_high",
                    "expected_failure_domain": "local_command",
                    "requested_tokens": 128
                }
            ],
            "signals": [
                {
                    "market_id": "mkt_low",
                    "yes_price": "0.40",
                    "no_price": "0.60",
                    "truth_status": "statistical_signal_only"
                },
                {
                    "market_id": "mkt_high",
                    "yes_price": "0.70",
                    "no_price": "0.30",
                    "truth_status": "statistical_signal_only"
                }
            ],
            "price_signal_hash": digest('a'),
            "pput_prior_hash": digest('b')
        }),
    );

    assert_eq!(response["result"]["schema_id"], "budget_allocated.v1");
    assert_eq!(response["result"]["mode"], "Shadow");
    assert_eq!(response["result"]["route_id"], "route_high");
    assert_eq!(response["result"]["market_id"], "mkt_high");
    assert_eq!(response["result"]["max_tokens"], 128);
    assert_eq!(response["result"]["emits_authorization"], false);
    assert_eq!(response["result"]["can_move_accepted_head"], false);
    assert_eq!(response["result"]["head_effect"], "PRESERVE");

    shutdown(socket, child);
}

#[test]
fn pputd_serves_hidden_prompt_shield() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("pputd.sock");
    let mut child = spawn_daemon("turing-pputd", &socket);
    wait_for_socket(&socket, &mut child);

    let visible = rpc(
        &socket,
        "pput.prompt.validate",
        json!({"prompt": "Implement the visible capsule and report pass or fail."}),
    );
    assert_eq!(visible["result"]["hidden_evaluator"], true);
    assert_eq!(visible["result"]["worker_prompt_visible"], true);
    assert_eq!(visible["result"]["contains_pput_formula"], false);

    let leaked = rpc(
        &socket,
        "pput.prompt.validate",
        json!({"prompt": "Optimize VPPUT against heldout golden path ids."}),
    );
    assert_eq!(leaked["error"]["code"], -32000);
    assert!(
        leaked["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("worker prompt leakage")
    );

    shutdown(socket, child);
}

#[test]
fn viewd_builds_disposable_projection_without_truth_write() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("viewd.sock");
    let mut child = spawn_daemon("turing-viewd", &socket);
    wait_for_socket(&socket, &mut child);

    let response = rpc(
        &socket,
        "projection.build",
        json!({
            "events": [
                {
                    "event_id": format!("mu:{}", "a".repeat(64)),
                    "event_type": "MarketCreated",
                    "subject_id": "mkt_demo"
                },
                {
                    "event_id": format!("mu:{}", "b".repeat(64)),
                    "event_type": "PPUTAccounted",
                    "subject_id": "run_demo"
                }
            ]
        }),
    );

    assert_eq!(response["result"]["schema_id"], "projection.v1");
    assert_eq!(response["result"]["source"], "micro_tape_only");
    assert_eq!(response["result"]["event_count"], 2);
    assert_eq!(response["result"]["market_event_count"], 1);
    assert_eq!(response["result"]["pput_event_count"], 1);
    assert_eq!(response["result"]["can_write_truth"], false);
    assert!(
        response["result"]["projection_hash"]
            .as_str()
            .expect("projection hash")
            .starts_with("sha256:")
    );

    shutdown(socket, child);
}

#[test]
fn execd_authorizes_scoped_grants_without_head_authority() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("execd.sock");
    let mut child = spawn_daemon("turing-execd", &socket);
    wait_for_socket(&socket, &mut child);

    let allowed = rpc(
        &socket,
        "grant.authorize",
        json!({
            "grant": grant_json(),
            "request": {
                "tool": "read_file",
                "path": "src/main.rs",
                "action": "FileRead",
                "mutates": false,
                "requested_tool_call_index": 1,
                "mutated_files_after": 0,
                "needs_network": false
            }
        }),
    );
    assert_eq!(allowed["result"]["authorized"], true);
    assert_eq!(allowed["result"]["can_move_accepted_head"], false);
    assert_eq!(allowed["result"]["receipt_type"], "ToolCallAuthorized");

    let denied = rpc(
        &socket,
        "grant.authorize",
        json!({
            "grant": grant_json(),
            "request": {
                "tool": "read_file",
                "path": "secrets/token.txt",
                "action": "FileRead",
                "mutates": false,
                "requested_tool_call_index": 1,
                "mutated_files_after": 0,
                "needs_network": false
            }
        }),
    );
    assert_eq!(denied["result"]["authorized"], false);
    assert_eq!(denied["result"]["can_move_accepted_head"], false);
    assert_eq!(denied["result"]["receipt_type"], "ToolCallDenied");
    assert!(
        denied["result"]["denial"]
            .as_str()
            .expect("denial")
            .contains("outside allowed scope")
    );

    shutdown(socket, child);
}

#[test]
fn execd_dispatches_fake_worker_without_head_authority() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("execd-dispatch.sock");
    let mut child = spawn_daemon("turing-execd", &socket);
    wait_for_socket(&socket, &mut child);

    let dispatched = rpc(
        &socket,
        "dispatch.request",
        json!({
            "worker_kind": "Fake",
            "worker_id": "worker_fake_rpc",
            "capsule_id": "wc_rpc",
            "grant_id": "grant_rpc"
        }),
    );

    assert_eq!(dispatched["result"]["receipt_type"], "WorkerDispatched");
    assert_eq!(dispatched["result"]["schema_id"], "execution_receipt.v1");
    assert_eq!(dispatched["result"]["capsule_id"], "wc_rpc");
    assert_eq!(dispatched["result"]["worker_id"], "worker_fake_rpc");
    assert_eq!(dispatched["result"]["grant_id"], "grant_rpc");
    assert_eq!(dispatched["result"]["exit_code"], 0);
    assert_eq!(dispatched["result"]["credential_material_absent"], true);
    assert_eq!(dispatched["result"]["micro_refs_moved"], false);
    assert_eq!(dispatched["result"]["can_move_accepted_head"], false);
    assert_eq!(dispatched["result"]["head_effect"], "PRESERVE");
    assert!(
        dispatched["result"]["receipt_id"]
            .as_str()
            .expect("receipt id")
            .starts_with("rcp_")
    );

    shutdown(socket, child);
}

#[test]
fn mcp_lists_read_only_resources_and_typed_commands_without_truth() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("mcp.sock");
    let mut child = spawn_daemon("turing-mcp", &socket);
    wait_for_socket(&socket, &mut child);

    let response = rpc(&socket, "mcp.resources.list", Value::Null);
    assert_eq!(response["result"]["can_write_truth"], false);
    assert_eq!(response["result"]["credential_material_included"], false);
    assert!(
        response["result"]["read_only_resources"]
            .as_array()
            .expect("resources")
            .iter()
            .any(|value| value == "heads.read")
    );
    assert!(
        response["result"]["typed_commands"]
            .as_array()
            .expect("commands")
            .iter()
            .any(|value| value == "capsule.approve")
    );
    assert!(
        response["result"]["typed_commands"]
            .as_array()
            .expect("commands")
            .iter()
            .all(|value| value != "move-accepted-head")
    );

    shutdown(socket, child);
}

fn spawn_daemon(name: &str, socket: &Path) -> Child {
    Command::new(bin(name))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
        ])
        .spawn()
        .expect("spawn daemon")
}

fn bin(name: &str) -> &'static str {
    match name {
        "turing-execd" => env!("CARGO_BIN_EXE_turing-execd"),
        "turing-marketd" => env!("CARGO_BIN_EXE_turing-marketd"),
        "turing-mcp" => env!("CARGO_BIN_EXE_turing-mcp"),
        "turing-pputd" => env!("CARGO_BIN_EXE_turing-pputd"),
        "turing-viewd" => env!("CARGO_BIN_EXE_turing-viewd"),
        other => panic!("unknown test binary {other}"),
    }
}

fn rpc(socket: &Path, method: &str, params: Value) -> Value {
    let mut stream = UnixStream::connect(socket).expect("connect to daemon socket");
    let request = json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    });
    writeln!(stream, "{request}").expect("write request");
    let mut line = String::new();
    BufReader::new(stream)
        .read_line(&mut line)
        .expect("read response");
    serde_json::from_str(&line).expect("JSON-RPC response")
}

fn shutdown(socket: impl AsRef<Path>, mut child: Child) {
    let response = rpc(socket.as_ref(), "daemon.shutdown", Value::Null);
    assert_eq!(response["result"]["shutdown"], true);
    let status = child.wait().expect("wait for daemon");
    assert!(status.success(), "daemon shutdown failed: {status}");
}

fn wait_for_socket(socket: &Path, child: &mut Child) {
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(5) {
        if socket.exists() {
            return;
        }
        if let Some(status) = child.try_wait().expect("poll child") {
            panic!("daemon exited before socket appeared: {status}");
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    let _ = child.kill();
    panic!("daemon socket did not appear at {}", socket.display());
}

fn digest(ch: char) -> String {
    format!("sha256:{}", ch.to_string().repeat(64))
}

fn grant_json() -> Value {
    json!({
        "grant_id": "grant_demo",
        "capsule_id": "wc_demo",
        "agent_id": "agent_demo",
        "market_id": null,
        "budget": {
            "max_tokens": 100,
            "max_wall_time_ms": 1000,
            "max_tool_calls": 2,
            "max_mutated_files": 1
        },
        "scope": {
            "allowed_paths": ["src"],
            "forbidden_paths": ["src/secrets"],
            "allowed_tools": ["read_file"],
            "network": "Denied"
        },
        "risk": {
            "risk_class": "P3",
            "human_before_dispatch": false,
            "human_before_accept": true,
            "human_before_merge": true
        },
        "authorization_event": null,
        "signature_route": "None"
    })
}
