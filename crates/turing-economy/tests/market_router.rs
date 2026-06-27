use turing_economy::{
    BudgetSuggestion, CandidateRoute, MarketRouter, MarketRouterMode, PriceBroadcast, PriceSignal,
};

#[test]
fn market_router_shadow_mode_suggests_without_authority() {
    let routes = vec![
        CandidateRoute {
            route_id: "route_high_price".to_string(),
            market_id: "mkt_demo".to_string(),
            expected_failure_domain: "provider_a".to_string(),
            requested_tokens: 2000,
        },
        CandidateRoute {
            route_id: "route_diverse".to_string(),
            market_id: "mkt_demo".to_string(),
            expected_failure_domain: "provider_b".to_string(),
            requested_tokens: 1000,
        },
    ];
    let signals = vec![PriceSignal {
        market_id: "mkt_demo".to_string(),
        yes_price: "0.73".to_string(),
        no_price: "0.27".to_string(),
        truth_status: "statistical_signal_only".to_string(),
    }];

    let suggestion: BudgetSuggestion = MarketRouter::new(MarketRouterMode::Shadow)
        .suggest(
            &routes,
            &signals,
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        .expect("shadow suggestion");

    assert_eq!(suggestion.schema_id, "budget_allocated.v1");
    assert_eq!(suggestion.mode, MarketRouterMode::Shadow);
    assert_eq!(suggestion.route_id, "route_high_price");
    assert_eq!(
        suggestion.price_signal_hash,
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    );
    assert_eq!(
        suggestion.pput_prior_hash,
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    );
    assert!(!suggestion.emits_authorization);
    assert!(!suggestion.can_move_accepted_head);
    assert_eq!(suggestion.head_effect, "PRESERVE");
}

#[test]
fn price_broadcast_is_abstract_statistical_signal() {
    let broadcast = PriceBroadcast::new(
        "mkt_demo",
        "0.61",
        "0.39",
        "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    )
    .expect("price broadcast");

    assert_eq!(broadcast.schema_id, "market_price_broadcast.v1");
    assert_eq!(broadcast.truth_status, "statistical_signal_only");
    assert_eq!(broadcast.head_effect, "PRESERVE");
    assert!(!broadcast.worker_visible_summary().contains("PPUT"));
    assert!(!broadcast.worker_visible_summary().contains("hidden"));
}
