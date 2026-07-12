//! WP1 (ADR-ECON-003 / design doc R1.1 §1.2, §4 G1, §7): `MarketRouterMode::Softmax`
//! selection tests.
//!
//! Fixed-seed hand-rolled random loops per the capsule's no-proptest rule (no
//! `Math.random` / no time seed) -- same convention as `hunt_authority.rs`/`hunt_replay.rs`.
//!
//! Covers the two WP1 acceptance properties named in the work-package row:
//! 1. τ=0 (`SoftmaxTemperature::ArgmaxBypass`) is byte-for-byte equivalent to the
//!    pre-existing argmax selection on random fixtures.
//! 2. Repeated calls with identical input produce identical output (determinism), for both
//!    a finite τ and the τ=∞ uniform regime.

use turing_economy::{
    BudgetSuggestion, CandidateRoute, MarketRouter, MarketRouterMode, PriceSignal,
    SoftmaxTemperature, TauQ32,
};

struct Xorshift64(u64);

impl Xorshift64 {
    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }

    fn range(&mut self, lo: u64, hi_exclusive: u64) -> u64 {
        lo + self.next_u64() % (hi_exclusive - lo)
    }
}

const SEED: u64 = 0x0B0A_DA71_0000_0007u64; // fixed, distinct per-lens seed.

fn random_decimal_string(rng: &mut Xorshift64) -> String {
    let whole = rng.range(0, 1_000_000_000_000);
    let frac = rng.range(0, 1_000_000_000);
    format!("{whole}.{frac:09}")
}

fn random_fixture(
    rng: &mut Xorshift64,
    round: u64,
) -> (Vec<CandidateRoute>, Vec<PriceSignal>, String, String, String) {
    let route_count = rng.range(1, 6) as usize;
    let mut routes = Vec::with_capacity(route_count);
    let mut signals = Vec::with_capacity(route_count);
    for i in 0..route_count {
        let market_id = format!("mkt_{round}_{i}");
        routes.push(CandidateRoute {
            route_id: format!("route_{round}_{i}"),
            market_id: market_id.clone(),
            expected_failure_domain: "provider_x".to_string(),
            requested_tokens: rng.range(1, 1_000_000),
        });
        signals.push(PriceSignal {
            market_id,
            yes_price: random_decimal_string(rng),
            no_price: random_decimal_string(rng),
            truth_status: "statistical_signal_only".to_string(),
        });
    }
    let price_signal_hash = format!("sha256:{:064x}", rng.next_u64());
    let pput_prior_hash = format!("sha256:{:064x}", rng.next_u64());
    let trigger_event_hash = format!("sha256:{:064x}", rng.next_u64());
    (
        routes,
        signals,
        price_signal_hash,
        pput_prior_hash,
        trigger_event_hash,
    )
}

/// Every field of `BudgetSuggestion` *except* `mode` (which legitimately differs between a
/// `Shadow`/`AssistedFuture` argmax suggestion and a `Softmax`+`ArgmaxBypass` one -- the
/// mode label is not part of the "τ=0 argmax equivalence" property, only the selection
/// outcome and every other field the selection produces).
fn assert_selection_outcome_equal(a: &BudgetSuggestion, b: &BudgetSuggestion) {
    assert_eq!(a.schema_id, b.schema_id);
    assert_eq!(a.route_id, b.route_id);
    assert_eq!(a.market_id, b.market_id);
    assert_eq!(a.price_signal_hash, b.price_signal_hash);
    assert_eq!(a.pput_prior_hash, b.pput_prior_hash);
    assert_eq!(a.diversity_policy_hash, b.diversity_policy_hash);
    assert_eq!(a.max_tokens, b.max_tokens);
    assert_eq!(a.emits_authorization, b.emits_authorization);
    assert_eq!(a.can_move_accepted_head, b.can_move_accepted_head);
    assert_eq!(a.head_effect, b.head_effect);
}

/// WP1 acceptance property 1: "τ=0 与 argmax 在随机 fixture 上逐字节等价". Runs the exact
/// same random fixtures through `Shadow` (legacy argmax) and `Softmax` +
/// `SoftmaxTemperature::ArgmaxBypass` (τ=0) and asserts the selection outcome is identical
/// on every round (this is guaranteed by construction -- both paths call the same
/// `argmax_select` helper internally -- this test pins that guarantee at the public API).
#[test]
fn softmax_tau_zero_is_byte_for_byte_equivalent_to_argmax() {
    let mut rng = Xorshift64(SEED);
    let argmax_router = MarketRouter::new(MarketRouterMode::Shadow);
    let bypass_router = MarketRouter::new_softmax(SoftmaxTemperature::ArgmaxBypass);

    for round in 0..500u64 {
        let (routes, signals, price_signal_hash, pput_prior_hash, trigger_event_hash) =
            random_fixture(&mut rng, round);

        let argmax_suggestion = argmax_router
            .suggest(
                &routes,
                &signals,
                &price_signal_hash,
                &pput_prior_hash,
                &trigger_event_hash,
            )
            .expect("argmax suggest must succeed on well-formed inputs");
        let bypass_suggestion = bypass_router
            .suggest(
                &routes,
                &signals,
                &price_signal_hash,
                &pput_prior_hash,
                &trigger_event_hash,
            )
            .expect("softmax tau=0 suggest must succeed on well-formed inputs");

        assert_eq!(
            bypass_suggestion.mode,
            MarketRouterMode::Softmax,
            "iteration {round}: bypass router mode label must still read Softmax"
        );
        assert_selection_outcome_equal(&argmax_suggestion, &bypass_suggestion);
    }
}

/// WP1 acceptance property 2: "同输入双跑 suggestion 相等(确定性)". Repeats the identical
/// call twice for a finite τ and for τ=∞ (`Uniform`) and asserts full `BudgetSuggestion`
/// equality (Art 0.2: same committed inputs -> same tape-derivable bytes, no live-random
/// selection step).
#[test]
fn softmax_repeated_call_on_identical_input_is_deterministic() {
    let mut rng = Xorshift64(SEED ^ 0x51DE_0000_0000_0000);
    let finite_tau = TauQ32::new(1u64 << 30).expect("nonzero mantissa"); // test-only value
    let routers = [
        MarketRouter::new_softmax(SoftmaxTemperature::Finite(finite_tau)),
        MarketRouter::new_softmax(SoftmaxTemperature::Uniform),
    ];

    for router in routers {
        for round in 0..300u64 {
            let (routes, signals, price_signal_hash, pput_prior_hash, trigger_event_hash) =
                random_fixture(&mut rng, round);

            let first = router
                .suggest(
                    &routes,
                    &signals,
                    &price_signal_hash,
                    &pput_prior_hash,
                    &trigger_event_hash,
                )
                .expect("suggestion 1");
            let second = router
                .suggest(
                    &routes,
                    &signals,
                    &price_signal_hash,
                    &pput_prior_hash,
                    &trigger_event_hash,
                )
                .expect("suggestion 2");
            assert_eq!(
                first, second,
                "iteration {round}: Softmax MarketRouter::suggest is nondeterministic on \
                 identical input for mode={:?}",
                router.mode()
            );
        }
    }
}

/// Sanity check that the Softmax selection is not degenerately equivalent to picking the
/// first (or every-time-the-same) route regardless of `u` -- across many distinct fixtures
/// a finite-τ router must select more than one distinct `route_id` (otherwise the seed
/// derivation or inverse-CDF walk would be silently ignoring the sampled `u`).
#[test]
fn softmax_finite_tau_selects_more_than_one_route_across_fixtures() {
    let mut rng = Xorshift64(SEED ^ 0xF00D_0000_0000_0000);
    let finite_tau = TauQ32::new(1u64 << 32).expect("nonzero mantissa"); // test-only value
    let router = MarketRouter::new_softmax(SoftmaxTemperature::Finite(finite_tau));

    let mut distinct_selections = std::collections::BTreeSet::new();
    for round in 0..200u64 {
        let (routes, signals, price_signal_hash, pput_prior_hash, trigger_event_hash) =
            random_fixture(&mut rng, round);
        let suggestion = router
            .suggest(
                &routes,
                &signals,
                &price_signal_hash,
                &pput_prior_hash,
                &trigger_event_hash,
            )
            .expect("suggest must succeed");
        distinct_selections.insert(suggestion.route_id);
    }
    assert!(
        distinct_selections.len() > 1,
        "softmax selection never varied across 200 distinct fixtures -- looks degenerate"
    );
}

/// B1 remedy (ADR-ECON-003 Decision 4, INDEPENDENT_AUDIT_ECON_LAB_20260707.md): the
/// `trigger_event_hash` seed input must be load-bearing at the public API -- two suggestions
/// that differ ONLY in `trigger_event_hash` must select different routes on this fixture.
/// The two expected `route_id`s were computed with the Python reference
/// (`tools/econ_lab/selection.py`: `derive_u` + `select_uniform` over `sorted(route_ids)`)
/// for these exact literals, so this is also a cross-language selection-parity pin.
#[test]
fn uniform_selection_depends_on_trigger_event_hash_and_matches_python_reference() {
    let price_signal_hash =
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    let pput_prior_hash =
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    let trigger_1 = "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    let trigger_2 = "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";

    let routes: Vec<CandidateRoute> = ["route_a", "route_b", "route_c"]
        .iter()
        .enumerate()
        .map(|(i, route_id)| CandidateRoute {
            route_id: (*route_id).to_string(),
            market_id: format!("mkt_{i}"),
            expected_failure_domain: "provider_x".to_string(),
            requested_tokens: 100,
        })
        .collect();
    let signals: Vec<PriceSignal> = routes
        .iter()
        .map(|route| PriceSignal {
            market_id: route.market_id.clone(),
            yes_price: "0.5".to_string(),
            no_price: "0.5".to_string(),
            truth_status: "statistical_signal_only".to_string(),
        })
        .collect();

    let router = MarketRouter::new_softmax(SoftmaxTemperature::Uniform);
    let suggestion_1 = router
        .suggest(&routes, &signals, price_signal_hash, pput_prior_hash, trigger_1)
        .expect("suggest with trigger_1");
    let suggestion_2 = router
        .suggest(&routes, &signals, price_signal_hash, pput_prior_hash, trigger_2)
        .expect("suggest with trigger_2");

    // Known answers from the Python reference for these literals: u(trigger_1) ~= 0.50560
    // -> route_b, u(trigger_2) ~= 0.96587 -> route_c (uniform inverse-CDF over 3 sorted ids).
    assert_eq!(suggestion_1.route_id, "route_b");
    assert_eq!(suggestion_2.route_id, "route_c");
    assert_ne!(
        suggestion_1.route_id, suggestion_2.route_id,
        "trigger_event_hash must be a load-bearing seed input (ADR-ECON-003 Decision 4)"
    );
}
