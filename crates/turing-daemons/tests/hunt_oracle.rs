//! PART C.1 oracle-binding lens (INV-11 / G-MKT-06) finder -- end-to-end confirmation
//! against the REAL `turing-marketd` daemon and a REAL micro-git tape (not just the pure
//! `market_settlement_gate_g_mkt_06` function in isolation). This exercises the exact
//! wiring in `market_settle_response` (crates/turing-daemons/src/lib.rs:1627-1750).
//!
//! Attack: two markets bound to two DIFFERENT, unrelated capsules. A single generic
//! `FailureNode` event (which by its closed schema carries no `capsule_id`) is appended once.
//! Both markets are then settled "NO" against that SAME FailureNode event id. A capsule-bound
//! settlement oracle should accept at most one; the real daemon accepts both.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use serde_json::{Value, json};
use turing_git_tape::append::{Append, AppendRequest};
use turing_git_tape::git;

fn build_market(repo: &Path, market_id: &str, capsule_id: &str, proposer_id: &str) {
    let tape = Append::open(repo).expect("open tape (append market)");
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
}

/// CONFIRMED CANDIDATE (end-to-end, real daemon + real tape): a single genuine FailureNode
/// (unassociated with any specific capsule -- its schema has no `capsule_id` field) settles
/// TWO markets bound to two mutually-exclusive, unrelated capsules, both as "NO", through the
/// real `turing-marketd` `market.settle` RPC and G-MKT-06 wiring.
///
/// NEEDS OWNER (PART D.1, capsule bug #3 / candidate #1): closing this end-to-end requires the
/// same architecture-level change as the pure-gate repro in
/// `turing-predicate/tests/hunt_oracle.rs` -- adding `capsule_id` to the closed/frozen
/// `FailureNodePayload` schema (`pack/05_schemas/failure_node_payload.v1.schema.json`), which
/// changes the committed payload bytes (`content_digest`) for every FailureNode and requires
/// rewiring every emission site. Not a local `market_settle_response`/G-MKT-06 fix.
#[test]
#[ignore = "NEEDS OWNER: requires adding capsule_id to the closed/frozen FailureNodePayload \
            schema (content_digest/hash format change). See PART D.1 capsule bug #3 / \
            candidate #1 in PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md."]
fn marketd_settles_two_unrelated_capsules_no_with_the_same_failurenode_e2e() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let genesis_tape = Append::open(&repo).expect("open tape (genesis)");
    genesis_tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"e".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    build_market(&repo, "mkt_alpha", "cap_alpha_real_capsule", "proposer_alpha");
    build_market(&repo, "mkt_beta", "cap_beta_unrelated_capsule", "proposer_beta");

    let tape = Append::open(&repo).expect("open tape");
    // A single generic FailureNode -- genuinely on-tape, genuinely predicate_fail-class, but
    // with NO capsule association recoverable from its payload (closed schema, per
    // turing-predicate::SettlementReference::FailureNode doc comment).
    let failure_receipt = tape
        .append(
            AppendRequest::new(
                "FailureNode",
                "writer:kernel",
                json!({
                    "verified": false,
                    "failure_class": "SEMANTIC_FAILURE",
                    "candidate_digest": "sha256:".to_string() + &"c".repeat(64),
                    "observation_digest": "sha256:".to_string() + &"d".repeat(64),
                }),
            )
            .predicate_fail(),
        )
        .expect("append failure node");

    let socket = dir.path().join("marketd-oracle-hunt.sock");
    let mut child = spawn_daemon_with_micro_git("turing-marketd", &socket, &repo);
    wait_for_socket(&socket, &mut child);

    let settle_alpha = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_alpha",
            "result": "NO",
            "settlement_event_id": failure_receipt.event_id,
        }),
    );
    let settle_beta = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_beta",
            "result": "NO",
            "settlement_event_id": failure_receipt.event_id,
        }),
    );

    shutdown(socket, child);

    assert_eq!(
        settle_alpha["result"]["event_type"], "MarketSettled",
        "sanity: first settlement against the real daemon should succeed, got {settle_alpha}"
    );

    // Expected (capsule-bound oracle, per INV-11's own stated invariant in SPEC_ECONOMY.md
    // and the capsule brief): the SAME FailureNode cannot legitimize "NO" for a second,
    // unrelated capsule's market. Observed: the real turing-marketd daemon accepts it too.
    assert!(
        settle_beta.get("error").is_some(),
        "CONFIRMED bug candidate (INV-11), end-to-end via real turing-marketd + real \
         micro-git tape: FailureNode event {:?} settled mkt_alpha (capsule \
         cap_alpha_real_capsule) as NO ({settle_alpha}), and the SAME FailureNode event was \
         THEN ALSO accepted to settle the completely unrelated mkt_beta (capsule \
         cap_beta_unrelated_capsule) as NO. Expected: settle_beta should contain \"error\" \
         (capsule cross-check refusal). Observed: {settle_beta}",
        failure_receipt.event_id,
    );
}

/// Second attack vector: "settlement temporal-ordering violation" via market revival.
/// `market_settlement_gate_g_mkt_06` never checks whether the market was already settled --
/// that guard lives entirely outside the gate, in `market_settle_response`'s
/// `projection.status != "open"` check, which is derived from
/// `MarketReplay::from_tape_events` naively `BTreeMap::insert`-ing a fresh "open" projection
/// on ANY `MarketCreated` event for that `market_id` (crates/turing-economy/src/lib.rs
/// `MarketReplay::from_tape_events`, `MarketCreated` arm). Since `event.append_preserve`
/// (crates/turing-daemons/src/lib.rs:351-414) never checks `market_id` uniqueness for
/// `MarketCreated` (despite the registry marking it `predicate_required: true`, that flag is
/// never consulted by the generic PRESERVE-append path -- it hardcodes `.predicate_pass()`),
/// re-appending a `MarketCreated` for an ALREADY-settled `market_id` should (if this gap is
/// real) flip `projection.status` back to "open" and let `market.settle` be called again for
/// the same market, potentially with a conflicting result.
#[test]
fn marketd_allows_resettlement_after_duplicate_marketcreated_reopens_status() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");
    let genesis_tape = Append::open(&repo).expect("open tape (genesis)");
    genesis_tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                json!({"constitution_digest": "sha256:".to_string() + &"f".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    build_market(&repo, "mkt_revive", "cap_revive", "proposer_revive");

    let tape = Append::open(&repo).expect("open tape");
    let candidate_receipt = tape
        .append(
            AppendRequest::new(
                "CandidateAccepted",
                "writer:kernel",
                json!({"candidate_id": "cand_revive", "capsule_id": "cap_revive"}),
            )
            .predicate_pass(),
        )
        .expect("append candidate accepted");
    let failure_receipt = tape
        .append(
            AppendRequest::new(
                "FailureNode",
                "writer:kernel",
                json!({
                    "verified": false,
                    "failure_class": "SEMANTIC_FAILURE",
                    "candidate_digest": "sha256:".to_string() + &"1".repeat(64),
                    "observation_digest": "sha256:".to_string() + &"2".repeat(64),
                }),
            )
            .predicate_fail(),
        )
        .expect("append failure node");

    let socket = dir.path().join("marketd-revive.sock");
    let mut child = spawn_daemon_with_micro_git("turing-marketd", &socket, &repo);
    wait_for_socket(&socket, &mut child);

    // Legitimate first settlement: YES, referencing the real CandidateAccepted for this
    // market's own capsule.
    let first_settle = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_revive",
            "result": "YES",
            "settlement_event_id": candidate_receipt.event_id,
        }),
    );
    assert_eq!(
        first_settle["result"]["event_type"], "MarketSettled",
        "sanity: legitimate first settlement should succeed, got {first_settle}"
    );

    // A second attempt to settle the SAME market again (no duplicate MarketCreated yet) must
    // be refused -- this is the expected, correct baseline behavior.
    let reject_double_settle_before_revival = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_revive",
            "result": "NO",
            "settlement_event_id": failure_receipt.event_id,
        }),
    );
    assert!(
        reject_double_settle_before_revival.get("error").is_some(),
        "sanity: settling an already-settled market must be refused, got {reject_double_settle_before_revival}"
    );

    // Attack: append a SECOND MarketCreated for the SAME market_id via the same
    // append-only tape mechanism the first one used (this is exactly the append path a
    // writer with tape access uses; no RPC-level `market.create` uniqueness check exists
    // anywhere in this codebase).
    build_market(&repo, "mkt_revive", "cap_revive", "proposer_revive");

    let resettle_after_revival = rpc(
        &socket,
        "market.settle",
        json!({
            "writer_id": "writer:kernel",
            "market_id": "mkt_revive",
            "result": "NO",
            "settlement_event_id": failure_receipt.event_id,
        }),
    );

    shutdown(socket, child);

    assert!(
        resettle_after_revival.get("error").is_some(),
        "CONFIRMED bug candidate (INV-11 / INV-2 boundary): after a duplicate MarketCreated \
         event was appended for the ALREADY-settled market_id \"mkt_revive\" (with no \
         uniqueness check anywhere in the codebase), market.settle accepted a SECOND, \
         CONFLICTING settlement (NO) for a market that had already been legitimately settled \
         YES ({first_settle}). Expected: refused (already settled / re-creation should not \
         reopen a market). Observed: {resettle_after_revival}"
    );
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
        "turing-marketd" => env!("CARGO_BIN_EXE_turing-marketd"),
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
    panic!("daemon socket never appeared: {socket:?}");
}
