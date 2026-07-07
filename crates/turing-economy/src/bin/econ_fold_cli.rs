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
//! Usage:
//!   echo '<derive-keys request JSON>'      | econ_fold_cli derive-keys
//!   echo '<fold-and-suggest request JSON>' | econ_fold_cli fold-and-suggest

use std::collections::BTreeMap;
use std::io::Read;

use serde::{Deserialize, Serialize};

use turing_economy::routing_fold::{
    domain_bucket, fold_routing_state_from_tape, scaffold_id, NodeState, RoutingKey,
    ScaffoldDescriptor, Q32_ONE,
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
    schema: String,
    #[serde(default)]
    committed_routing_events: Vec<EconomyEvent>,
    #[serde(default)]
    initial_prices: Vec<InitialPriceInput>,
    candidate_routes: Vec<CandidateRouteInput>,
    price_signal_hash: String,
    pput_prior_hash: String,
    router_mode: RouterModeInput,
}

#[derive(Serialize)]
struct NodeStateOutput {
    domain_bucket: String,
    scaffold_id: String,
    p_q32: String,
    n: u64,
    s: u64,
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
            s: node.s(),
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

fn run_fold_and_suggest(input: &str) -> Result<String, String> {
    let request: FoldAndSuggestRequest = serde_json::from_str(input)
        .map_err(|e| format!("invalid fold-and-suggest request JSON: {e}"))?;
    if request.schema != "econ_fold_cli.fold_and_suggest.request.v1" {
        return Err(format!(
            "unrecognized request schema (expected econ_fold_cli.fold_and_suggest.request.v1, got {})",
            request.schema
        ));
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

    // Single source of truth: turing_economy::routing_fold::fold_routing_state_from_tape
    // (WP3/WP4) -- the (Q, N, P) tape fold itself is never reimplemented here.
    let nodes = fold_routing_state_from_tape(&initial_prices, &request.committed_routing_events)
        .map_err(|e| format!("routing fold failed: {e:?}"))?;

    // Build CandidateRoute + a synthesized PriceSignal per route from that route's Q_eff
    // (ADR-ECON-003 Decision 6.2 "选择律作用于 Q_eff"): the *only* new glue code in this
    // file, a radix conversion (see module doc), not a reimplementation of Q_eff itself.
    let mut routes: Vec<CandidateRoute> = Vec::with_capacity(request.candidate_routes.len());
    let mut signals: Vec<PriceSignal> = Vec::with_capacity(request.candidate_routes.len());
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
        .suggest(&routes, &signals, &request.price_signal_hash, &request.pput_prior_hash)
        .map_err(|e| format!("suggest failed: {e:?}"))?;

    let response = FoldAndSuggestResponse {
        schema: "econ_fold_cli.fold_and_suggest.response.v1",
        node_states: node_state_outputs(&nodes),
        budget_suggestion: BudgetSuggestionOutput::from(&suggestion),
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
        other => Err(format!(
            "unknown subcommand {other:?} (expected derive-keys or fold-and-suggest)"
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
