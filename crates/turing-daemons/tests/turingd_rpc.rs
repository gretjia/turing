use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use serde_json::Value;
use serde_json::json;
use turing_git_tape::append::{Append, AppendRequest};
use turing_git_tape::git;

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

#[test]
fn turingd_reads_real_micro_tape_heads_from_configured_repo() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");

    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    let authorization = tape
        .append(
            AppendRequest::new(
                "AtomAuthorized",
                "writer:auth",
                json!({"atom_id": "atom_demo"}),
            )
            .predicate_pass(),
        )
        .expect("append authorization");
    let accepted = tape
        .append(
            AppendRequest::new(
                "CandidateAccepted",
                "writer:accept",
                json!({"candidate_id": "cand_demo"}),
            )
            .predicate_pass(),
        )
        .expect("append accepted");

    let socket = dir.path().join("turingd-real-heads.sock");
    let mut child = Command::new(env!("CARGO_BIN_EXE_turingd"))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
            "--micro-git",
            repo.to_str().expect("UTF-8 repo path"),
        ])
        .spawn()
        .expect("spawn turingd");

    wait_for_socket(&socket, &mut child);

    let heads = rpc(&socket, "heads.read");
    assert_eq!(heads["result"]["source"], "micro_tape");
    assert_eq!(heads["result"]["can_write_truth"], false);
    assert_eq!(heads["result"]["tape_tip"], accepted.event_id);
    assert_eq!(
        heads["result"]["authorization_head"],
        authorization.event_id
    );
    assert_eq!(heads["result"]["accepted_head"], accepted.event_id);
    assert_ne!(heads["result"]["accepted_head"], genesis.event_id);

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
