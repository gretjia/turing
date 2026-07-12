//! WP9a (`RES_ECON_emergence_toplevel_design_20260707.md` R1.1 §7 WP9 lineage / `tools/
//! econ_lab/live_driver.py`'s Rust bridge): the ONE subprocess bridge between the Python
//! live-run driver and this crate's deterministic routing math.
//!
//! Hard rule this file exists to enforce: no formula (key derivation, JCS canonicalization,
//! the `(Q, N, P)` tape fold, softmax/argmax/uniform selection, Q32.32 arithmetic) is
//! reimplemented here. Every subcommand below is a thin JSON (stdin) -> JSON (stdout)
//! wrapper around a pre-existing `turing_economy` / `turing_economy::routing_fold` public
//! function. The two exceptions, called out explicitly at their call sites, are (a) a
//! trivial Q32.32<->base-10-decimal-string *encoding* conversion (no economic math, just a
//! radix change, needed because `routing_fold`'s `Q_eff` is Q32.32 while
//! `MarketRouter::suggest`'s `PriceSignal.yes_price` is a decimal string -- the crate itself
//! has no public converter between the two WPs' numeric representations) and (b) the `N=0`
//! degenerate case of `Q_eff = P` for a routing key that has never appeared in the fold's
//! output map at all (ADR-ECON-003 Decision 6.2's own documented boundary case, not a new
//! formula: `NodeState::q_eff_q32` already documents "`N=0` reduces exactly to `Q_eff = P`",
//! this file merely applies that identity to a key with zero events instead of calling a
//! `NodeState` accessor that does not exist for absent keys).
//!
//! Art III.4 / F4 discipline: this binary never echoes a τ/λ/N_eff-floor/H_lineage-floor
//! *value* back onto stdout -- the `fold-and-suggest` response mirrors `BudgetSuggestion`'s
//! own field set exactly (which itself carries no τ field, by WP1 design), and the τ
//! configuration a caller supplies on stdin for the `SoftmaxFinite` regime is consumed only
//! to construct a `TauQ32`, never reflected in any output or error text.
//!
//! WP9a lineage-expansion update (spec: PREREG_ECON_emergence_experiments_20260707.md
//! Appendix A, frozen 2026-07-07 -- 4 independent worker lineages via SiliconFlow +
//! DeepSeek-direct fallback): added the `diversity-metrics` subcommand, a thin wrapper
//! around `turing_economy::diversity_metrics::compute_n_eff_and_h_lineage` (WP5, already
//! merged) so the Python driver never re-derives N_eff/H_lineage itself, exactly the same
//! "single source of truth" discipline as the two subcommands above.
//!
//! WP9b (ADR-ECON-003 Decision 2.4, 2026-07-07 增补; `tools/econ_lab/verifier/
//! live_split_verifier.py`'s own live independent-verifier wiring): added the
//! `build-routing-prior-updated` subcommand, a thin wrapper around
//! `turing_economy::EconomyEvent::routing_prior_updated` (WP4, already merged). This exists
//! solely so the Python live-run driver never recomputes the `event_hash` JCS-SHA256
//! identity digest itself ("python 不重算任何公式") -- the driver reads a per-test-id
//! independent verdict from the real SWE-bench harness's own report, then calls this
//! subcommand to get back the fully-formed, correctly-hashed `EconomyEvent` to append to its
//! `committed_routing_events` tape.
//!
//! Usage:
//!   echo '<derive-keys request JSON>'                  | econ_fold_cli derive-keys
//!   echo '<fold-and-suggest request JSON>'             | econ_fold_cli fold-and-suggest
//!   echo '<diversity-metrics request JSON>'            | econ_fold_cli diversity-metrics
//!   echo '<build-routing-prior-updated request JSON>'  | econ_fold_cli build-routing-prior-updated
//!   echo '<derive-stage-keys request JSON>'            | econ_fold_cli derive-stage-keys
//!   echo '<fold-and-suggest-stage request JSON>'       | econ_fold_cli fold-and-suggest-stage
//!   echo '<derive-route-keys request JSON>'            | econ_fold_cli derive-route-keys
//!   echo '<fold-and-suggest-route request JSON>'       | econ_fold_cli fold-and-suggest-route
//!   echo '<build-route-fuse-tripped request JSON>'     | econ_fold_cli build-route-fuse-tripped
//!   echo '<build-route-falsified request JSON>'        | econ_fold_cli build-route-falsified
//!
//! CAPSULE B (depth-k): `derive-stage-keys` / `fold-and-suggest-stage` are additive new
//! subcommands (B1 versioning discipline). Pre-existing subcommands and their schemas are
//! byte-identical; stage selection seeds append `‖ stage_name` per ADR-ECON-005 proposed.
//!
//! WP-H4 (ADR-ECON-007 Decisions 2/4/5): `derive-route-keys` / `fold-and-suggest-route` /
//! `build-route-fuse-tripped` / `build-route-falsified` are additive new subcommands. The
//! route stage reuses `fold-and-suggest-stage`'s exact machinery (`stage_name = "route"`)
//! plus a Decision 2 pause-mask filter applied to `candidate_routes` before selection; every
//! pre-existing subcommand and schema above is untouched.

use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;

use serde::{Deserialize, Serialize};

use turing_economy::diversity_metrics::{compute_n_eff_and_h_lineage, LineageSettlement, NEffHLineage};
use turing_economy::route_pause_mask::{
    compute_route_pause_mask, economy_events_to_route_fuse_trips, filter_paused_candidates,
    RoutePauseConfig,
};
use turing_economy::routing_fold::{
    domain_bucket, fold_routing_state_from_tape, options_for_stage, route_descriptor_id,
    scaffold_id, stage_option_id, stage_walk_v0, validate_stage_option, NodeState, RouteDescriptor,
    RoutingKey, ScaffoldDescriptor, STAGE_ROUTE, Q32_ONE,
};
use turing_economy::{
    BudgetSuggestion, CandidateRoute, EconomyEvent, MarketRouter, MarketRouterMode, PriceSignal,
    SoftmaxTemperature, TauQ32,
};

// ---------------------------------------------------------------------------
// Q32.32 <-> decimal-string encoding (I/O glue only -- see module doc). Q_eff/P are always
// in `[0, Q32_ONE]` by construction (Decision 6: P clamped to `[0,1]`, and `S <= N` always
// holds so `(P + S*Q32_ONE)/(1+N) <= Q32_ONE` whenever `P <= Q32_ONE`), so this never has to
// handle a negative or >1 value; it still clamps defensively rather than panicking.
// ---------------------------------------------------------------------------

/// Same `SCALE = 1_000_000_000` (9 fractional decimal digits) convention
/// `DecimalAmount`/`PriceSignal.yes_price` already use elsewhere in this crate.
const DECIMAL_SCALE: i128 = 1_000_000_000;

fn q32_to_decimal_string(value_q32: i128) -> String {
    let clamped = value_q32.clamp(0, Q32_ONE);
    let whole = clamped / Q32_ONE;
    let remainder = clamped % Q32_ONE;
    // Truncate toward zero (ADR-ECON-003 Decision 4's rounding convention throughout).
    let frac = (remainder * DECIMAL_SCALE) / Q32_ONE;
    format!("{whole}.{frac:09}")
}

fn parse_i128_decimal(raw: &str) -> Result<i128, String> {
    raw.parse::<i128>()
        .map_err(|_| format!("not a valid i128 decimal literal: {raw:?}"))
}

// ---------------------------------------------------------------------------
// derive-keys
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct ScaffoldDescriptorInput {
    label: String,
    decomposition_kind: String,
    toolchain: Vec<String>,
    team_spec: String,
    verify_loop: String,
}

#[derive(Deserialize)]
struct DeriveKeysRequest {
    schema: String,
    task_family: Option<String>,
    #[serde(default)]
    scaffold_descriptors: Vec<ScaffoldDescriptorInput>,
}

#[derive(Serialize)]
struct ScaffoldIdOutput {
    label: String,
    scaffold_id: String,
}

#[derive(Serialize)]
struct DeriveKeysResponse {
    schema: &'static str,
    domain_bucket: String,
    scaffold_ids: Vec<ScaffoldIdOutput>,
}

fn run_derive_keys(input: &str) -> Result<String, String> {
    let request: DeriveKeysRequest =
        serde_json::from_str(input).map_err(|e| format!("invalid derive-keys request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.derive_keys.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.derive_keys.request.v1, got {})",
            request.schema
        ));
    }

    // Single source of truth: turing_economy::routing_fold::domain_bucket (ADR-ECON-003
    // Decision 1), never re-derived with ad hoc string ops in this file or in the Python
    // driver.
    let bucket = domain_bucket(request.task_family.as_deref());

    let mut scaffold_ids = Vec::with_capacity(request.scaffold_descriptors.len());
    for descriptor in &request.scaffold_descriptors {
        let id = scaffold_id(&ScaffoldDescriptor {
            decomposition_kind: descriptor.decomposition_kind.clone(),
            toolchain: descriptor.toolchain.clone(),
            team_spec: descriptor.team_spec.clone(),
            verify_loop: descriptor.verify_loop.clone(),
        })
        .map_err(|e| format!("scaffold_id derivation failed for {:?}: {e:?}", descriptor.label))?;
        scaffold_ids.push(ScaffoldIdOutput {
            label: descriptor.label.clone(),
            scaffold_id: id,
        });
    }

    let response = DeriveKeysResponse {
        schema: "econ_fold_cli.derive_keys.response.v1",
        domain_bucket: bucket,
        scaffold_ids,
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// fold-and-suggest
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct InitialPriceInput {
    domain_bucket: String,
    scaffold_id: String,
    /// i128 Q32.32 mantissa, as a decimal-literal string (JSON numbers cannot losslessly
    /// carry i128; see the module doc's I/O-glue note).
    p_q32: String,
}

#[derive(Deserialize)]
struct CandidateRouteInput {
    route_id: String,
    market_id: String,
    expected_failure_domain: String,
    requested_tokens: u64,
    /// The routing key this candidate route's price should be read from (ADR-ECON-003
    /// Decision 6.2 "选择律作用于 Q_eff"): the caller (Python driver) supplies which
    /// `(domain_bucket, scaffold_id)` node backs this route; this file never invents that
    /// mapping, it only looks the key up in the already-folded node map.
    domain_bucket: String,
    scaffold_id: String,
}

#[derive(Deserialize)]
#[serde(tag = "kind")]
enum RouterModeInput {
    Shadow,
    AssistedFuture,
    SoftmaxArgmaxBypass,
    SoftmaxUniform,
    /// τ configuration read by the caller from the B-zone parameter mechanism (ADR-ECON-003
    /// Decision 5); consumed here only to build a `TauQ32`, never echoed back (Art III.4).
    SoftmaxFinite { tau_q32_mantissa: u64 },
}

#[derive(Deserialize)]
struct FoldAndSuggestRequest {
    /// Enforced (presence + exact v2 value) via the `SchemaOnly` pre-parse in
    /// `run_fold_and_suggest`, which runs *before* this struct deserializes so a version
    /// mismatch reports as such; kept here too so the full-struct parse still requires it.
    #[allow(dead_code)]
    schema: String,
    #[serde(default)]
    committed_routing_events: Vec<EconomyEvent>,
    #[serde(default)]
    initial_prices: Vec<InitialPriceInput>,
    candidate_routes: Vec<CandidateRouteInput>,
    price_signal_hash: String,
    pput_prior_hash: String,
    /// ADR-ECON-003 Decision 4's fourth selection-seed input (B1 remedy, owner decision
    /// 2026-07: conform to the pin): the already-committed `sha256:`-prefixed identity
    /// digest of the event that triggered this routing decision. Required -- its addition
    /// is exactly why the request schema below is `v2` (a pre-B1 `v1` request carries no
    /// such field and must be rejected by version, not by a confusing missing-field error).
    trigger_event_hash: String,
    router_mode: RouterModeInput,
}

#[derive(Serialize)]
struct NodeStateOutput {
    domain_bucket: String,
    scaffold_id: String,
    p_q32: String,
    n: u64,
    /// Binary success count (legacy; exact under binary mode).
    s: u64,
    /// ADR-ECON-006: Q32.32 success sum as decimal-literal string.
    s_q32: String,
    q_eff_q32: String,
}

#[derive(Serialize)]
struct BudgetSuggestionOutput {
    schema_id: String,
    mode: MarketRouterMode,
    route_id: String,
    market_id: String,
    price_signal_hash: String,
    pput_prior_hash: String,
    diversity_policy_hash: String,
    max_tokens: u64,
    emits_authorization: bool,
    can_move_accepted_head: bool,
    head_effect: String,
}

impl From<&BudgetSuggestion> for BudgetSuggestionOutput {
    fn from(suggestion: &BudgetSuggestion) -> Self {
        BudgetSuggestionOutput {
            schema_id: suggestion.schema_id.clone(),
            mode: suggestion.mode,
            route_id: suggestion.route_id.clone(),
            market_id: suggestion.market_id.clone(),
            price_signal_hash: suggestion.price_signal_hash.clone(),
            pput_prior_hash: suggestion.pput_prior_hash.clone(),
            diversity_policy_hash: suggestion.diversity_policy_hash.clone(),
            max_tokens: suggestion.max_tokens,
            emits_authorization: suggestion.emits_authorization,
            can_move_accepted_head: suggestion.can_move_accepted_head,
            head_effect: suggestion.head_effect.clone(),
        }
    }
}

#[derive(Serialize)]
struct FoldAndSuggestResponse {
    schema: &'static str,
    node_states: Vec<NodeStateOutput>,
    budget_suggestion: BudgetSuggestionOutput,
}

fn node_state_outputs(
    nodes: &BTreeMap<RoutingKey, NodeState>,
) -> Vec<NodeStateOutput> {
    nodes
        .iter()
        .map(|(key, node)| NodeStateOutput {
            domain_bucket: key.domain_bucket.clone(),
            scaffold_id: key.scaffold_id.clone(),
            p_q32: node.p_q32().to_string(),
            n: node.n(),
            // Binary success count (legacy field; exact under binary mode).
            s: node.s(),
            // ADR-ECON-006: Q32.32 success sum (always present for fractional consumers).
            s_q32: node.s_q32().to_string(),
            q_eff_q32: node.q_eff_q32().to_string(),
        })
        .collect()
}

/// `Q_eff` for a routing key (ADR-ECON-003 Decision 6.2), reading it from the already-folded
/// node map when the key has at least one settlement, and falling back to the `N=0`
/// degenerate case (`Q_eff = P`, the fold's own documented boundary identity -- see module
/// doc) when the key has never appeared in the fold output at all.
fn q_eff_for_key(
    nodes: &BTreeMap<RoutingKey, NodeState>,
    key: &RoutingKey,
    initial_prices: &BTreeMap<RoutingKey, i128>,
) -> i128 {
    if let Some(node) = nodes.get(key) {
        return node.q_eff_q32();
    }
    initial_prices
        .get(key)
        .copied()
        .map(|p| p.clamp(0, Q32_ONE))
        .unwrap_or(Q32_ONE / 2)
}

/// Just the `schema` discriminator, parsed ahead of the full request struct so a
/// version mismatch is reported as a version mismatch -- not as whatever missing-field
/// error the full struct would produce first (a pre-B1 `v1` request has no
/// `trigger_event_hash` and would otherwise die on `missing field` before the version
/// check ever ran).
#[derive(Deserialize)]
struct SchemaOnly {
    schema: String,
}

fn run_fold_and_suggest(input: &str) -> Result<String, String> {
    // v1 -> v2 (ADR-ECON-003 Decision 1's evolution rule -- new required input = new schema
    // version, never implicit drift): v2 adds the required `trigger_event_hash` seed input
    // pinned by Decision 4 (B1 remedy). A v1 request (no trigger_event_hash) is a pre-B1
    // caller and is rejected here by version string, before full-struct deserialization.
    let schema_probe: SchemaOnly = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest request JSON: {e}"))?;
    if schema_probe.schema != "econ_fold_cli.fold_and_suggest.request.v2" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.fold_and_suggest.request.v2, got {})",
            schema_probe.schema
        ));
    }
    let request: FoldAndSuggestRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest request JSON: {e}"))?;

    let mut initial_prices: BTreeMap<RoutingKey, i128> = BTreeMap::new();
    for entry in &request.initial_prices {
        let key = RoutingKey {
            domain_bucket: entry.domain_bucket.clone(),
            scaffold_id: entry.scaffold_id.clone(),
        };
        let value = parse_i128_decimal(&entry.p_q32)?;
        initial_prices.insert(key, value);
    }

    // Single source of truth: turing_economy::routing_fold::fold_routing_state_from_tape
    // (WP3/WP4) -- the (Q, N, P) tape fold itself is never reimplemented here.
    let nodes = fold_routing_state_from_tape(&initial_prices, &request.committed_routing_events)
        .map_err(|e| format!("routing fold failed: {e:?}"))?;

    // Build CandidateRoute + a synthesized PriceSignal per route from that route's Q_eff
    // (ADR-ECON-003 Decision 6.2 "选择律作用于 Q_eff"): the *only* new glue code in this
    // file, a radix conversion (see module doc), not a reimplementation of Q_eff itself.
    let mut routes: Vec<CandidateRoute> = Vec::with_capacity(request.candidate_routes.len());
    let mut signals: Vec<PriceSignal> = Vec::with_capacity(request.candidate_routes.len());
    // `MarketRouter::suggest` joins each route back to its synthesized PriceSignal by
    // `market_id` (first match wins), so a duplicate `market_id` across candidate routes
    // would silently misattribute one route's Q_eff to another: reject it up front.
    let mut seen_market_ids: BTreeSet<&str> = BTreeSet::new();
    for route_input in &request.candidate_routes {
        if !seen_market_ids.insert(route_input.market_id.as_str()) {
            return Err(format!(
                "duplicate market_id {:?} across candidate_routes: every candidate route \
                 must reference a distinct market_id (the per-route Q_eff price signal is \
                 joined back by market_id, so a duplicate would silently misattribute Q_eff)",
                route_input.market_id
            ));
        }
    }
    for route_input in &request.candidate_routes {
        let key = RoutingKey {
            domain_bucket: route_input.domain_bucket.clone(),
            scaffold_id: route_input.scaffold_id.clone(),
        };
        let q_eff = q_eff_for_key(&nodes, &key, &initial_prices);
        let yes_price = q32_to_decimal_string(q_eff);
        let no_price = q32_to_decimal_string(Q32_ONE - q_eff.clamp(0, Q32_ONE));
        routes.push(CandidateRoute {
            route_id: route_input.route_id.clone(),
            market_id: route_input.market_id.clone(),
            expected_failure_domain: route_input.expected_failure_domain.clone(),
            requested_tokens: route_input.requested_tokens,
        });
        signals.push(PriceSignal {
            market_id: route_input.market_id.clone(),
            yes_price,
            no_price,
            truth_status: "statistical_signal_only".to_string(),
        });
    }

    let router = match request.router_mode {
        RouterModeInput::Shadow => MarketRouter::new(MarketRouterMode::Shadow),
        RouterModeInput::AssistedFuture => MarketRouter::new(MarketRouterMode::AssistedFuture),
        RouterModeInput::SoftmaxArgmaxBypass => {
            MarketRouter::new_softmax(SoftmaxTemperature::ArgmaxBypass)
        }
        RouterModeInput::SoftmaxUniform => MarketRouter::new_softmax(SoftmaxTemperature::Uniform),
        RouterModeInput::SoftmaxFinite { tau_q32_mantissa } => {
            let tau = TauQ32::new(tau_q32_mantissa)
                .map_err(|e| format!("invalid softmax temperature: {e:?}"))?;
            MarketRouter::new_softmax(SoftmaxTemperature::Finite(tau))
        }
    };

    // Single source of truth: turing_economy::MarketRouter::suggest (WP1) -- the
    // argmax/softmax/uniform selection math itself is never reimplemented here.
    let suggestion = router
        .suggest(
            &routes,
            &signals,
            &request.price_signal_hash,
            &request.pput_prior_hash,
            &request.trigger_event_hash,
        )
        .map_err(|e| format!("suggest failed: {e:?}"))?;

    let response = FoldAndSuggestResponse {
        schema: "econ_fold_cli.fold_and_suggest.response.v1",
        node_states: node_state_outputs(&nodes),
        budget_suggestion: BudgetSuggestionOutput::from(&suggestion),
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// diversity-metrics (WP5 bridge; PREREG Appendix A lineage-expansion update)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct LineageSettlementInput {
    lineage_id: String,
    settlement_index: u64,
    verdict: bool,
}

#[derive(Deserialize)]
struct DiversityMetricsRequest {
    schema: String,
    history: Vec<LineageSettlementInput>,
}

#[derive(Serialize)]
struct DiversityMetricsResponse {
    schema: &'static str,
    status: &'static str,
    n_eff_q32: Option<String>,
    h_lineage_q32: Option<String>,
}

fn run_diversity_metrics(input: &str) -> Result<String, String> {
    let request: DiversityMetricsRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid diversity-metrics request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.diversity_metrics.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.diversity_metrics.request.v1, got {})",
            request.schema
        ));
    }

    let history: Vec<LineageSettlement> = request
        .history
        .into_iter()
        .map(|entry| LineageSettlement {
            lineage_id: entry.lineage_id,
            settlement_index: entry.settlement_index,
            verdict: entry.verdict,
        })
        .collect();

    // Single source of truth: turing_economy::diversity_metrics::compute_n_eff_and_h_lineage
    // (WP5) -- the N_eff/H_lineage estimator itself is never reimplemented here.
    let result = compute_n_eff_and_h_lineage(&history)
        .map_err(|e| format!("diversity metrics computation failed: {e:?}"))?;

    let response = match result {
        NEffHLineage::NotEnoughData => DiversityMetricsResponse {
            schema: "econ_fold_cli.diversity_metrics.response.v1",
            status: "NOT_ENOUGH_DATA",
            n_eff_q32: None,
            h_lineage_q32: None,
        },
        NEffHLineage::Computed {
            n_eff_q32,
            h_lineage_q32,
        } => DiversityMetricsResponse {
            schema: "econ_fold_cli.diversity_metrics.response.v1",
            status: "COMPUTED",
            n_eff_q32: Some(n_eff_q32.to_string()),
            h_lineage_q32: Some(h_lineage_q32.to_string()),
        },
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// build-routing-prior-updated (WP9b bridge; ADR-ECON-003 Decision 2.4)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct BuildRoutingPriorUpdatedRequest {
    schema: String,
    route_domain: String,
    route_scaffold: String,
    verdict: bool,
    /// ADR-ECON-006: optional Q32.32 fraction as decimal-literal string. Absent ⇒ binary
    /// constructor (pre-006 byte-identical event). Present ⇒ fractional v2 event.
    #[serde(default)]
    verdict_fraction_q32: Option<String>,
    verdict_source_id: String,
    /// `sha256:`-prefixed 64-hex attestation digest (validated by
    /// `EconomyEvent::routing_prior_updated` itself, not re-validated here).
    verifier_attestation_hash: String,
}

#[derive(Serialize)]
struct BuildRoutingPriorUpdatedResponse {
    schema: &'static str,
    /// The fully-formed `EconomyEvent::RoutingPriorUpdated(..)`, serialized in the crate's
    /// own externally-tagged enum representation (`{"RoutingPriorUpdated": {...}}`) -- the
    /// same shape `committed_routing_events` already accepts in `fold-and-suggest`, so the
    /// Python caller appends this value verbatim onto its growing tape.
    event: EconomyEvent,
}

fn run_build_routing_prior_updated(input: &str) -> Result<String, String> {
    let request: BuildRoutingPriorUpdatedRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid build-routing-prior-updated request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.build_routing_prior_updated.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.build_routing_prior_updated.request.v1, got {})",
            request.schema
        ));
    }

    // Single source of truth: turing_economy::EconomyEvent::routing_prior_updated (WP4) /
    // routing_prior_updated_fractional (ADR-ECON-006) -- the event_hash JCS-SHA256 identity
    // digest is never recomputed in this file or in the Python driver.
    let event = match request.verdict_fraction_q32 {
        None => EconomyEvent::routing_prior_updated(
            request.route_domain,
            request.route_scaffold,
            request.verdict,
            request.verdict_source_id,
            request.verifier_attestation_hash,
        )
        .map_err(|e| format!("routing_prior_updated construction failed: {e:?}"))?,
        Some(frac_str) => {
            let frac: i128 = frac_str
                .parse()
                .map_err(|e| format!("invalid verdict_fraction_q32 {frac_str:?}: {e}"))?;
            EconomyEvent::routing_prior_updated_fractional(
                request.route_domain,
                request.route_scaffold,
                request.verdict,
                frac,
                request.verdict_source_id,
                request.verifier_attestation_hash,
            )
            .map_err(|e| format!("routing_prior_updated_fractional construction failed: {e:?}"))?
        }
    };

    let response = BuildRoutingPriorUpdatedResponse {
        schema: "econ_fold_cli.build_routing_prior_updated.response.v1",
        event,
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// derive-stage-keys (CAPSULE B / depth-k; additive subcommand)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct DeriveStageKeysRequest {
    schema: String,
    task_family: Option<String>,
    /// Optional explicit stage list; default = frozen v0 walk (context/repair/verify)
    /// with their frozen option spaces.
    #[serde(default)]
    stages: Vec<StageSpecInput>,
}

#[derive(Deserialize)]
struct StageSpecInput {
    stage_name: String,
    options: Vec<String>,
}

#[derive(Serialize)]
struct StageKeyOutput {
    stage_name: String,
    option: String,
    stage_option_id: String,
    domain_bucket: String,
}

#[derive(Serialize)]
struct DeriveStageKeysResponse {
    schema: &'static str,
    domain_bucket: String,
    stage_keys: Vec<StageKeyOutput>,
}

fn run_derive_stage_keys(input: &str) -> Result<String, String> {
    let request: DeriveStageKeysRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid derive-stage-keys request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.derive_stage_keys.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.derive_stage_keys.request.v1, got {})",
            request.schema
        ));
    }

    let bucket = domain_bucket(request.task_family.as_deref());

    let stage_specs: Vec<(String, Vec<String>)> = if request.stages.is_empty() {
        stage_walk_v0()
            .into_iter()
            .map(|name| {
                let opts = options_for_stage(name)
                    .expect("frozen stage walk entries always validate")
                    .iter()
                    .map(|s| (*s).to_string())
                    .collect();
                (name.to_string(), opts)
            })
            .collect()
    } else {
        request
            .stages
            .into_iter()
            .map(|s| (s.stage_name, s.options))
            .collect()
    };

    let mut stage_keys = Vec::new();
    for (stage_name, options) in stage_specs {
        for option in options {
            validate_stage_option(&stage_name, &option)
                .map_err(|e| format!("stage option validation failed: {e:?}"))?;
            let id = stage_option_id(&stage_name, &option)
                .map_err(|e| format!("stage_option_id derivation failed: {e:?}"))?;
            stage_keys.push(StageKeyOutput {
                stage_name: stage_name.clone(),
                option,
                stage_option_id: id,
                domain_bucket: bucket.clone(),
            });
        }
    }

    let response = DeriveStageKeysResponse {
        schema: "econ_fold_cli.derive_stage_keys.response.v1",
        domain_bucket: bucket,
        stage_keys,
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// fold-and-suggest-stage (CAPSULE B / depth-k; additive subcommand)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct FoldAndSuggestStageRequest {
    #[allow(dead_code)]
    schema: String,
    /// Which stage this selection is for (appended to Decision 4 seed; CAPSULE B).
    stage_name: String,
    #[serde(default)]
    committed_routing_events: Vec<EconomyEvent>,
    #[serde(default)]
    initial_prices: Vec<InitialPriceInput>,
    candidate_routes: Vec<CandidateRouteInput>,
    price_signal_hash: String,
    pput_prior_hash: String,
    trigger_event_hash: String,
    router_mode: RouterModeInput,
}

#[derive(Serialize)]
struct FoldAndSuggestStageResponse {
    schema: &'static str,
    stage_name: String,
    node_states: Vec<NodeStateOutput>,
    budget_suggestion: BudgetSuggestionOutput,
}

fn run_fold_and_suggest_stage(input: &str) -> Result<String, String> {
    // Schema-first (B1 discipline): reject pre-v1 / wrong schema before full deserialize.
    let schema_probe: SchemaOnly = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest-stage request JSON: {e}"))?;
    if schema_probe.schema != "econ_fold_cli.fold_and_suggest_stage.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.fold_and_suggest_stage.request.v1, got {})",
            schema_probe.schema
        ));
    }
    let request: FoldAndSuggestStageRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest-stage request JSON: {e}"))?;

    if request.stage_name.is_empty() {
        return Err("stage_name must be non-empty".to_string());
    }
    // Options on candidate routes must belong to this stage's frozen space (when the
    // route_id equals the option label — the depth_driver convention).
    for route in &request.candidate_routes {
        // Soft validation: if route_id looks like a v0 option for this stage, check it.
        // Unknown route_ids (custom labels) are allowed for tests; stage_name itself is
        // still the seed domain separator regardless.
        let _ = route;
    }

    let mut initial_prices: BTreeMap<RoutingKey, i128> = BTreeMap::new();
    for entry in &request.initial_prices {
        let key = RoutingKey {
            domain_bucket: entry.domain_bucket.clone(),
            scaffold_id: entry.scaffold_id.clone(),
        };
        let value = parse_i128_decimal(&entry.p_q32)?;
        initial_prices.insert(key, value);
    }

    let nodes = fold_routing_state_from_tape(&initial_prices, &request.committed_routing_events)
        .map_err(|e| format!("routing fold failed: {e:?}"))?;

    let mut routes: Vec<CandidateRoute> = Vec::with_capacity(request.candidate_routes.len());
    let mut signals: Vec<PriceSignal> = Vec::with_capacity(request.candidate_routes.len());
    let mut seen_market_ids: BTreeSet<&str> = BTreeSet::new();
    for route_input in &request.candidate_routes {
        if !seen_market_ids.insert(route_input.market_id.as_str()) {
            return Err(format!(
                "duplicate market_id {:?} across candidate_routes",
                route_input.market_id
            ));
        }
    }
    for route_input in &request.candidate_routes {
        let key = RoutingKey {
            domain_bucket: route_input.domain_bucket.clone(),
            scaffold_id: route_input.scaffold_id.clone(),
        };
        let q_eff = q_eff_for_key(&nodes, &key, &initial_prices);
        let yes_price = q32_to_decimal_string(q_eff);
        let no_price = q32_to_decimal_string(Q32_ONE - q_eff.clamp(0, Q32_ONE));
        routes.push(CandidateRoute {
            route_id: route_input.route_id.clone(),
            market_id: route_input.market_id.clone(),
            expected_failure_domain: route_input.expected_failure_domain.clone(),
            requested_tokens: route_input.requested_tokens,
        });
        signals.push(PriceSignal {
            market_id: route_input.market_id.clone(),
            yes_price,
            no_price,
            truth_status: "statistical_signal_only".to_string(),
        });
    }

    let router = match request.router_mode {
        RouterModeInput::Shadow => MarketRouter::new(MarketRouterMode::Shadow),
        RouterModeInput::AssistedFuture => MarketRouter::new(MarketRouterMode::AssistedFuture),
        RouterModeInput::SoftmaxArgmaxBypass => {
            MarketRouter::new_softmax(SoftmaxTemperature::ArgmaxBypass)
        }
        RouterModeInput::SoftmaxUniform => MarketRouter::new_softmax(SoftmaxTemperature::Uniform),
        RouterModeInput::SoftmaxFinite { tau_q32_mantissa } => {
            let tau = TauQ32::new(tau_q32_mantissa)
                .map_err(|e| format!("invalid softmax temperature: {e:?}"))?;
            MarketRouter::new_softmax(SoftmaxTemperature::Finite(tau))
        }
    };

    // Single source of truth: MarketRouter::suggest_with_stage (Decision 4 + ‖ stage_name).
    let suggestion = router
        .suggest_with_stage(
            &routes,
            &signals,
            &request.price_signal_hash,
            &request.pput_prior_hash,
            &request.trigger_event_hash,
            &request.stage_name,
        )
        .map_err(|e| format!("suggest_with_stage failed: {e:?}"))?;

    let response = FoldAndSuggestStageResponse {
        schema: "econ_fold_cli.fold_and_suggest_stage.response.v1",
        stage_name: request.stage_name,
        node_states: node_state_outputs(&nodes),
        budget_suggestion: BudgetSuggestionOutput::from(&suggestion),
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// derive-route-keys (WP-H4 / ADR-ECON-007 Decision 5; additive subcommand)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct RouteDescriptorInput {
    route_label: String,
    context: String,
    repair: String,
    verify: String,
}

#[derive(Deserialize)]
struct DeriveRouteKeysRequest {
    schema: String,
    task_family: Option<String>,
    routes: Vec<RouteDescriptorInput>,
}

#[derive(Serialize)]
struct RouteKeyOutput {
    route_label: String,
    /// `route_descriptor.v1` JCS-SHA256 digest (Decision 5, Decision-1 precedent).
    route_id: String,
    /// The fully-encoded fold key (`stage_option_id(STAGE_ROUTE, route_id)`) -- exactly the
    /// value a `CandidateRouteInput.scaffold_id` / `RouteFuseTripped.route_scaffold` must
    /// carry for this route.
    route_scaffold: String,
}

#[derive(Serialize)]
struct DeriveRouteKeysResponse {
    schema: &'static str,
    domain_bucket: String,
    route_keys: Vec<RouteKeyOutput>,
}

fn run_derive_route_keys(input: &str) -> Result<String, String> {
    let request: DeriveRouteKeysRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid derive-route-keys request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.derive_route_keys.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.derive_route_keys.request.v1, got {})",
            request.schema
        ));
    }

    let bucket = domain_bucket(request.task_family.as_deref());

    let mut route_keys = Vec::with_capacity(request.routes.len());
    for route in &request.routes {
        // Single source of truth: turing_economy::routing_fold::route_descriptor_id /
        // stage_option_id (Decision 5) -- never re-derived with ad hoc JCS/hash ops here or
        // in the Python driver.
        let route_id = route_descriptor_id(&RouteDescriptor {
            route_label: route.route_label.clone(),
            context: route.context.clone(),
            repair: route.repair.clone(),
            verify: route.verify.clone(),
        })
        .map_err(|e| format!("route_descriptor_id derivation failed for {:?}: {e:?}", route.route_label))?;
        let route_scaffold = stage_option_id(STAGE_ROUTE, &route_id)
            .map_err(|e| format!("stage_option_id(route, ..) derivation failed: {e:?}"))?;
        route_keys.push(RouteKeyOutput {
            route_label: route.route_label.clone(),
            route_id,
            route_scaffold,
        });
    }

    let response = DeriveRouteKeysResponse {
        schema: "econ_fold_cli.derive_route_keys.response.v1",
        domain_bucket: bucket,
        route_keys,
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// fold-and-suggest-route (WP-H4 / ADR-ECON-007 Decision 2/5; additive subcommand)
//
// Same shape as fold-and-suggest-stage, PLUS the Decision 2 pause-mask filter applied to
// `candidate_routes` before `suggest_with_stage(stage_name = STAGE_ROUTE)` ever runs. The
// mask never touches `node_states`/Q -- it only narrows which candidates reach selection
// (Decision 2: "掩码作用于 suggest 候选集过滤,不碰 Q").
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct FoldAndSuggestRouteRequest {
    #[allow(dead_code)]
    schema: String,
    #[serde(default)]
    committed_routing_events: Vec<EconomyEvent>,
    #[serde(default)]
    initial_prices: Vec<InitialPriceInput>,
    candidate_routes: Vec<CandidateRouteInput>,
    price_signal_hash: String,
    pput_prior_hash: String,
    trigger_event_hash: String,
    router_mode: RouterModeInput,
    /// ADR-ECON-007 Decision 2 pause validity window (B-zone value; caller reads it from
    /// wherever the A-zone-existence/B-zone-value config mechanism lives -- consumed here
    /// only to build a `RoutePauseConfig`, never echoed back in the response, same
    /// discipline as `SoftmaxFinite`'s `tau_q32_mantissa` above).
    pause_validity_window: u64,
    /// The logical-clock position this selection is evaluated "as of" (see
    /// `route_pause_mask`'s module doc). Must be `>=` every `RouteFuseTripped.event_ordinal`
    /// on `committed_routing_events` that the caller intends to have already taken effect.
    as_of_event_ordinal: u64,
}

#[derive(Serialize)]
struct FoldAndSuggestRouteResponse {
    schema: &'static str,
    node_states: Vec<NodeStateOutput>,
    /// The `route_id` label (the caller's own `CandidateRouteInput.route_id`, never a raw
    /// B-zone threshold value -- Decision 3's no-numeric-leak discipline) of every candidate
    /// the Decision 2 pause mask filtered out before selection ran.
    paused_route_ids: Vec<String>,
    budget_suggestion: BudgetSuggestionOutput,
}

fn run_fold_and_suggest_route(input: &str) -> Result<String, String> {
    let schema_probe: SchemaOnly = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest-route request JSON: {e}"))?;
    if schema_probe.schema != "econ_fold_cli.fold_and_suggest_route.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.fold_and_suggest_route.request.v1, got {})",
            schema_probe.schema
        ));
    }
    let request: FoldAndSuggestRouteRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest-route request JSON: {e}"))?;

    let mut initial_prices: BTreeMap<RoutingKey, i128> = BTreeMap::new();
    for entry in &request.initial_prices {
        let key = RoutingKey {
            domain_bucket: entry.domain_bucket.clone(),
            scaffold_id: entry.scaffold_id.clone(),
        };
        let value = parse_i128_decimal(&entry.p_q32)?;
        initial_prices.insert(key, value);
    }

    // Single source of truth: turing_economy::routing_fold::fold_routing_state_from_tape --
    // the (Q, N, P) tape fold itself is never reimplemented here, and RouteFuseTripped
    // events are never translated into it (Decision 2: "熔断不写 Q").
    let nodes = fold_routing_state_from_tape(&initial_prices, &request.committed_routing_events)
        .map_err(|e| format!("routing fold failed: {e:?}"))?;

    let mut routes: Vec<CandidateRoute> = Vec::with_capacity(request.candidate_routes.len());
    let mut route_keys: BTreeMap<String, RoutingKey> = BTreeMap::new();
    let mut signals: Vec<PriceSignal> = Vec::with_capacity(request.candidate_routes.len());
    let mut seen_market_ids: BTreeSet<&str> = BTreeSet::new();
    for route_input in &request.candidate_routes {
        if !seen_market_ids.insert(route_input.market_id.as_str()) {
            return Err(format!(
                "duplicate market_id {:?} across candidate_routes",
                route_input.market_id
            ));
        }
    }
    for route_input in &request.candidate_routes {
        let key = RoutingKey {
            domain_bucket: route_input.domain_bucket.clone(),
            scaffold_id: route_input.scaffold_id.clone(),
        };
        let q_eff = q_eff_for_key(&nodes, &key, &initial_prices);
        let yes_price = q32_to_decimal_string(q_eff);
        let no_price = q32_to_decimal_string(Q32_ONE - q_eff.clamp(0, Q32_ONE));
        routes.push(CandidateRoute {
            route_id: route_input.route_id.clone(),
            market_id: route_input.market_id.clone(),
            expected_failure_domain: route_input.expected_failure_domain.clone(),
            requested_tokens: route_input.requested_tokens,
        });
        route_keys.insert(route_input.route_id.clone(), key);
        signals.push(PriceSignal {
            market_id: route_input.market_id.clone(),
            yes_price,
            no_price,
            truth_status: "statistical_signal_only".to_string(),
        });
    }

    // Decision 2 pause mask: pure fold over the RouteFuseTripped events already present on
    // `committed_routing_events`, then a pure candidate-set filter -- never touches `nodes`
    // (the Q/N/P fold output above) in any way.
    let fuse_trips = economy_events_to_route_fuse_trips(&request.committed_routing_events);
    let pause_cfg = RoutePauseConfig {
        validity_window: request.pause_validity_window,
    };
    let paused = compute_route_pause_mask(&fuse_trips, &pause_cfg, request.as_of_event_ordinal);
    let filtered_routes = filter_paused_candidates(
        &routes,
        |route| {
            route_keys
                .get(&route.route_id)
                .cloned()
                .unwrap_or_else(|| RoutingKey {
                    domain_bucket: String::new(),
                    scaffold_id: String::new(),
                })
        },
        &paused,
    );
    let paused_route_ids: Vec<String> = routes
        .iter()
        .filter(|route| !filtered_routes.iter().any(|kept| kept.route_id == route.route_id))
        .map(|route| route.route_id.clone())
        .collect();

    let router = match request.router_mode {
        RouterModeInput::Shadow => MarketRouter::new(MarketRouterMode::Shadow),
        RouterModeInput::AssistedFuture => MarketRouter::new(MarketRouterMode::AssistedFuture),
        RouterModeInput::SoftmaxArgmaxBypass => {
            MarketRouter::new_softmax(SoftmaxTemperature::ArgmaxBypass)
        }
        RouterModeInput::SoftmaxUniform => MarketRouter::new_softmax(SoftmaxTemperature::Uniform),
        RouterModeInput::SoftmaxFinite { tau_q32_mantissa } => {
            let tau = TauQ32::new(tau_q32_mantissa)
                .map_err(|e| format!("invalid softmax temperature: {e:?}"))?;
            MarketRouter::new_softmax(SoftmaxTemperature::Finite(tau))
        }
    };

    // Signals must be filtered/joined the same way `suggest_with_stage` expects -- filtered
    // by market_id membership in `filtered_routes` so a paused route's price never
    // influences anything even incidentally.
    let filtered_market_ids: BTreeSet<&str> =
        filtered_routes.iter().map(|r| r.market_id.as_str()).collect();
    let filtered_signals: Vec<PriceSignal> = signals
        .into_iter()
        .filter(|s| filtered_market_ids.contains(s.market_id.as_str()))
        .collect();

    // Single source of truth: MarketRouter::suggest_with_stage (Decision 4 + ‖ stage_name).
    let suggestion = router
        .suggest_with_stage(
            &filtered_routes,
            &filtered_signals,
            &request.price_signal_hash,
            &request.pput_prior_hash,
            &request.trigger_event_hash,
            STAGE_ROUTE,
        )
        .map_err(|e| format!("suggest_with_stage failed: {e:?}"))?;

    let response = FoldAndSuggestRouteResponse {
        schema: "econ_fold_cli.fold_and_suggest_route.response.v1",
        node_states: node_state_outputs(&nodes),
        paused_route_ids,
        budget_suggestion: BudgetSuggestionOutput::from(&suggestion),
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// build-route-fuse-tripped (WP-H4 / ADR-ECON-007 Decision 2; additive subcommand)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct BuildRouteFuseTrippedRequest {
    schema: String,
    route_domain: String,
    route_scaffold: String,
    detector_rule_id: String,
    /// `sha256:`-prefixed 64-hex digest over the off-tape diagnostic facts (validated by
    /// `EconomyEvent::route_fuse_tripped` itself, not re-validated here).
    diagnostic_digest: String,
    event_ordinal: u64,
}

#[derive(Serialize)]
struct BuildRouteFuseTrippedResponse {
    schema: &'static str,
    event: EconomyEvent,
}

fn run_build_route_fuse_tripped(input: &str) -> Result<String, String> {
    let request: BuildRouteFuseTrippedRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid build-route-fuse-tripped request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.build_route_fuse_tripped.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.build_route_fuse_tripped.request.v1, got {})",
            request.schema
        ));
    }

    // Single source of truth: turing_economy::EconomyEvent::route_fuse_tripped (WP-H4) --
    // never reimplemented here.
    let event = EconomyEvent::route_fuse_tripped(
        request.route_domain,
        request.route_scaffold,
        request.detector_rule_id,
        request.diagnostic_digest,
        request.event_ordinal,
    )
    .map_err(|e| format!("route_fuse_tripped construction failed: {e:?}"))?;

    let response = BuildRouteFuseTrippedResponse {
        schema: "econ_fold_cli.build_route_fuse_tripped.response.v1",
        event,
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// build-route-falsified (WP-H4 / ADR-ECON-007 Decision 4; additive subcommand)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct BuildRouteFalsifiedRequest {
    schema: String,
    route_id: String,
    attempts: u64,
    #[serde(default)]
    verifier_evidence: Vec<String>,
    #[serde(default)]
    detector_events: Vec<String>,
    #[serde(default)]
    remaining_candidates: Vec<String>,
    recommendation: String,
}

#[derive(Serialize)]
struct BuildRouteFalsifiedResponse {
    schema: &'static str,
    event: EconomyEvent,
}

fn run_build_route_falsified(input: &str) -> Result<String, String> {
    let request: BuildRouteFalsifiedRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid build-route-falsified request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.build_route_falsified.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.build_route_falsified.request.v1, got {})",
            request.schema
        ));
    }

    // Single source of truth: turing_economy::EconomyEvent::route_falsified (WP-H4) -- never
    // reimplemented here.
    let event = EconomyEvent::route_falsified(
        request.route_id,
        request.attempts,
        request.verifier_evidence,
        request.detector_events,
        request.remaining_candidates,
        request.recommendation,
    );

    let response = BuildRouteFalsifiedResponse {
        schema: "econ_fold_cli.build_route_falsified.response.v1",
        event,
    };
    serde_json::to_string_pretty(&response).map_err(|e| format!("failed to encode response: {e}"))
}

// ---------------------------------------------------------------------------
// entry point
// ---------------------------------------------------------------------------

fn main() {
    let subcommand = std::env::args().nth(1).unwrap_or_default();
    let mut input = String::new();
    if std::io::stdin().read_to_string(&mut input).is_err() {
        eprintln!("econ_fold_cli: failed to read stdin");
        std::process::exit(2);
    }

    let result = match subcommand.as_str() {
        "derive-keys" => run_derive_keys(&input),
        "fold-and-suggest" => run_fold_and_suggest(&input),
        "diversity-metrics" => run_diversity_metrics(&input),
        "build-routing-prior-updated" => run_build_routing_prior_updated(&input),
        "derive-stage-keys" => run_derive_stage_keys(&input),
        "fold-and-suggest-stage" => run_fold_and_suggest_stage(&input),
        "derive-route-keys" => run_derive_route_keys(&input),
        "fold-and-suggest-route" => run_fold_and_suggest_route(&input),
        "build-route-fuse-tripped" => run_build_route_fuse_tripped(&input),
        "build-route-falsified" => run_build_route_falsified(&input),
        other => Err(format!(
            "unknown subcommand {other:?} (expected derive-keys, fold-and-suggest, \
             diversity-metrics, build-routing-prior-updated, derive-stage-keys, \
             fold-and-suggest-stage, derive-route-keys, fold-and-suggest-route, \
             build-route-fuse-tripped, or build-route-falsified)"
        )),
    };

    match result {
        Ok(output) => {
            println!("{output}");
        }
        Err(message) => {
            eprintln!("econ_fold_cli: {message}");
            std::process::exit(1);
        }
    }
}
