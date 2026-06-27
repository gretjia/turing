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
fn turingd_bootstraps_genesis_only_on_empty_micro_tape() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");

    let socket = dir.path().join("turingd-bootstrap-genesis.sock");
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

    let bootstrapped = rpc_params(
        &socket,
        "project.bootstrap_genesis",
        json!({
            "writer_id": "writer:bootstrap",
            "constitution_digest": digest('9')
        }),
    );
    let event_id = bootstrapped["result"]["event_id"]
        .as_str()
        .expect("event id")
        .to_string();
    assert!(event_id.starts_with("mu:"));
    assert_eq!(
        bootstrapped["result"]["event_type"],
        "SystemConstitutionAccepted"
    );
    assert_eq!(bootstrapped["result"]["accepted_head_moved"], true);
    assert_eq!(bootstrapped["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        bootstrapped["result"]["head_set"]["accepted_head"],
        event_id
    );

    let second = rpc_params(
        &socket,
        "project.bootstrap_genesis",
        json!({
            "writer_id": "writer:bootstrap",
            "constitution_digest": digest('9')
        }),
    );
    assert_eq!(second["error"]["code"], -32000);
    assert!(
        second["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("already bootstrapped")
    );

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

#[test]
fn turingd_project_status_reads_boot_metadata_without_truth_authority() {
    let dir = tempfile::tempdir().expect("temp dir");
    let project = dir.path().join("project");
    std::fs::create_dir(&project).expect("create project dir");
    let state_dir = project.join(".turingos");
    std::fs::create_dir(&state_dir).expect("create state dir");
    let project_root = std::fs::canonicalize(&project).expect("canonical project");
    std::fs::write(
        state_dir.join("project.json"),
        json!({
            "schema_id": "operator_project.v1",
            "project_root": project_root.to_str().expect("UTF-8 project path"),
            "truth_source": "micro_tape",
            "can_write_micro_truth": false,
            "credential_material_included": false
        })
        .to_string(),
    )
    .expect("write project metadata");

    let socket = dir.path().join("turingd-project-status.sock");
    let mut child = Command::new(env!("CARGO_BIN_EXE_turingd"))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
            "--project",
            project.to_str().expect("UTF-8 project path"),
        ])
        .spawn()
        .expect("spawn turingd");

    wait_for_socket(&socket, &mut child);

    let status = rpc(&socket, "project.status");
    assert_eq!(status["result"]["schema_id"], "operator_project.v1");
    assert_eq!(status["result"]["source"], "operator_project_metadata");
    assert_eq!(
        status["result"]["project_root"],
        project_root.to_str().expect("UTF-8 canonical project path")
    );
    assert_eq!(status["result"]["truth_source"], "micro_tape");
    assert_eq!(status["result"]["can_write_micro_truth"], false);
    assert_eq!(status["result"]["credential_material_included"], false);
    assert!(status["result"].get("credential_hash").is_none());
    assert!(status["result"].get("credential_scope_hash").is_none());

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_appends_preserve_events_without_moving_accepted_head() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"c".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let socket = dir.path().join("turingd-append-preserve.sock");
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

    let appended = rpc_params(
        &socket,
        "event.append_preserve",
        json!({
            "event_type": "GoalStateProposed",
            "writer_id": "writer:goal",
            "payload": {
                "goal_id": "goal_rpc",
                "intent": "append preserve event through turingd"
            }
        }),
    );
    let event_id = appended["result"]["event_id"]
        .as_str()
        .expect("event id")
        .to_string();
    assert!(event_id.starts_with("mu:"));
    assert_eq!(appended["result"]["event_type"], "GoalStateProposed");
    assert_eq!(appended["result"]["head_effect"], "PRESERVE");
    assert_eq!(appended["result"]["accepted_head_moved"], false);
    assert_eq!(appended["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        appended["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );

    let denied = rpc_params(
        &socket,
        "event.append_preserve",
        json!({
            "event_type": "CandidateAccepted",
            "writer_id": "writer:accept",
            "payload": {
                "candidate_id": "cand_forbidden"
            }
        }),
    );
    assert_eq!(denied["error"]["code"], -32000);
    assert!(
        denied["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("not a PRESERVE event")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_routes_predicate_pass_and_fail() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"d".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_worker_receipt(&tape, "wc_rpc", "rcp_pass");
    append_worker_receipt(&tape, "wc_rpc", "rcp_fail");
    append_macro_observation(&tape, "wc_rpc", "macro:diff_rpc");
    append_official_evaluator_evidence(
        &tape,
        "ev_official_pass",
        "wc_rpc",
        "macro:diff_rpc",
        "rcp_pass",
        "PASS",
        false,
    );

    let socket = dir.path().join("turingd-verify-write.sock");
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

    let passed = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_pass",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:diff_rpc",
                "worker_receipt_id": "rcp_pass",
                "official_evaluator_evidence_id": "ev_official_pass"
            },
            "failure": {
                "candidate_digest": digest('e'),
                "observation_digest": digest('f'),
                "detail": "unused on pass"
            }
        }),
    );
    let accepted_id = passed["result"]["event_id"]
        .as_str()
        .expect("accepted event id")
        .to_string();
    assert_eq!(passed["result"]["write_event_type"], "CandidateAccepted");
    assert_eq!(passed["result"]["predicate_product"], "PASS");
    assert_eq!(passed["result"]["accepted_head_moved"], true);
    assert_eq!(passed["result"]["head_set"]["accepted_head"], accepted_id);
    assert!(
        passed["result"]["predicate_report_hash"]
            .as_str()
            .expect("predicate report hash")
            .starts_with("sha256:")
    );

    let failed = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_fail",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": format!("mu:{}", "0".repeat(64)),
                "worker_receipt_id": "rcp_fail"
            },
            "failure": {
                "candidate_digest": digest('a'),
                "observation_digest": digest('b'),
                "detail": "scope violation"
            }
        }),
    );
    assert_eq!(failed["result"]["write_event_type"], "FailureNode");
    assert_eq!(failed["result"]["predicate_product"], "FAIL");
    assert_eq!(failed["result"]["failure_class"], "SEMANTIC_FAILURE");
    assert_eq!(failed["result"]["accepted_head_moved"], false);
    assert_eq!(failed["result"]["head_set"]["accepted_head"], accepted_id);

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_rejects_missing_macro_anchor_from_derived_predicate_pack() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"2".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_worker_receipt(&tape, "wc_rpc", "rcp_missing_macro_anchor");

    let socket = dir.path().join("turingd-predicate-pack.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_missing_macro_anchor",
                "capsule_id": "wc_rpc",
                "worker_receipt_id": "rcp_missing_macro_anchor"
            },
            "failure": {
                "candidate_digest": digest('3'),
                "observation_digest": digest('4'),
                "detail": "required predicate pack check missing"
            }
        }),
    );

    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("failure event id")
        .to_string();
    assert_eq!(rejected["result"]["write_event_type"], "FailureNode");
    assert_eq!(rejected["result"]["predicate_product"], "FAIL");
    assert_eq!(rejected["result"]["accepted_head_moved"], false);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        rejected["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );
    assert!(
        rejected["result"]["failed_predicates"]
            .as_array()
            .expect("failed predicates")
            .iter()
            .any(|value| value == "macro_anchor")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_rejects_caller_supplied_predicate_checks() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    let _genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let socket = dir
        .path()
        .join("turingd-verify-write-ignores-booleans.sock");
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

    let response = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_ignore_client_bools",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:diff_rpc",
                "worker_receipt_id": "rcp_ignore_client_bools"
            },
            "checks": [
                {"check_id": "capsule_contract", "passed": true},
                {"check_id": "macro_anchor", "passed": true},
                {"check_id": "worker_receipt", "passed": true},
                {"check_id": "scope.allowed", "passed": true},
                {"check_id": "budget.within_limit", "passed": true},
                {"check_id": "provenance.checked", "passed": true},
                {"check_id": "replay.ready", "passed": true}
            ],
            "failure": {
                "candidate_digest": digest('d'),
                "observation_digest": digest('e'),
                "detail": "client tried to supply predicate checks"
            }
        }),
    );

    assert_eq!(response["error"]["code"], -32602);
    assert!(
        response["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("caller-supplied checks are forbidden")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_rejects_well_formed_refs_absent_from_tape() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"6".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");

    let socket = dir.path().join("turingd-absent-refs.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_absent_refs",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:absent",
                "worker_receipt_id": "rcp_absent"
            },
            "failure": {
                "candidate_digest": digest('6'),
                "observation_digest": digest('7'),
                "detail": "well-formed refs are absent from tape"
            }
        }),
    );

    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("failure event id")
        .to_string();
    assert_eq!(rejected["result"]["write_event_type"], "FailureNode");
    assert_eq!(rejected["result"]["predicate_product"], "FAIL");
    assert_eq!(rejected["result"]["accepted_head_moved"], false);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        rejected["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );
    assert!(
        rejected["result"]["failed_predicates"]
            .as_array()
            .expect("failed predicates")
            .iter()
            .any(|value| value == "macro_anchor")
    );
    assert!(
        rejected["result"]["failed_predicates"]
            .as_array()
            .expect("failed predicates")
            .iter()
            .any(|value| value == "worker_receipt")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_rejects_micro_id_as_macro_anchor() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"5".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_worker_receipt(&tape, "wc_rpc", "rcp_bad_anchor");

    let socket = dir.path().join("turingd-macro-anchor-id.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_bad_anchor",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": format!("mu:{}", "6".repeat(64)),
                "worker_receipt_id": "rcp_bad_anchor"
            },
            "failure": {
                "candidate_digest": digest('7'),
                "observation_digest": digest('8'),
                "detail": "macro anchor identity confusion"
            }
        }),
    );

    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("failure event id")
        .to_string();
    assert_eq!(rejected["result"]["write_event_type"], "FailureNode");
    assert_eq!(rejected["result"]["predicate_product"], "FAIL");
    assert_eq!(rejected["result"]["accepted_head_moved"], false);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        rejected["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );
    assert!(
        rejected["result"]["failed_predicates"]
            .as_array()
            .expect("failed predicates")
            .iter()
            .any(|value| value == "macro_anchor")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_rejects_missing_worker_receipt() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"9".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_macro_observation(&tape, "wc_rpc", "macro:diff_rpc");

    let socket = dir.path().join("turingd-worker-receipt-id.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_missing_receipt",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:diff_rpc"
            },
            "failure": {
                "candidate_digest": digest('9'),
                "observation_digest": digest('a'),
                "detail": "worker receipt missing"
            }
        }),
    );

    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("failure event id")
        .to_string();
    assert_eq!(rejected["result"]["write_event_type"], "FailureNode");
    assert_eq!(rejected["result"]["predicate_product"], "FAIL");
    assert_eq!(rejected["result"]["accepted_head_moved"], false);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        rejected["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );
    assert!(
        rejected["result"]["failed_predicates"]
            .as_array()
            .expect("failed predicates")
            .iter()
            .any(|value| value == "worker_receipt")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_requires_official_evaluator_evidence_before_accept() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"8".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_worker_receipt(&tape, "wc_rpc", "rcp_no_official_eval");
    append_macro_observation(&tape, "wc_rpc", "macro:diff_rpc");

    let socket = dir.path().join("turingd-missing-official-eval.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_missing_official_eval",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:diff_rpc",
                "worker_receipt_id": "rcp_no_official_eval"
            },
            "failure": {
                "candidate_digest": digest('8'),
                "observation_digest": digest('9'),
                "detail": "official evaluator evidence is absent from tape"
            }
        }),
    );

    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("failure event id")
        .to_string();
    assert_eq!(rejected["result"]["write_event_type"], "FailureNode");
    assert_eq!(rejected["result"]["predicate_product"], "FAIL");
    assert_eq!(rejected["result"]["accepted_head_moved"], false);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        rejected["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );
    assert!(
        rejected["result"]["failed_predicates"]
            .as_array()
            .expect("failed predicates")
            .iter()
            .any(|value| value == "official_evaluator_evidence")
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_accepts_derived_predicate_pack_without_checks() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    let _genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"b".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_worker_receipt(&tape, "wc_rpc", "rcp_pack");
    append_macro_observation(&tape, "wc_rpc", "macro:diff_rpc");
    append_official_evaluator_evidence(
        &tape,
        "ev_official_pack",
        "wc_rpc",
        "macro:diff_rpc",
        "rcp_pack",
        "PASS",
        false,
    );

    let socket = dir.path().join("turingd-expanded-pack.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_derived_pack",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:diff_rpc",
                "worker_receipt_id": "rcp_pack",
                "official_evaluator_evidence_id": "ev_official_pack"
            }
        }),
    );

    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("accepted event id")
        .to_string();
    assert_eq!(rejected["result"]["write_event_type"], "CandidateAccepted");
    assert_eq!(rejected["result"]["predicate_product"], "PASS");
    assert_eq!(rejected["result"]["accepted_head_moved"], true);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(rejected["result"]["head_set"]["accepted_head"], event_id);

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_verify_write_rejects_extra_truthy_candidate_fields() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"b".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    append_work_capsule(&tape, "wc_rpc");
    append_worker_receipt(&tape, "wc_rpc", "rcp_pack");
    append_macro_observation(&tape, "wc_rpc", "macro:diff_rpc");

    let socket = dir.path().join("turingd-extra-fields.sock");
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

    let rejected = rpc_params(
        &socket,
        "candidate.verify_write",
        json!({
            "writer_id": "writer:predicate",
            "candidate_payload": {
                "candidate_id": "cand_truthy_payload",
                "capsule_id": "wc_rpc",
                "macro_anchor_id": "macro:diff_rpc",
                "worker_receipt_id": "rcp_pack",
                "ci_green": true,
                "price_truth": true,
                "accepted": true
            }
        }),
    );

    assert_eq!(rejected["error"]["code"], -32000);
    assert!(
        rejected["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("unexpected candidate_payload field")
    );
    let heads = Append::open(&repo)
        .expect("reopen tape")
        .head_set_guarded()
        .expect("head set")
        .expect("heads exist");
    assert_eq!(heads.accepted_head, genesis.event_id);

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_rejects_in_memory_test_atom_authorization_without_moving_authorization_head() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"e".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let socket = dir.path().join("turingd-approval.sock");
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

    let rejected = rpc_params(
        &socket,
        "approval.authorize_atom",
        json!({
            "key_id": "operator-local-key",
            "payload": {
                "schema_id": "approval_payload.v2",
                "approval_id": "ap_atom_rpc",
                "authority_epoch": 0,
                "action": "atom_authorize",
                "subject_id": "atom_rpc",
                "evidence_digests": [digest('c')],
                "risk_class": "P2",
                "signature_route": "InMemoryTest"
            },
            "display_copy": {
                "title_zh": "批准 Atom",
                "body_en": "Authorize atom dispatch."
            }
        }),
    );

    assert_eq!(rejected["error"]["code"], -32602);
    assert!(
        rejected["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("requires signature_route OsKeyring")
    );
    let heads = Append::open(&repo)
        .expect("reopen tape")
        .head_set_guarded()
        .expect("head set")
        .expect("heads exist");
    assert_eq!(heads.authorization_head, None);
    assert_eq!(heads.accepted_head, genesis.event_id);

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_goal_submit_validates_goal_state_before_append() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"f".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let socket = dir.path().join("turingd-goal-submit.sock");
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

    let rejected = rpc_params(
        &socket,
        "goal.submit",
        json!({
            "writer_id": "writer:goal",
            "goal": {
                "schema_id": "goal_state.v1",
                "goal_id": "goal_bad_rpc",
                "objective": "ship from prose only",
                "must_haves": [
                    {
                        "text": "make it good",
                        "machine_checks": []
                    }
                ],
                "anti_goals": []
            }
        }),
    );
    assert_eq!(rejected["error"]["code"], -32602);
    assert!(
        rejected["error"]["message"]
            .as_str()
            .expect("validation message")
            .contains("lacks a predicate or PCP check")
    );

    let submitted = rpc_params(
        &socket,
        "goal.submit",
        json!({
            "writer_id": "writer:goal",
            "goal": {
                "schema_id": "goal_state.v1",
                "goal_id": "goal_rpc",
                "objective": "bootstrap a replayable runtime",
                "must_haves": [
                    {
                        "text": "replay passes",
                        "machine_checks": [
                            {
                                "kind": "PREDICATE",
                                "predicate_id": "predicate.replay.verify"
                            }
                        ]
                    }
                ],
                "anti_goals": ["do not expose PPUT to Worker prompts"]
            }
        }),
    );
    let event_id = submitted["result"]["event_id"]
        .as_str()
        .expect("goal event id")
        .to_string();
    assert_eq!(submitted["result"]["event_type"], "GoalStateProposed");
    assert_eq!(submitted["result"]["goal_id"], "goal_rpc");
    assert_eq!(submitted["result"]["head_effect"], "PRESERVE");
    assert_eq!(submitted["result"]["accepted_head_moved"], false);
    assert!(
        submitted["result"]["goal_digest"]
            .as_str()
            .expect("goal digest")
            .starts_with("sha256:")
    );
    assert_eq!(submitted["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        submitted["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_rejects_in_memory_test_capsule_approval_without_moving_authorization_head() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"0".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let socket = dir.path().join("turingd-capsule-approve.sock");
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

    let rejected = rpc_params(
        &socket,
        "capsule.approve",
        json!({
            "key_id": "operator-local-key",
            "payload": {
                "schema_id": "approval_payload.v2",
                "approval_id": "ap_capsule_rpc",
                "authority_epoch": 0,
                "action": "capsule_approve",
                "subject_id": "wc_rpc",
                "evidence_digests": [digest('d')],
                "risk_class": "P2",
                "signature_route": "InMemoryTest"
            },
            "display_copy": {
                "title_zh": "批准 Capsule",
                "body_en": "Authorize capsule dispatch."
            }
        }),
    );

    assert_eq!(rejected["error"]["code"], -32602);
    assert!(
        rejected["error"]["message"]
            .as_str()
            .expect("error message")
            .contains("requires signature_route OsKeyring")
    );
    let heads = Append::open(&repo)
        .expect("reopen tape")
        .head_set_guarded()
        .expect("head set")
        .expect("heads exist");
    assert_eq!(heads.authorization_head, None);
    assert_eq!(heads.accepted_head, genesis.event_id);

    let shutdown = rpc(&socket, "daemon.shutdown");
    assert_eq!(shutdown["result"]["shutdown"], true);
    let status = child.wait().expect("wait for turingd");
    assert!(status.success(), "turingd shutdown failed: {status}");
}

#[test]
fn turingd_capsule_reject_appends_failure_without_moving_heads() {
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
                json!({"constitution_digest": "sha256:".to_string() + &"1".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");

    let socket = dir.path().join("turingd-capsule-reject.sock");
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

    let rejected = rpc_params(
        &socket,
        "capsule.reject",
        json!({
            "writer_id": "writer:operator",
            "capsule_id": "wc_rejected",
            "capsule_digest": digest('1'),
            "observation_digest": digest('2'),
            "detail": "operator rejected the proposed dispatch"
        }),
    );
    let event_id = rejected["result"]["event_id"]
        .as_str()
        .expect("failure event id")
        .to_string();
    assert_eq!(rejected["result"]["event_type"], "FailureNode");
    assert_eq!(rejected["result"]["capsule_id"], "wc_rejected");
    assert_eq!(rejected["result"]["failure_class"], "STEER_REJECTED");
    assert_eq!(rejected["result"]["authorization_head_moved"], false);
    assert_eq!(rejected["result"]["accepted_head_moved"], false);
    assert_eq!(rejected["result"]["head_set"]["tape_tip"], event_id);
    assert_eq!(
        rejected["result"]["head_set"]["authorization_head"],
        Value::Null
    );
    assert_eq!(
        rejected["result"]["head_set"]["accepted_head"],
        genesis.event_id
    );

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

fn rpc_params(socket: &Path, method: &str, params: Value) -> Value {
    let mut stream = UnixStream::connect(socket).expect("connect to turingd socket");
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

fn append_work_capsule(tape: &Append, capsule_id: &str) {
    tape.append(
        AppendRequest::new(
            "WorkCapsuleBuilt",
            "writer:test-capsule",
            json!({
                "capsule_id": capsule_id,
                "private_contract_hash": digest('c'),
                "acceptance_commands": ["cargo test --workspace"]
            }),
        )
        .predicate_pass(),
    )
    .expect("append work capsule");
}

fn append_worker_receipt(tape: &Append, capsule_id: &str, receipt_id: &str) {
    tape.append(
        AppendRequest::new(
            "WorkerReceiptImported",
            "writer:test-receipt",
            json!({
                "receipt_id": receipt_id,
                "capsule_id": capsule_id,
                "worker_id": "worker:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                "exit_code": 0,
                "stdout_hash": digest('1'),
                "stderr_hash": digest('2'),
                "done_json_hash": digest('3'),
                "credential_material_absent": true,
                "micro_refs_moved": false
            }),
        )
        .predicate_pass(),
    )
    .expect("append worker receipt");
}

fn append_macro_observation(tape: &Append, capsule_id: &str, macro_id: &str) {
    tape.append(
        AppendRequest::new(
            "MacroObservationImported",
            "writer:test-macro",
            json!({
                "macro_id": macro_id,
                "capsule_id": capsule_id,
                "diff_hash": digest('4'),
                "external_evidence_only": true
            }),
        )
        .predicate_pass(),
    )
    .expect("append macro observation");
}

fn append_official_evaluator_evidence(
    tape: &Append,
    evidence_id: &str,
    capsule_id: &str,
    macro_anchor_id: &str,
    worker_receipt_id: &str,
    result: &str,
    forbidden_test_edit_detected: bool,
) {
    tape.append(
        AppendRequest::new(
            "OfficialEvaluatorEvidenceImported",
            "writer:test-official-evaluator",
            json!({
                "schema_id": "official_evaluator_evidence_imported.v1",
                "event_type": "OfficialEvaluatorEvidenceImported",
                "evidence_id": evidence_id,
                "instance_id": "django__django-11790",
                "capsule_id": capsule_id,
                "macro_anchor_id": macro_anchor_id,
                "worker_receipt_id": worker_receipt_id,
                "candidate_patch_hash": digest('4'),
                "test_patch_hash": digest('5'),
                "apply_candidate_result": "PASS",
                "apply_test_patch_result": "PASS",
                "target_test_exit_code": 0,
                "target_test_result": result,
                "result": result,
                "failure_class": serde_json::Value::Null,
                "forbidden_test_edit_detected": forbidden_test_edit_detected,
                "forbidden_test_edit_paths": [],
                "truth_source": "official_evaluator_macro_evidence"
            }),
        )
        .predicate_pass(),
    )
    .expect("append official evaluator evidence");
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

fn digest(ch: char) -> String {
    format!("sha256:{}", ch.to_string().repeat(64))
}
