use std::io::{BufRead, BufReader, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use serde_json::{Value, json};
use turing_git_tape::append::{Append, AppendRequest};
use turing_git_tape::git;

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
fn daemons_reject_world_writable_socket_parents() {
    let dir = tempfile::tempdir().expect("temp dir");
    let unsafe_parent = dir.path().join("unsafe");
    std::fs::create_dir(&unsafe_parent).expect("create unsafe parent");
    let mut perms = std::fs::metadata(&unsafe_parent)
        .expect("metadata")
        .permissions();
    perms.set_mode(0o777);
    std::fs::set_permissions(&unsafe_parent, perms).expect("chmod unsafe parent");

    let socket = unsafe_parent.join("marketd.sock");
    let mut child = Command::new(env!("CARGO_BIN_EXE_turing-marketd"))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
        ])
        .spawn()
        .expect("spawn marketd");

    let start = Instant::now();
    let mut status = None;
    while start.elapsed() < Duration::from_secs(2) {
        if let Some(exit) = child.try_wait().expect("poll child") {
            status = Some(exit);
            break;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    if status.is_none() {
        let _ = child.kill();
    }
    let waited = child.wait().expect("wait daemon child");
    let status = status.unwrap_or(waited);
    assert!(!status.success(), "daemon must reject unsafe socket parent");
}

#[test]
fn marketd_writes_project_scoped_market_snapshot_without_truth_authority() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"1".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");
    tape.append(
        AppendRequest::new(
            "MarketCreated",
            "writer:market",
            json!({
                "schema_id": "market_created.v1",
                "event_type": "MarketCreated",
                "head_effect": "PRESERVE",
                "market_id": "mkt_tape",
                "initial_pool_y": "120",
                "initial_pool_n": "80",
                "k": "9600",
                "truth_status": "statistical_signal_only"
            }),
        )
        .predicate_pass(),
    )
    .expect("append tape market");
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

    let socket = dir.path().join("marketd-snapshot.sock");
    let mut child =
        spawn_daemon_with_project_and_micro_git("turing-marketd", &socket, &project, &repo);
    wait_for_socket(&socket, &mut child);

    let response = rpc(
        &socket,
        "market.snapshot.write",
        json!({
            "events": [
                {
                    "event_type": "MarketCreated",
                    "schema_id": "market_created.v1",
                    "head_effect": "PRESERVE",
                    "market_id": "mkt_forged",
                    "initial_pool_y": "1000",
                    "initial_pool_n": "1000",
                    "k": "10000",
                    "truth_status": "statistical_signal_only"
                }
            ]
        }),
    );

    assert_eq!(
        response["result"]["schema_id"],
        "market_projection_snapshot.v1"
    );
    assert_eq!(response["result"]["source"], "micro_tape_only");
    assert_eq!(response["result"]["market_count"], 1);
    assert_eq!(response["result"]["price_not_truth"], true);
    assert_eq!(response["result"]["emits_authorization"], false);
    assert_eq!(response["result"]["can_move_accepted_head"], false);
    assert_eq!(
        response["result"]["snapshot_path"],
        state_dir
            .join("market_projection.json")
            .to_str()
            .expect("UTF-8 snapshot path")
    );
    assert!(
        response["result"]["market_projection_hash"]
            .as_str()
            .expect("market projection hash")
            .starts_with("sha256:")
    );

    let snapshot =
        std::fs::read_to_string(state_dir.join("market_projection.json")).expect("market snapshot");
    assert!(snapshot.contains(r#""schema_id":"market_projection_snapshot.v1""#));
    assert!(snapshot.contains(r#""price_not_truth":true"#));
    assert!(snapshot.contains(r#""can_move_accepted_head":false"#));
    assert!(snapshot.contains(r#""mkt_tape""#));
    assert!(!snapshot.contains(r#""mkt_forged""#));
    assert!(!snapshot.contains(r#""accepted_head""#));
    assert!(!snapshot.contains("authorization_event"));

    shutdown(socket, child);
}

#[test]
fn marketd_writes_project_scoped_wallet_snapshot_without_truth_authority() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"2".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");
    tape.append(
        AppendRequest::new(
            "PositionMinted",
            "writer:wallet",
            json!({
                "schema_id": "position_minted.v1",
                "event_type": "PositionMinted",
                "market_id": "mkt_tape_wallet",
                "agent_id": "agent_tape",
                "coin_in": "5",
                "yes_out": "5",
                "no_out": "5",
                "invariant": "coin_in == yes_out == no_out"
            }),
        )
        .predicate_pass(),
    )
    .expect("append wallet mint");
    tape.append(
        AppendRequest::new(
            "PositionMinted",
            "writer:wallet",
            json!({
                "schema_id": "position_minted.v1",
                "market_id": "mkt_wallet_tape",
                "agent_id": "agent_tape",
                "coin_in": "5",
                "yes_out": "5",
                "no_out": "5",
                "invariant": "coin_in == yes_out == no_out"
            }),
        )
        .predicate_pass(),
    )
    .expect("append mint");
    tape.append(
        AppendRequest::new(
            "RewardDistributed",
            "writer:wallet",
            json!({
                "schema_id": "reward_distributed.v1",
                "market_id": "mkt_wallet_tape",
                "agent_id": "agent_tape",
                "reward_coin": "2",
                "slash_coin": "1",
                "reason": "PREDICATE_SETTLEMENT"
            }),
        )
        .predicate_pass(),
    )
    .expect("append reward");
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

    let socket = dir.path().join("wallet-snapshot.sock");
    let mut child =
        spawn_daemon_with_project_and_micro_git("turing-marketd", &socket, &project, &repo);
    wait_for_socket(&socket, &mut child);

    let response = rpc(
        &socket,
        "wallet.snapshot.write",
        json!({
            "events": [
                {
                    "event_type": "PositionMinted",
                    "schema_id": "position_minted.v1",
                    "market_id": "mkt_forged",
                    "agent_id": "agent_forged",
                    "coin_in": "50",
                    "yes_out": "50",
                    "no_out": "50",
                    "invariant": "coin_in == yes_out == no_out"
                }
            ]
        }),
    );

    assert_eq!(
        response["result"]["schema_id"],
        "wallet_projection_snapshot.v1"
    );
    assert_eq!(response["result"]["source"], "micro_tape_only");
    assert_eq!(response["result"]["wallet_count"], 1);
    assert_eq!(response["result"]["derived_only"], true);
    assert_eq!(response["result"]["credential_material_included"], false);
    assert_eq!(response["result"]["can_move_accepted_head"], false);
    assert_eq!(
        response["result"]["snapshot_path"],
        state_dir
            .join("wallet_projection.json")
            .to_str()
            .expect("UTF-8 snapshot path")
    );
    assert!(
        response["result"]["wallet_projection_hash"]
            .as_str()
            .expect("wallet projection hash")
            .starts_with("sha256:")
    );

    let snapshot =
        std::fs::read_to_string(state_dir.join("wallet_projection.json")).expect("wallet snapshot");
    assert!(snapshot.contains(r#""schema_id":"wallet_projection_snapshot.v1""#));
    assert!(snapshot.contains(r#""agent_tape""#));
    // E0.1 regression guard: the tape carries TWO PositionMinted events (the
    // second, deliberately, without an inner `payload.event_type` key — that
    // is exactly the shape real tape payloads have) plus a RewardDistributed.
    // A filter keyed on the inner payload's event_type drops the second mint
    // and the reward silently; both must survive into the projection.
    assert!(
        snapshot.contains(r#""yes_positions":{"mkt_tape_wallet":"5","mkt_wallet_tape":"5"}"#),
        "expected both mints in yes_positions, got: {snapshot}"
    );
    assert!(
        snapshot.contains(r#""no_positions":{"mkt_tape_wallet":"5","mkt_wallet_tape":"5"}"#),
        "expected both mints in no_positions, got: {snapshot}"
    );
    // coin_balance = -5 (mint 1) - 5 (mint 2) + 2 (reward) - 1 (slash) = -9;
    // this only lands at -9 if the reward event also survived the filter.
    assert!(
        snapshot.contains(r#""coin_balance":"-9""#),
        "expected reward-adjusted coin_balance -9, got: {snapshot}"
    );
    assert!(!snapshot.contains(r#""agent_forged""#));
    assert!(snapshot.contains(r#""credential_material_included":false"#));
    assert!(!snapshot.contains(r#""accepted_head""#));
    assert!(!snapshot.contains("credential_hash"));

    shutdown(socket, child);
}

/// Builds a `SystemConstitutionAccepted` genesis + `MarketCreated` (with a G-MKT-06 capsule
/// binding) fixture tape, and returns the repo dir handle plus the market's frozen
/// `predicate_set_hash` (so callers can also build a matching/mismatching `CandidateAccepted`).
fn build_market_fixture_tape(
    repo: &Path,
    market_id: &str,
    capsule_id: &str,
    proposer_id: &str,
) -> String {
    git::init_sha256(repo).expect("init micro git");
    let tape = Append::open(repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"9".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");
    let predicate_set_hash = turing_predicate::candidate_predicate_set_hash();
    tape.append(
        AppendRequest::new(
            "MarketCreated",
            "writer:market",
            json!({
                "schema_id": "market_created.v1",
                "event_type": "MarketCreated",
                "head_effect": "PRESERVE",
                "market_id": market_id,
                "initial_pool_y": "1000",
                "initial_pool_n": "1000",
                "k": "1000000",
                "truth_status": "statistical_signal_only",
                "capsule_id": capsule_id,
                "proposer_id": proposer_id,
                "predicate_set_hash": predicate_set_hash,
            }),
        )
        .predicate_pass(),
    )
    .expect("append market");
    predicate_set_hash
}

#[test]
fn marketd_mints_swaps_and_settles_a_real_tape_market_via_g_mkt_06() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    build_market_fixture_tape(&repo, "mkt_e1b", "cap_e1b", "proposer_e1b");
    let tape = Append::open(&repo).expect("open tape");
    let candidate_receipt = tape
        .append(
            AppendRequest::new(
                "CandidateAccepted",
                "writer:kernel",
                json!({"candidate_id": "cand_e1b", "capsule_id": "cap_e1b"}),
            )
            .predicate_pass(),
        )
        .expect("append candidate accepted");
    let accepted_head_before = git::rev_parse_opt(&repo, "refs/turingos/accepted_head")
        .expect("read accepted head before marketd calls");

    let socket = dir.path().join("marketd-mint.sock");
    let mut child = spawn_daemon_with_micro_git("turing-marketd", &socket, &repo);
    wait_for_socket(&socket, &mut child);

    let mint_response = rpc(
        &socket,
        "market.mint",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_e1b",
            "agent_id": "trader_1",
            "coin_in": "50",
            "principal_position_cap": "1000",
        }),
    );
    assert_eq!(mint_response["result"]["event_type"], "PositionMinted");
    assert_eq!(mint_response["result"]["yes_out"], "50");
    assert_eq!(mint_response["result"]["no_out"], "50");
    assert_eq!(mint_response["result"]["can_move_accepted_head"], false);
    assert_eq!(mint_response["result"]["accepted_head_moved"], false);

    let swap_response = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_e1b",
            "trader_id": "trader_1",
            "side": "BUY_YES",
            "pay_coin": "10",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "1000",
        }),
    );
    assert_eq!(swap_response["result"]["event_type"], "AMMSwapExecuted");
    assert_eq!(swap_response["result"]["side"], "BUY_YES");
    assert_eq!(swap_response["result"]["can_move_accepted_head"], false);

    let settle_response = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_e1b",
            "result": "YES",
            "settlement_event_id": candidate_receipt.event_id,
        }),
    );
    assert_eq!(
        settle_response["result"]["event_type"], "MarketSettled",
        "expected a valid G-MKT-06 settlement to be accepted, got: {settle_response}"
    );
    assert_eq!(settle_response["result"]["result"], "YES");
    assert_eq!(settle_response["result"]["can_move_accepted_head"], false);

    let accepted_head_after = git::rev_parse_opt(&repo, "refs/turingos/accepted_head")
        .expect("read accepted head after marketd calls");
    assert_eq!(
        accepted_head_before, accepted_head_after,
        "marketd's mint/swap/settle must never move accepted_head"
    );

    shutdown(socket, child);
}

#[test]
fn marketd_refuses_settlement_that_fails_g_mkt_06() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    build_market_fixture_tape(&repo, "mkt_gate", "cap_real", "proposer_gate");
    let tape = Append::open(&repo).expect("open tape");
    // A CandidateAccepted for a DIFFERENT capsule than the market is bound to.
    let wrong_capsule_receipt = tape
        .append(
            AppendRequest::new(
                "CandidateAccepted",
                "writer:kernel",
                json!({"candidate_id": "cand_other", "capsule_id": "cap_other"}),
            )
            .predicate_pass(),
        )
        .expect("append candidate accepted for a different capsule");
    let failure_receipt = tape
        .append(
            AppendRequest::new(
                "FailureNode",
                "writer:kernel",
                json!({
                    "verified": false,
                    "failure_class": "SEMANTIC_FAILURE",
                    "candidate_digest": "sha256:".to_string() + &"a".repeat(64),
                    "observation_digest": "sha256:".to_string() + &"b".repeat(64),
                }),
            )
            .predicate_fail(),
        )
        .expect("append failure node");

    let socket = dir.path().join("marketd-gate.sock");
    let mut child = spawn_daemon_with_micro_git("turing-marketd", &socket, &repo);
    wait_for_socket(&socket, &mut child);

    let capsule_mismatch = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_gate",
            "result": "YES",
            "settlement_event_id": wrong_capsule_receipt.event_id,
        }),
    );
    assert!(
        capsule_mismatch.get("error").is_some(),
        "settlement referencing a CandidateAccepted for a different capsule must be refused, got: {capsule_mismatch}"
    );

    let wrong_reference_type = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_gate",
            "result": "NO",
            "settlement_event_id": wrong_capsule_receipt.event_id,
        }),
    );
    assert!(
        wrong_reference_type.get("error").is_some(),
        "a NO settlement must reference a FailureNode, not a CandidateAccepted; got: {wrong_reference_type}"
    );

    let missing_reference = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_gate",
            "result": "YES",
            "settlement_event_id": "mu:".to_string() + &"0".repeat(64),
        }),
    );
    assert!(
        missing_reference.get("error").is_some(),
        "a settlement_event_id absent from the tape must be refused, got: {missing_reference}"
    );

    // Sanity: the legitimate FailureNode path (NO) DOES pass G-MKT-06 (existence + type +
    // ordering all hold), proving the above refusals are real gate failures, not a blanket
    // "market.settle never works" bug.
    let valid_no = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_gate",
            "result": "NO",
            "settlement_event_id": failure_receipt.event_id,
        }),
    );
    assert_eq!(
        valid_no["result"]["event_type"], "MarketSettled",
        "a NO settlement referencing a real on-tape FailureNode must be accepted, got: {valid_no}"
    );

    shutdown(socket, child);
}

#[test]
fn marketd_swap_refuses_self_trade_position_cap_and_proposer_conflict() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    build_market_fixture_tape(&repo, "mkt_defense", "cap_defense", "proposer_defense");

    let socket = dir.path().join("marketd-defense.sock");
    let mut child = spawn_daemon_with_micro_git("turing-marketd", &socket, &repo);
    wait_for_socket(&socket, &mut child);

    // Seed trader_1 with a BUY_YES swap.
    let first_swap = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "trader_1",
            "side": "BUY_YES",
            "pay_coin": "10",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "1000",
        }),
    );
    assert_eq!(first_swap["result"]["event_type"], "AMMSwapExecuted");

    // Self-trade: trader_1 immediately takes the opposite side against the same pool with no
    // other principal trading in between.
    let self_trade = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "trader_1",
            "side": "BUY_NO",
            "pay_coin": "5",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "1000",
        }),
    );
    assert!(
        self_trade.get("error").is_some(),
        "trader_1 taking the opposite side immediately after its own swap must be refused, got: {self_trade}"
    );

    // A DIFFERENT trader may legitimately take the opposite side (no self-trade issue).
    let other_trader_swap = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "trader_2",
            "side": "BUY_NO",
            "pay_coin": "5",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "1000",
        }),
    );
    assert_eq!(
        other_trader_swap["result"]["event_type"], "AMMSwapExecuted",
        "a different principal must be able to take the opposite side, got: {other_trader_swap}"
    );

    // Now trader_1 taking BUY_NO is allowed again (trader_2 traded in between).
    let round_reopened = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "trader_1",
            "side": "BUY_NO",
            "pay_coin": "1",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "1000",
        }),
    );
    assert_eq!(
        round_reopened["result"]["event_type"], "AMMSwapExecuted",
        "after an intervening trade by another principal, trader_1 may take the opposite side, got: {round_reopened}"
    );

    // Principal position cap: trader_2 already holds get_y/get_n from its swap above; a tiny
    // cap must refuse further exposure.
    let cap_exceeded = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "trader_2",
            "side": "BUY_NO",
            "pay_coin": "1",
            "principal_position_cap": "0.000000001",
            "proposer_no_deminimis_cap": "1000",
        }),
    );
    assert!(
        cap_exceeded.get("error").is_some(),
        "a principal_position_cap far below existing exposure must refuse the swap, got: {cap_exceeded}"
    );

    // Proposer-conflict: the market's own proposer betting NO above a de-minimis cap.
    let proposer_conflict = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "proposer_defense",
            "side": "BUY_NO",
            "pay_coin": "10",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "0.000000001",
        }),
    );
    assert!(
        proposer_conflict.get("error").is_some(),
        "the market's own proposer betting NO above de-minimis must be refused, got: {proposer_conflict}"
    );

    // The same proposer betting YES on its own capsule is fine (the honest-signal direction).
    let proposer_yes = rpc(
        &socket,
        "market.swap",
        json!({
            "writer_id": "writer:trader",
            "market_id": "mkt_defense",
            "trader_id": "proposer_defense",
            "side": "BUY_YES",
            "pay_coin": "10",
            "principal_position_cap": "1000",
            "proposer_no_deminimis_cap": "0.000000001",
        }),
    );
    assert_eq!(
        proposer_yes["result"]["event_type"], "AMMSwapExecuted",
        "the proposer betting YES on its own capsule must be allowed, got: {proposer_yes}"
    );

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
fn pputd_writes_hidden_project_scoped_pput_snapshot_without_prompt_leakage() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"3".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");
    tape.append(
        AppendRequest::new(
            "CostEvent",
            "writer:pput",
            cost_event_v2("run_tape", "problem_tape", "branch_failed", 17, 100),
        )
        .predicate_pass(),
    )
    .expect("append cost event");
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

    let socket = dir.path().join("pputd-snapshot.sock");
    let mut child =
        spawn_daemon_with_project_and_micro_git("turing-pputd", &socket, &project, &repo);
    wait_for_socket(&socket, &mut child);

    let response = rpc(
        &socket,
        "pput.snapshot.write",
        json!({
            "cost_events": [
                {
                    "schema_id": "cost_event.v1",
                    "event_type": "CostEvent",
                    "head_effect": "PRESERVE",
                    "run_id": "run_forged",
                    "problem_id": "problem_forged",
                    "split": "heldout",
                    "agent_id": "agent_worker",
                    "branch_id": "branch_failed",
                    "capsule_id": "wc_snapshot",
                    "prompt_tokens": 20,
                    "completion_tokens": 30,
                    "tool_tokens": 50,
                    "tool_stdout_tokens": 70,
                    "total_tokens": 170,
                    "wall_time_ms": 1000,
                    "tool_stdout_hash": digest('f'),
                    "counted_in_total": true
                }
            ]
        }),
    );

    assert_eq!(
        response["result"]["schema_id"],
        "pput_projection_snapshot.v1"
    );
    assert_eq!(response["result"]["source"], "micro_tape_only");
    assert_eq!(response["result"]["cost_event_count"], 1);
    assert_eq!(response["result"]["total_tokens"], 17);
    assert_eq!(response["result"]["total_wall_time_ms"], 100);
    assert_eq!(response["result"]["hidden_evaluator"], true);
    assert_eq!(response["result"]["hidden_from_worker_prompt"], true);
    assert_eq!(response["result"]["raw_formula_exposed"], false);
    assert_eq!(response["result"]["heldout_ids_exposed"], false);
    assert_eq!(response["result"]["can_move_accepted_head"], false);
    assert_eq!(
        response["result"]["snapshot_path"],
        state_dir
            .join("pput_projection.json")
            .to_str()
            .expect("UTF-8 snapshot path")
    );
    assert!(
        response["result"]["pput_projection_hash"]
            .as_str()
            .expect("PPUT projection hash")
            .starts_with("sha256:")
    );

    let snapshot =
        std::fs::read_to_string(state_dir.join("pput_projection.json")).expect("PPUT snapshot");
    assert!(snapshot.contains(r#""schema_id":"pput_projection_snapshot.v1""#));
    assert!(snapshot.contains(r#""hidden_from_worker_prompt":true"#));
    assert!(snapshot.contains(r#""raw_formula_exposed":false"#));
    assert!(!snapshot.contains("VPPUT_i"));
    assert!(!snapshot.contains(r#""heldout_ids""#));
    assert!(!snapshot.contains(r#""accepted_head""#));

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
fn viewd_writes_project_scoped_projection_snapshot_without_truth_write() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let tape = Append::open(&repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"4".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");
    tape.append(
        AppendRequest::new(
            "MarketCreated",
            "writer:view",
            json!({
                "schema_id": "market_created.v1",
                "event_type": "MarketCreated",
                "head_effect": "PRESERVE",
                "market_id": "mkt_tape_projection",
                "initial_pool_y": "100",
                "initial_pool_n": "100",
                "k": "10000",
                "truth_status": "statistical_signal_only"
            }),
        )
        .predicate_pass(),
    )
    .expect("append market event");
    tape.append(
        AppendRequest::new(
            "CostEvent",
            "writer:view",
            json!({
                "schema_id": "cost_event.v1",
                "event_type": "CostEvent",
                "head_effect": "PRESERVE",
                "run_id": "run_tape_projection",
                "problem_id": "problem_tape_projection",
                "split": "heldout",
                "agent_id": "agent_projection",
                "branch_id": "branch_projection",
                "capsule_id": "wc_projection",
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "tool_tokens": 1,
                "tool_stdout_tokens": 1,
                "total_tokens": 4,
                "wall_time_ms": 50,
                "tool_stdout_hash": digest('e'),
                "counted_in_total": true
            }),
        )
        .predicate_pass(),
    )
    .expect("append cost event");
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

    let socket = dir.path().join("viewd-snapshot.sock");
    let mut child =
        spawn_daemon_with_project_and_micro_git("turing-viewd", &socket, &project, &repo);
    wait_for_socket(&socket, &mut child);

    let response = rpc(
        &socket,
        "projection.snapshot.write",
        json!({
            "events": [
                {
                    "event_id": format!("mu:{}", "c".repeat(64)),
                    "event_type": "MarketCreated",
                    "subject_id": "mkt_forged"
                },
                {
                    "event_id": format!("mu:{}", "d".repeat(64)),
                    "event_type": "PPUTAccounted",
                    "subject_id": "run_forged"
                }
            ]
        }),
    );

    assert_eq!(response["result"]["schema_id"], "projection_snapshot.v1");
    assert_eq!(response["result"]["source"], "micro_tape_only");
    assert_eq!(response["result"]["can_write_truth"], false);
    assert_eq!(response["result"]["event_count"], 2);
    assert_eq!(
        response["result"]["snapshot_path"],
        state_dir
            .join("projection.json")
            .to_str()
            .expect("UTF-8 snapshot path")
    );
    assert!(
        response["result"]["projection_hash"]
            .as_str()
            .expect("projection hash")
            .starts_with("sha256:")
    );

    let snapshot =
        std::fs::read_to_string(state_dir.join("projection.json")).expect("projection snapshot");
    assert!(snapshot.contains(r#""schema_id":"projection_snapshot.v1""#));
    assert!(snapshot.contains(r#""can_write_truth":false"#));
    assert!(snapshot.contains(r#""projection_hash":"sha256:"#));
    assert!(!snapshot.contains(r#""mkt_forged""#));
    assert!(!snapshot.contains(r#""run_forged""#));

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
            "worker_id": "worker:sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "capsule_id": "wc_rpc",
            "grant_id": "grant_rpc"
        }),
    );

    assert_eq!(dispatched["result"]["receipt_type"], "WorkerDispatched");
    assert_eq!(dispatched["result"]["schema_id"], "execution_receipt.v1");
    assert_eq!(dispatched["result"]["capsule_id"], "wc_rpc");
    assert_eq!(
        dispatched["result"]["worker_id"],
        "worker:sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    );
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

#[test]
fn sidecars_read_project_status_without_truth_authority() {
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

    for name in [
        "turing-execd",
        "turing-marketd",
        "turing-mcp",
        "turing-pputd",
        "turing-viewd",
    ] {
        let socket = dir.path().join(format!("{name}.sock"));
        let mut child = spawn_daemon_with_project(name, &socket, &project);
        wait_for_socket(&socket, &mut child);

        let status = rpc(&socket, "project.status", Value::Null);
        assert_eq!(status["result"]["role"], name);
        assert_eq!(status["result"]["schema_id"], "operator_project.v1");
        assert_eq!(
            status["result"]["project_root"],
            project_root.to_str().expect("UTF-8 canonical project path")
        );
        assert_eq!(status["result"]["truth_source"], "micro_tape");
        assert_eq!(status["result"]["can_write_micro_truth"], false);
        assert_eq!(status["result"]["credential_material_included"], false);
        assert_eq!(status["result"]["can_move_accepted_head"], false);
        assert!(status["result"].get("credential_hash").is_none());
        assert!(status["result"].get("credential_scope_hash").is_none());

        shutdown(socket, child);
    }
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

fn spawn_daemon_with_project(name: &str, socket: &Path, project: &Path) -> Child {
    Command::new(bin(name))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
            "--project",
            project.to_str().expect("UTF-8 project path"),
        ])
        .spawn()
        .expect("spawn daemon")
}

fn spawn_daemon_with_project_and_micro_git(
    name: &str,
    socket: &Path,
    project: &Path,
    micro_git: &Path,
) -> Child {
    Command::new(bin(name))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
            "--micro-git",
            micro_git.to_str().expect("UTF-8 micro git path"),
            "--project",
            project.to_str().expect("UTF-8 project path"),
        ])
        .spawn()
        .expect("spawn daemon")
}

fn spawn_daemon_with_micro_git(name: &str, socket: &Path, micro_git: &Path) -> Child {
    Command::new(bin(name))
        .args([
            "--serve",
            "--socket",
            socket.to_str().expect("UTF-8 socket path"),
            "--micro-git",
            micro_git.to_str().expect("UTF-8 micro git path"),
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

fn cost_event_v2(
    run_id: &str,
    problem_id: &str,
    branch_id: &str,
    total_tokens: u64,
    wall_time_ms: u64,
) -> Value {
    json!({
        "schema_id": "turingos.cost_event.v2",
        "run_id": run_id,
        "problem_id": problem_id,
        "split": "heldout",
        "agent_id": "agent_worker",
        "branch_id": branch_id,
        "capsule_id": "wc_snapshot",
        "receipt_id": "rcpt:".to_string() + &"1".repeat(64),
        "worker": {
            "adapter_kind": "fake",
            "provider": "fixture",
            "model_id_requested": "fixture-model",
            "model_id_resolved": "fixture-model-20260702",
            "endpoint": "fixture://pput",
            "request_id": "req_fixture_pput",
            "response_sha256": digest('b')
        },
        "usage": {
            "input_tokens": total_tokens / 2,
            "output_tokens": total_tokens - (total_tokens / 2),
            "total_tokens": total_tokens,
            "provider_usage_raw_sha256": digest('c')
        },
        "cost": {
            "cost_source_kind": "fixture",
            "cost_microusd": 0,
            "price_table_digest": "sha256:21db84a3efaf6e7ff8b185e7cb958243adc5a23def982ea0fcce0bc5fc7c6f2c",
            "bound_kind": null
        },
        "wall_time_ms": wall_time_ms,
        "tool_stdout_hash": digest('f'),
        "counted_in_total": true
    })
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
