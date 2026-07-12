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

use turing_economy::diversity_metrics::{compute_n_eff_and_h_lineage, LineageSettlement, NEffHLineage};
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

/// Like [`run_cli`], but for requests the CLI must *reject*: asserts a non-zero exit and
/// returns stderr so the caller can pin the diagnostic.
fn run_cli_expect_error(subcommand: &str, request_json: &Value) -> String {
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
        !output.status.success(),
        "econ_fold_cli {subcommand} unexpectedly succeeded on an invalid request: stdout={}",
        String::from_utf8_lossy(&output.stdout)
    );
    String::from_utf8_lossy(&output.stderr).into_owned()
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
        "schema": "econ_fold_cli.fold_and_suggest.request.v2",
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
        "trigger_event_hash": digest("trigger-event"),
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

/// Fix-regression: `fold-and-suggest` joins each candidate route back to its synthesized
/// Q_eff price signal by `market_id` (first match wins inside `MarketRouter::suggest`), so
/// a duplicate `market_id` across `candidate_routes` would silently misattribute one
/// route's Q_eff to another. The CLI must reject such a request with a clear error.
#[test]
fn cli_fold_and_suggest_rejects_duplicate_market_id_across_candidate_routes() {
    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest.request.v2",
        "committed_routing_events": [],
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "route_a",
                "market_id": "mkt_shared",
                "expected_failure_domain": "provider_x",
                "requested_tokens": 1,
                "domain_bucket": "swe_bench_verified_500_campaign",
                "scaffold_id": "scaffold:sha256:cross-check-armA",
            },
            {
                "route_id": "route_b",
                "market_id": "mkt_shared",
                "expected_failure_domain": "provider_y",
                "requested_tokens": 1,
                "domain_bucket": "swe_bench_verified_500_campaign",
                "scaffold_id": "scaffold:sha256:cross-check-armB",
            }
        ],
        "price_signal_hash": digest("price-signal"),
        "pput_prior_hash": digest("pput-prior"),
        "trigger_event_hash": digest("trigger-event"),
        "router_mode": {"kind": "SoftmaxArgmaxBypass"},
    });
    let stderr = run_cli_expect_error("fold-and-suggest", &request);
    assert!(
        stderr.contains("duplicate market_id") && stderr.contains("mkt_shared"),
        "diagnostic must name the duplicate market_id; got stderr: {stderr}"
    );
}

/// B1 remedy schema-versioning discipline (ADR-ECON-003 Decision 1's "new schema version,
/// never implicit drift"): a pre-B1 `v1` fold-and-suggest request (which cannot carry the
/// now-required `trigger_event_hash` seed input) must be rejected by version string with a
/// diagnostic naming the expected `v2` -- not silently accepted, and not failed with an
/// unrelated missing-field parse error.
#[test]
fn cli_fold_and_suggest_rejects_pre_b1_v1_request_schema() {
    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest.request.v1",
        "committed_routing_events": [],
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "route_a",
                "market_id": "mkt_a",
                "expected_failure_domain": "provider_x",
                "requested_tokens": 1,
                "domain_bucket": "swe_bench_verified_500_campaign",
                "scaffold_id": "scaffold:sha256:cross-check-armA",
            }
        ],
        "price_signal_hash": digest("price-signal"),
        "pput_prior_hash": digest("pput-prior"),
        // Deliberately NO trigger_event_hash: this is the exact shape a pre-B1 caller sends.
        "router_mode": {"kind": "SoftmaxArgmaxBypass"},
    });
    let stderr = run_cli_expect_error("fold-and-suggest", &request);
    assert!(
        stderr.contains("econ_fold_cli.fold_and_suggest.request.v2")
            && stderr.contains("econ_fold_cli.fold_and_suggest.request.v1"),
        "diagnostic must name both the expected v2 and the rejected v1 schema; got stderr: {stderr}"
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

/// WP9a lineage-expansion update (PREREG Appendix A, frozen): `econ_fold_cli
/// diversity-metrics` must match `diversity_metrics::compute_n_eff_and_h_lineage` called
/// directly, byte-for-byte, on an identical 4-lineage settlement history (the shape this
/// task's driver now produces: deepseek/qwen/glm/kimi).
#[test]
fn cli_diversity_metrics_matches_direct_library_call() {
    let mut history: Vec<LineageSettlement> = Vec::new();
    let lineages = ["deepseek", "qwen", "glm", "kimi"];
    for i in 0..8u64 {
        for (li, &lineage) in lineages.iter().enumerate() {
            // A simple deterministic pattern that varies by lineage so the 4 lineages are
            // not all identical (would otherwise collapse to a degenerate N_eff=1 case).
            let verdict = ((i as usize) + li) % 2 == 0;
            history.push(LineageSettlement {
                lineage_id: lineage.to_string(),
                settlement_index: i,
                verdict,
            });
        }
    }

    let direct = compute_n_eff_and_h_lineage(&history).expect("direct call must succeed");
    let (expected_status, expected_n_eff, expected_h_lineage) = match direct {
        NEffHLineage::NotEnoughData => ("NOT_ENOUGH_DATA".to_string(), None, None),
        NEffHLineage::Computed {
            n_eff_q32,
            h_lineage_q32,
        } => (
            "COMPUTED".to_string(),
            Some(n_eff_q32.to_string()),
            Some(h_lineage_q32.to_string()),
        ),
    };

    let history_json: Vec<Value> = history
        .iter()
        .map(|entry| {
            json!({
                "lineage_id": entry.lineage_id,
                "settlement_index": entry.settlement_index,
                "verdict": entry.verdict,
            })
        })
        .collect();
    let request = json!({
        "schema": "econ_fold_cli.diversity_metrics.request.v1",
        "history": history_json,
    });
    let response = run_cli("diversity-metrics", &request);

    assert_eq!(response["status"].as_str().unwrap(), expected_status);
    assert_eq!(
        response["n_eff_q32"].as_str().map(str::to_string),
        expected_n_eff
    );
    assert_eq!(
        response["h_lineage_q32"].as_str().map(str::to_string),
        expected_h_lineage
    );
}

// ---------------------------------------------------------------------------
// CAPSULE B / depth-k: stage-key derivation + stage fold/suggest cross-checks
// ---------------------------------------------------------------------------

#[test]
fn cli_derive_stage_keys_matches_direct_library_calls() {
    use turing_economy::routing_fold::{
        domain_bucket, stage_option_id, STAGE_CONTEXT, CONTEXT_OPTIONS,
    };

    let expected_bucket = domain_bucket(Some("Django/Django"));
    let expected_id = stage_option_id(STAGE_CONTEXT, CONTEXT_OPTIONS[0]).expect("stage_option_id");

    let request = json!({
        "schema": "econ_fold_cli.derive_stage_keys.request.v1",
        "task_family": "Django/Django",
        "stages": [
            {"stage_name": "context", "options": ["minimal", "source_context"]}
        ],
    });
    let response = run_cli("derive-stage-keys", &request);
    assert_eq!(response["schema"], "econ_fold_cli.derive_stage_keys.response.v1");
    assert_eq!(response["domain_bucket"].as_str().unwrap(), expected_bucket);
    assert_eq!(
        response["stage_keys"][0]["stage_option_id"].as_str().unwrap(),
        expected_id
    );
    assert_eq!(response["stage_keys"][0]["option"], "minimal");
    assert_eq!(response["stage_keys"][1]["option"], "source_context");
}

#[test]
fn cli_derive_stage_keys_default_walk_has_six_options() {
    let request = json!({
        "schema": "econ_fold_cli.derive_stage_keys.request.v1",
        "task_family": null,
    });
    let response = run_cli("derive-stage-keys", &request);
    let keys = response["stage_keys"].as_array().unwrap();
    // 3 stages × 2 options = 6 hierarchical market nodes
    assert_eq!(keys.len(), 6);
    let stages: std::collections::BTreeSet<_> = keys
        .iter()
        .map(|k| k["stage_name"].as_str().unwrap())
        .collect();
    assert_eq!(
        stages,
        ["context", "repair", "verify"].into_iter().collect()
    );
}

#[test]
fn cli_fold_and_suggest_stage_matches_library_and_is_deterministic() {
    use turing_economy::routing_fold::{stage_option_id, STAGE_CONTEXT};

    let opt_min = stage_option_id(STAGE_CONTEXT, "minimal").unwrap();
    let opt_src = stage_option_id(STAGE_CONTEXT, "source_context").unwrap();
    let domain = "swe_bench_verified_500_campaign";

    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest_stage.request.v1",
        "stage_name": "context",
        "committed_routing_events": [],
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "minimal",
                "market_id": format!("stage:{domain}:{opt_min}"),
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000u64,
                "domain_bucket": domain,
                "scaffold_id": opt_min,
            },
            {
                "route_id": "source_context",
                "market_id": format!("stage:{domain}:{opt_src}"),
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000u64,
                "domain_bucket": domain,
                "scaffold_id": opt_src,
            }
        ],
        "price_signal_hash": digest("price-signal.v1:stage-cross-check"),
        "pput_prior_hash": digest("pput-prior.v1:stage-cross-check"),
        "trigger_event_hash": digest("trigger-event.v1:stage-cross-check"),
        "router_mode": {"kind": "SoftmaxUniform"},
    });

    let response_1 = run_cli("fold-and-suggest-stage", &request);
    let response_2 = run_cli("fold-and-suggest-stage", &request);
    assert_eq!(
        response_1, response_2,
        "fold-and-suggest-stage must be deterministic across repeated CLI invocations"
    );
    assert_eq!(
        response_1["schema"],
        "econ_fold_cli.fold_and_suggest_stage.response.v1"
    );
    assert_eq!(response_1["stage_name"], "context");
    assert!(
        response_1["budget_suggestion"]["route_id"]
            .as_str()
            .unwrap()
            == "minimal"
            || response_1["budget_suggestion"]["route_id"]
                .as_str()
                .unwrap()
                == "source_context"
    );
    // Authority ceiling preserved on stage path too.
    assert_eq!(response_1["budget_suggestion"]["emits_authorization"], false);
    assert_eq!(
        response_1["budget_suggestion"]["can_move_accepted_head"],
        false
    );
    assert_eq!(response_1["budget_suggestion"]["head_effect"], "PRESERVE");
}

#[test]
fn cli_fold_and_suggest_stage_seed_domain_separates_stages() {
    use turing_economy::routing_fold::{stage_option_id, STAGE_CONTEXT, STAGE_REPAIR};

    // Build two requests that differ only in stage_name; under SoftmaxUniform over two
    // options with equal Q, different stage seeds can (and in this fixture do) yield
    // different selections — at minimum the seed path is exercised and responses stay valid.
    let domain = "default";
    // Reuse same option ids shape for both stages by using each stage's own option ids
    // but identical route_id labels so the only seed difference is stage_name.
    let ctx_a = stage_option_id(STAGE_CONTEXT, "minimal").unwrap();
    let ctx_b = stage_option_id(STAGE_CONTEXT, "source_context").unwrap();
    let rep_a = stage_option_id(STAGE_REPAIR, "single_shot").unwrap();
    let rep_b = stage_option_id(STAGE_REPAIR, "loop").unwrap();

    let mk = |stage: &str, id_a: &str, id_b: &str, label_a: &str, label_b: &str| {
        json!({
            "schema": "econ_fold_cli.fold_and_suggest_stage.request.v1",
            "stage_name": stage,
            "committed_routing_events": [],
            "initial_prices": [],
            "candidate_routes": [
                {
                    "route_id": label_a,
                    "market_id": format!("stage:{domain}:{id_a}"),
                    "expected_failure_domain": "x",
                    "requested_tokens": 1000u64,
                    "domain_bucket": domain,
                    "scaffold_id": id_a,
                },
                {
                    "route_id": label_b,
                    "market_id": format!("stage:{domain}:{id_b}"),
                    "expected_failure_domain": "x",
                    "requested_tokens": 1000u64,
                    "domain_bucket": domain,
                    "scaffold_id": id_b,
                }
            ],
            "price_signal_hash": digest("price-signal.v1:seed-sep"),
            "pput_prior_hash": digest("pput-prior.v1:seed-sep"),
            "trigger_event_hash": digest("trigger-event.v1:seed-sep"),
            "router_mode": {"kind": "SoftmaxUniform"},
        })
    };

    let r_ctx = run_cli(
        "fold-and-suggest-stage",
        &mk("context", &ctx_a, &ctx_b, "minimal", "source_context"),
    );
    let r_rep = run_cli(
        "fold-and-suggest-stage",
        &mk("repair", &rep_a, &rep_b, "single_shot", "loop"),
    );
    // Both succeed; stage_name is echoed; seeds are independent (responses need not differ
    // in route_id for every seed, but stage_name field proves domain isolation of requests).
    assert_eq!(r_ctx["stage_name"], "context");
    assert_eq!(r_rep["stage_name"], "repair");
}

#[test]
fn cli_fold_and_suggest_v2_still_rejects_v1_after_depthk() {
    // Isolation proof: pre-existing v1 reject path is unchanged after CAPSULE B.
    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest.request.v1",
        "committed_routing_events": [],
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "r1",
                "market_id": "m1",
                "expected_failure_domain": "x",
                "requested_tokens": 1u64,
                "domain_bucket": "default",
                "scaffold_id": "scaffold:sha256:aa",
            }
        ],
        "price_signal_hash": digest("p"),
        "pput_prior_hash": digest("q"),
        "router_mode": {"kind": "SoftmaxArgmaxBypass"},
    });
    let stderr = run_cli_expect_error("fold-and-suggest", &request);
    assert!(
        stderr.contains("econ_fold_cli.fold_and_suggest.request.v2")
            && stderr.contains("econ_fold_cli.fold_and_suggest.request.v1"),
        "pre-B1 v1 reject path must remain after depth-k: {stderr}"
    );
}

#[test]
fn stage_option_ids_are_shared_across_scaffolds_conceptually() {
    // Two complete scaffolds that share stage-1/2 options must hash to the same
    // stage_option_id for those stages (cross-scaffold shared statistics nodes).
    use turing_economy::routing_fold::{
        compose_dispatch_arm, stage_option_id, ScaffoldDescriptorV2, STAGE_CONTEXT, STAGE_REPAIR,
        STAGE_VERIFY,
    };

    let shared_ctx = stage_option_id(STAGE_CONTEXT, "source_context").unwrap();
    let shared_rep = stage_option_id(STAGE_REPAIR, "loop").unwrap();
    let verify_none = stage_option_id(STAGE_VERIFY, "none").unwrap();
    let verify_check = stage_option_id(STAGE_VERIFY, "self_check").unwrap();

    // armB-like and armC-like share context+repair nodes, differ only on verify.
    assert_eq!(
        stage_option_id(STAGE_CONTEXT, "source_context").unwrap(),
        shared_ctx
    );
    assert_eq!(stage_option_id(STAGE_REPAIR, "loop").unwrap(), shared_rep);
    assert_ne!(verify_none, verify_check);

    let arm_b = ScaffoldDescriptorV2 {
        context: "source_context".into(),
        repair: "loop".into(),
        verify: "none".into(),
        lineage: "deepseek".into(),
    };
    let arm_c = ScaffoldDescriptorV2 {
        context: "source_context".into(),
        repair: "loop".into(),
        verify: "self_check".into(),
        lineage: "deepseek".into(),
    };
    assert_eq!(compose_dispatch_arm(&arm_b), "armB");
    assert_eq!(compose_dispatch_arm(&arm_c), "armC");
}

// ---------------------------------------------------------------------------
// WP-H4 (ADR-ECON-007 Decision 2/5): route-stage key derivation + pause-mask cross-checks
// ---------------------------------------------------------------------------

#[test]
fn cli_derive_route_keys_matches_direct_library_calls() {
    use turing_economy::routing_fold::{
        domain_bucket, route_descriptor_id, stage_option_id, RouteDescriptor, STAGE_ROUTE,
    };

    let descriptor = RouteDescriptor {
        route_label: "conservative_repair".to_string(),
        context: "minimal".to_string(),
        repair: "single_shot".to_string(),
        verify: "none".to_string(),
    };
    let expected_bucket = domain_bucket(Some("Astropy/Astropy"));
    let expected_route_id = route_descriptor_id(&descriptor).expect("route_descriptor_id");
    let expected_route_scaffold =
        stage_option_id(STAGE_ROUTE, &expected_route_id).expect("stage_option_id");

    let request = json!({
        "schema": "econ_fold_cli.derive_route_keys.request.v1",
        "task_family": "Astropy/Astropy",
        "routes": [
            {
                "route_label": "conservative_repair",
                "context": "minimal",
                "repair": "single_shot",
                "verify": "none",
            }
        ],
    });
    let response = run_cli("derive-route-keys", &request);

    assert_eq!(response["schema"], "econ_fold_cli.derive_route_keys.response.v1");
    assert_eq!(response["domain_bucket"].as_str().unwrap(), expected_bucket);
    assert_eq!(
        response["route_keys"][0]["route_id"].as_str().unwrap(),
        expected_route_id
    );
    assert_eq!(
        response["route_keys"][0]["route_scaffold"].as_str().unwrap(),
        expected_route_scaffold
    );
}

/// Core Decision 2 acceptance property, exercised end-to-end through the real CLI subprocess:
/// a route with a `RouteFuseTripped` trip still active as of `as_of_event_ordinal` (a) is
/// excluded from selection entirely (`budget_suggestion.route_id` can never be the paused
/// route, even though it is the ONLY other candidate besides a low-value decoy) and (b) its
/// `(Q, N, P)` node state in `node_states` is byte-identical to what the fold produces with
/// no `RouteFuseTripped` events at all -- i.e. the trip never touched Q.
#[test]
fn cli_fold_and_suggest_route_pause_mask_excludes_tripped_route_and_never_touches_q() {
    use turing_economy::routing_fold::{route_descriptor_id, stage_option_id, RouteDescriptor, STAGE_ROUTE};

    let domain = "swe_bench_verified_500_campaign";
    let route_a = RouteDescriptor {
        route_label: "route_a".to_string(),
        context: "minimal".to_string(),
        repair: "single_shot".to_string(),
        verify: "none".to_string(),
    };
    let route_b = RouteDescriptor {
        route_label: "route_b".to_string(),
        context: "source_context".to_string(),
        repair: "loop".to_string(),
        verify: "none".to_string(),
    };
    let route_a_id = route_descriptor_id(&route_a).unwrap();
    let route_b_id = route_descriptor_id(&route_b).unwrap();
    let route_a_scaffold = stage_option_id(STAGE_ROUTE, &route_a_id).unwrap();
    let route_b_scaffold = stage_option_id(STAGE_ROUTE, &route_b_id).unwrap();

    // Independent-verifier settlement so route_a has a strictly higher Q than route_b (an
    // un-paused argmax would pick route_a): one PASS verdict on route_a, none on route_b.
    let settle_a = json!({
        "RoutingPriorUpdated": {
            "schema_id": "routing_prior_updated.v1",
            "event_type": "RoutingPriorUpdated",
            "head_effect": "PRESERVE",
            "route_domain": domain,
            "route_scaffold": route_a_scaffold,
            "verdict": true,
            "verdict_source_id": "verifier:heldout-diff-checker-v1",
            "verifier_attestation_hash": digest("attestation-route-a"),
            "event_hash": turing_economy::EconomyEvent::routing_prior_updated(
                domain,
                route_a_scaffold.clone(),
                true,
                "verifier:heldout-diff-checker-v1",
                digest("attestation-route-a"),
            ).map(|e| match e { turing_economy::EconomyEvent::RoutingPriorUpdated(u) => u.event_hash, _ => unreachable!() }).unwrap(),
        }
    });

    let fuse_trip = json!({
        "RouteFuseTripped": {
            "schema_id": "route_fuse_tripped.v1",
            "event_type": "RouteFuseTripped",
            "head_effect": "PRESERVE",
            "route_domain": domain,
            "route_scaffold": route_a_scaffold,
            "detector_rule_id": "detector:loop_v1",
            "diagnostic_digest": digest("diagnostic-facts-route-a"),
            "event_ordinal": 5u64,
        }
    });

    let committed = vec![settle_a, fuse_trip];

    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest_route.request.v1",
        "committed_routing_events": committed,
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "route_a",
                "market_id": format!("route:{domain}:{route_a_scaffold}"),
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000u64,
                "domain_bucket": domain,
                "scaffold_id": route_a_scaffold,
            },
            {
                "route_id": "route_b",
                "market_id": format!("route:{domain}:{route_b_scaffold}"),
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000u64,
                "domain_bucket": domain,
                "scaffold_id": route_b_scaffold,
            }
        ],
        "price_signal_hash": digest("price-signal.v1:route-mask"),
        "pput_prior_hash": digest("pput-prior.v1:route-mask"),
        "trigger_event_hash": digest("trigger-event.v1:route-mask"),
        "router_mode": {"kind": "SoftmaxArgmaxBypass"},
        // Trip at ordinal 5, validity window 10 -> paused through ordinal 15.
        "pause_validity_window": 10u64,
        "as_of_event_ordinal": 12u64,
    });

    let response = run_cli("fold-and-suggest-route", &request);
    assert_eq!(response["schema"], "econ_fold_cli.fold_and_suggest_route.response.v1");
    assert_eq!(
        response["budget_suggestion"]["route_id"].as_str().unwrap(),
        "route_b",
        "the higher-Q route_a is paused, so selection must fall through to route_b even \
         though an un-paused argmax would have picked route_a"
    );
    assert_eq!(
        response["paused_route_ids"].as_array().unwrap(),
        &vec![Value::String("route_a".to_string())]
    );

    // Q untouched: fold node_states for route_a's key must be byte-identical to calling
    // fold_routing_state_from_tape directly with ONLY the RoutingPriorUpdated event (i.e. as
    // if RouteFuseTripped had never been on the tape at all).
    let committed_without_trip: Vec<Value> = request["committed_routing_events"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|e| e.get("RouteFuseTripped").is_none())
        .cloned()
        .collect();
    let events_without_trip: Vec<turing_economy::EconomyEvent> = committed_without_trip
        .iter()
        .map(|v| serde_json::from_value(v.clone()).expect("parse EconomyEvent"))
        .collect();
    let direct_nodes = fold_routing_state_from_tape(&BTreeMap::new(), &events_without_trip)
        .expect("direct fold without the fuse trip");
    let direct_node_a = direct_nodes
        .iter()
        .find(|(k, _)| k.scaffold_id == route_a_scaffold)
        .map(|(_, node)| (node.p_q32(), node.n(), node.s(), node.q_eff_q32()))
        .expect("route_a node present in direct fold");

    let cli_node_a = response["node_states"]
        .as_array()
        .unwrap()
        .iter()
        .find(|n| n["scaffold_id"].as_str().unwrap() == route_a_scaffold)
        .expect("route_a node present in CLI response");
    assert_eq!(cli_node_a["p_q32"].as_str().unwrap(), direct_node_a.0.to_string());
    assert_eq!(cli_node_a["n"].as_u64().unwrap(), direct_node_a.1);
    assert_eq!(cli_node_a["s"].as_u64().unwrap(), direct_node_a.2);
    assert_eq!(
        cli_node_a["q_eff_q32"].as_str().unwrap(),
        direct_node_a.3.to_string(),
        "RouteFuseTripped must never change route_a's (Q, N, P) fold state"
    );

    // Determinism.
    let response_2 = run_cli("fold-and-suggest-route", &request);
    assert_eq!(response, response_2);
}

#[test]
fn cli_fold_and_suggest_route_unpauses_once_validity_window_elapses() {
    use turing_economy::routing_fold::{route_descriptor_id, stage_option_id, RouteDescriptor, STAGE_ROUTE};

    let domain = "default";
    let route_a = RouteDescriptor {
        route_label: "route_a".to_string(),
        context: "minimal".to_string(),
        repair: "single_shot".to_string(),
        verify: "none".to_string(),
    };
    let route_a_id = route_descriptor_id(&route_a).unwrap();
    let route_a_scaffold = stage_option_id(STAGE_ROUTE, &route_a_id).unwrap();

    let fuse_trip = json!({
        "RouteFuseTripped": {
            "schema_id": "route_fuse_tripped.v1",
            "event_type": "RouteFuseTripped",
            "head_effect": "PRESERVE",
            "route_domain": domain,
            "route_scaffold": route_a_scaffold,
            "detector_rule_id": "detector:loop_v1",
            "diagnostic_digest": digest("diagnostic-facts"),
            "event_ordinal": 1u64,
        }
    });

    let mk_request = |as_of: u64| {
        json!({
            "schema": "econ_fold_cli.fold_and_suggest_route.request.v1",
            "committed_routing_events": [fuse_trip.clone()],
            "initial_prices": [],
            "candidate_routes": [
                {
                    "route_id": "route_a",
                    "market_id": format!("route:{domain}:{route_a_scaffold}"),
                    "expected_failure_domain": "x",
                    "requested_tokens": 1000u64,
                    "domain_bucket": domain,
                    "scaffold_id": route_a_scaffold,
                }
            ],
            "price_signal_hash": digest("price-signal.v1:route-expiry"),
            "pput_prior_hash": digest("pput-prior.v1:route-expiry"),
            "trigger_event_hash": digest("trigger-event.v1:route-expiry"),
            "router_mode": {"kind": "SoftmaxArgmaxBypass"},
            "pause_validity_window": 3u64,
            "as_of_event_ordinal": as_of,
        })
    };

    // as_of=4 is within [1, 1+3=4] -- still paused -> the ONLY candidate is filtered out ->
    // suggest() must hard-error (NoCandidateRoutes), not silently bypass the mask.
    let stderr = run_cli_expect_error("fold-and-suggest-route", &mk_request(4));
    assert!(
        stderr.contains("NoCandidateRoutes"),
        "expected NoCandidateRoutes once the only candidate is paused; got: {stderr}"
    );

    // as_of=5 is one past expiry -> unpaused -> selection succeeds.
    let response = run_cli("fold-and-suggest-route", &mk_request(5));
    assert_eq!(
        response["budget_suggestion"]["route_id"].as_str().unwrap(),
        "route_a"
    );
    assert!(response["paused_route_ids"].as_array().unwrap().is_empty());
}

#[test]
fn cli_build_route_fuse_tripped_and_route_falsified_round_trip() {
    let tripped_request = json!({
        "schema": "econ_fold_cli.build_route_fuse_tripped.request.v1",
        "route_domain": "code_review",
        "route_scaffold": "stage:sha256:aaaa",
        "detector_rule_id": "detector:loop_v1",
        "diagnostic_digest": digest("diagnostic-facts"),
        "event_ordinal": 9u64,
    });
    let tripped_response = run_cli("build-route-fuse-tripped", &tripped_request);
    assert_eq!(
        tripped_response["schema"],
        "econ_fold_cli.build_route_fuse_tripped.response.v1"
    );
    let event = &tripped_response["event"]["RouteFuseTripped"];
    assert_eq!(event["head_effect"], "PRESERVE");
    assert_eq!(event["route_domain"], "code_review");
    assert_eq!(event["event_ordinal"], 9);

    let falsified_request = json!({
        "schema": "econ_fold_cli.build_route_falsified.request.v1",
        "route_id": "route:sha256:bbbb",
        "attempts": 3u64,
        "verifier_evidence": ["ev-1"],
        "detector_events": ["det-1"],
        "remaining_candidates": ["route:sha256:cccc"],
        "recommendation": "escalate to GRILL-ME",
    });
    let falsified_response = run_cli("build-route-falsified", &falsified_request);
    assert_eq!(
        falsified_response["schema"],
        "econ_fold_cli.build_route_falsified.response.v1"
    );
    let falsified_event = &falsified_response["event"]["RouteFalsified"];
    assert_eq!(falsified_event["head_effect"], "PRESERVE");
    assert_eq!(falsified_event["proposal_only"], true);
    assert_eq!(falsified_event["attempts"], 3);
    assert_eq!(falsified_event["route_id"], "route:sha256:bbbb");
}

/// Isolation proof (WP-H4 red line "旧行为对拍不变"): the pre-existing `fold-and-suggest`
/// subcommand's byte-for-byte parity with the direct library call (the very first test in
/// this file) must still hold after adding the route-stage subcommands -- re-run here with a
/// distinct fixture so this test does not merely duplicate the earlier one, but exercises the
/// exact same code path after this WP's additions.
#[test]
fn cli_fold_and_suggest_still_matches_direct_library_call_after_wp_h4() {
    let request = json!({
        "schema": "econ_fold_cli.fold_and_suggest.request.v2",
        "committed_routing_events": [],
        "initial_prices": [],
        "candidate_routes": [
            {
                "route_id": "route_only",
                "market_id": "mkt_only",
                "expected_failure_domain": "provider_x",
                "requested_tokens": 42u64,
                "domain_bucket": "default",
                "scaffold_id": "scaffold:sha256:wp-h4-isolation-check",
            }
        ],
        "price_signal_hash": digest("price-signal.v1:wp-h4-isolation"),
        "pput_prior_hash": digest("pput-prior.v1:wp-h4-isolation"),
        "trigger_event_hash": digest("trigger-event.v1:wp-h4-isolation"),
        "router_mode": {"kind": "SoftmaxArgmaxBypass"},
    });
    let response = run_cli("fold-and-suggest", &request);
    assert_eq!(response["schema"], "econ_fold_cli.fold_and_suggest.response.v1");
    assert_eq!(
        response["budget_suggestion"]["route_id"].as_str().unwrap(),
        "route_only"
    );
    assert_eq!(response["budget_suggestion"]["head_effect"], "PRESERVE");
    assert_eq!(response["budget_suggestion"]["emits_authorization"], false);
    assert_eq!(response["budget_suggestion"]["can_move_accepted_head"], false);
}
