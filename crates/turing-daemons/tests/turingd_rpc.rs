use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use serde_json::Value;

#[test]
fn turingd_serves_jsonrpc_health_and_read_only_heads() {
    let dir = tempfile::tempdir().expect("temp dir");
    let socket = dir.path().join("turingd.sock");
    let mut child = Command::new(env!("CARGO_BIN_EXE_turingd"))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
        ])
        .spawn()
        .expect("spawn turingd");

    wait_for_socket(&socket, &mut child);

    let check = rpc(&socket, "daemon.check");
    assert_eq!(check["result"]["role"], "turingd");
    assert_eq!(check["result"]["can_move_accepted_head"], true);
    assert_eq!(check["result"]["single_loop_subroutine"], true);

    let heads = rpc(&socket, "heads.read");
    assert_eq!(heads["result"]["source"], "micro_tape");
    assert_eq!(heads["result"]["can_write_truth"], false);
    assert_eq!(heads["result"]["accepted_head"], Value::Null);

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

fn rpc(socket: &Path, method: &str) -> Value {
    let mut stream = UnixStream::connect(socket).expect("connect to turingd socket");
    writeln!(stream, r#"{{"jsonrpc":"2.0","id":1,"method":"{method}"}}"#).expect("write request");
    let mut line = String::new();
    BufReader::new(stream)
        .read_line(&mut line)
        .expect("read response");
    serde_json::from_str(&line).expect("JSON-RPC response")
}

fn wait_for_socket(socket: &Path, child: &mut Child) {
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(5) {
        if socket.exists() {
            return;
        }
        if let Some(status) = child.try_wait().expect("poll child") {
            panic!("turingd exited before socket appeared: {status}");
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    let _ = child.kill();
    panic!("turingd socket did not appear at {}", socket.display());
}
