//! WP9a deliverable 4 (`econ_fold_cli`'s "single source of truth" guarantee): the CLI's
//! `fold-and-suggest` subcommand's reported `(Q, N, P)` node states must match, byte-for-byte,
//! calling `turing_economy::routing_fold::fold_routing_state_from_tape` directly in-process
//! on the identical committed event tape. This is the acceptance property the WP9a task
//! description calls "the single implementation of the deterministic math, invoked from
//! Python via subprocess" -- if the CLI ever drifted from the library (e.g. a stale binary,
//! a serialization mismatch, a translation bug), this test would catch it.
//!
//! Spawns the real `econ_fold_cli` binary built by this same crate (`CARGO_BIN_EXE_
//! econ_fold_cli`, set automatically by cargo for integration tests in a package that also
//! owns that bin target) -- no mock, no reimplementation of the CLI's own JSON contract logic
//! beyond what is needed to construct a request and parse a response.

use std::collections::BTreeMap;
use std::io::Write;
use std::process::{Command, Stdio};

use serde_json::{json, Value};

use turing_economy::routing_fold::fold_routing_state_from_tape;
use turing_economy::EconomyEvent;

fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn digest(label: &str) -> String {
    format!("sha256:{}", sha256_hex(label.as_bytes()))
}

fn run_cli(subcommand: &str, request_json: &Value) -> Value {
    let bin = env!("CARGO_BIN_EXE_econ_fold_cli");
    let mut child = Command::new(bin)
        .arg(subcommand)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn econ_fold_cli");
    child
        .stdin
        .take()
        .expect("child stdin")
        .write_all(request_json.to_string().as_bytes())
        .expect("write request to child stdin");
    let output = child.wait_with_output().expect("wait for econ_fold_cli");
    assert!(
        output.status.success(),
        "econ_fold_cli {subcommand} exited non-zero: stderr={}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).expect("econ_fold_cli stdout must be valid JSON")
}

/// Builds a tape with two keys: one that accumulates two `RoutingPriorUpdated` verdicts
/// (one true, one false) and one whose single update is then clawed back (net-zero state) --
/// exercising both the "N>0" and "clawed-back-to-N=0" branches of the fold in one tape.
fn build_tape() -> (Vec<EconomyEvent>, [String; 2]) {
    let domain = "swe_bench_verified_500_campaign".to_string();
    let scaffold_repair = "scaffold:sha256:cross-check-armA".to_string();
    let scaffold_loop = "scaffold:sha256:cross-check-armB".to_string();

    let update_1 = EconomyEvent::routing_prior_updated(
        domain.clone(),
        scaffold_repair.clone(),
        true,
        "verifier:heldout-diff-checker-v1",
        digest("attestation-1"),
    )
    .expect("routing_prior_updated 1");
    let update_2 = EconomyEvent::routing_prior_updated(
        domain.clone(),
        scaffold_repair.clone(),
        false,
        "verifier:heldout-diff-checker-v1",
        digest("attestation-2"),
    )
    .expect("routing_prior_updated 2");
    let update_3 = EconomyEvent::routing_prior_updated(
        domain.clone(),
        scaffold_loop.clone(),
        true,
        "verifier:heldout-diff-checker-v1",
        digest("attestation-3"),
    )
    .expect("routing_prior_updated 3");
    let update_3_hash = match &update_3 {
        EconomyEvent::RoutingPriorUpdated(payload) => payload.event_hash.clone(),
        _ => unreachable!(),
    };
    let clawback_3 = EconomyEvent::routing_prior_clawback(update_3_hash).expect("clawback 3");

    (
        vec![update_1, update_2, update_3, clawback_3],
        [domain.clone() + "\u{0}" + &scaffold_repair, domain + "\u{0}" + &scaffold_loop],
    )
}

fn cli_node_states_by_key(response: &Value) -> BTreeMap<(String, String), (String, u64, u64, String)> {
    let mut map = BTreeMap::new();
    for node in response["node_states"].as_array().expect("node_states array") {
        let key = (
            node["domain_bucket"].as_str().unwrap().to_string(),
            node["scaffold_id"].as_str().unwrap().to_string(),
        );
        map.insert(
            key,
            (
                node["p_q32"].as_str().unwrap().to_string(),
                node["n"].as_u64().unwrap(),
                node["s"].as_u64().unwrap(),
                node["q_eff_q32"].as_str().unwrap().to_string(),
            ),
        );
    }
    map
}

#[test]
fn cli_fold_output_matches_direct_library_fold_call_byte_for_byte() {
    let (tape, _keys) = build_tape();

    // Direct in-process library call (the "single source of truth").
    let direct_nodes = fold_routing_state_from_tape(&BTreeMap::new(), &tape)
        .expect("fold_routing_state_from_tape must succeed on this well-formed tape");
    let mut direct_by_key: BTreeMap<(String, String), (String, u64, u64, String)> = BTreeMap::new();
    for (key, node) in &direct_nodes {
        direct_by_key.insert(
            (key.domain_bucket.clone(), key.scaffold_id.clone()),
            (
                node.p_q32().to_string(),
                node.n(),
                node.s(),
                node.q_eff_q32().to_string(),
            ),
        );
    }

    // Same tape, through the CLI subprocess. `candidate_routes` is a single dummy route so
    // `suggest()` has something non-empty to select over (this test only asserts on
    // `node_states`, not `budget_suggestion`).
    let events_json: Vec<Value> = tape
        .iter()
        .map(|e| serde_json::to_value(e).expect("EconomyEvent serializes"))
        .collect();
    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest.request.v1",
        "committed_routing_events": events_json,
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "route_dummy",
                "market_id": "mkt_dummy",
                "expected_failure_domain": "provider_x",
                "requested_tokens": 1,
                "domain_bucket": "swe_bench_verified_500_campaign",
                "scaffold_id": "scaffold:sha256:cross-check-armA",
            }
        ],
        "price_signal_hash": digest("price-signal"),
        "pput_prior_hash": digest("pput-prior"),
        "router_mode": {"kind": "SoftmaxArgmaxBypass"},
    });
    let response = run_cli("fold-and-suggest", &request);
    let cli_by_key = cli_node_states_by_key(&response);

    assert_eq!(
        direct_by_key.len(),
        cli_by_key.len(),
        "CLI and direct library call must report the same number of routing-key nodes"
    );
    for (key, direct_value) in &direct_by_key {
        let cli_value = cli_by_key
            .get(key)
            .unwrap_or_else(|| panic!("CLI response missing node for key {key:?}"));
        assert_eq!(
            cli_value, direct_value,
            "node state for {key:?} must match byte-for-byte between the CLI and direct library call"
        );
    }

    // Byte-for-byte determinism: replaying the same tape through the CLI twice must yield an
    // identical response (Art 0.2), not just an identical node-state subset.
    let response_2 = run_cli("fold-and-suggest", &request);
    assert_eq!(
        response, response_2,
        "fold-and-suggest must be deterministic across repeated CLI invocations on identical input"
    );
}

#[test]
fn cli_derive_keys_matches_direct_library_calls() {
    use turing_economy::routing_fold::{domain_bucket, scaffold_id, ScaffoldDescriptor};

    let descriptor = ScaffoldDescriptor {
        decomposition_kind: "single_shot_capsule_repair".to_string(),
        toolchain: vec!["deepseek-v4-pro".to_string()],
        team_spec: "solo_worker".to_string(),
        verify_loop: "swebench_official_harness".to_string(),
    };
    let expected_bucket = domain_bucket(Some("Astropy/Astropy"));
    let expected_scaffold_id = scaffold_id(&descriptor).expect("scaffold_id");

    let request = json!({
        "schema": "econ_fold_cli.derive_keys.request.v1",
        "task_family": "Astropy/Astropy",
        "scaffold_descriptors": [
            {
                "label": "armA",
                "decomposition_kind": descriptor.decomposition_kind,
                "toolchain": descriptor.toolchain,
                "team_spec": descriptor.team_spec,
                "verify_loop": descriptor.verify_loop,
            }
        ],
    });
    let response = run_cli("derive-keys", &request);

    assert_eq!(response["domain_bucket"].as_str().unwrap(), expected_bucket);
    assert_eq!(
        response["scaffold_ids"][0]["scaffold_id"].as_str().unwrap(),
        expected_scaffold_id
    );
}
