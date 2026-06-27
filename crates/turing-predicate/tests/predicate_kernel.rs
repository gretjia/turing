use turing_contracts::envelope::PredicateProduct;
use turing_predicate::{
    MarketPputPredicateError, PredicateCheck, PredicateKernel, PredicateReport,
    market_event_preserves_truth, market_settlement_event_is_micro, no_pput_in_worker_prompt,
};

#[test]
fn predicate_product_deterministic() {
    let kernel = PredicateKernel::default();
    let checks = vec![
        PredicateCheck::pass("scope.allowed"),
        PredicateCheck::fail("budget.within_limit", "BUDGET_SCOPE"),
    ];
    let reversed = vec![
        PredicateCheck::fail("budget.within_limit", "BUDGET_SCOPE"),
        PredicateCheck::pass("scope.allowed"),
    ];

    let report = kernel
        .run("CandidateAccepted", checks)
        .expect("predicate report");
    let same_report = kernel
        .run("CandidateAccepted", reversed)
        .expect("same report");

    assert_eq!(report, same_report);
    assert_eq!(report.product, PredicateProduct::Fail);
    assert_eq!(report.reject_class.as_deref(), Some("BUDGET_SCOPE"));
    assert_eq!(report.failed_predicates, ["budget.within_limit"]);
    assert!(report.report_hash.starts_with("sha256:"));

    let pass = kernel
        .run(
            "CandidateAccepted",
            vec![
                PredicateCheck::pass("budget.within_limit"),
                PredicateCheck::pass("scope.allowed"),
            ],
        )
        .expect("pass report");
    assert_eq!(
        pass,
        PredicateReport {
            event_type: "CandidateAccepted".to_string(),
            product: PredicateProduct::Pass,
            passed_predicates: vec![
                "budget.within_limit".to_string(),
                "scope.allowed".to_string(),
            ],
            failed_predicates: Vec::new(),
            reject_class: None,
            report_hash: pass.report_hash.clone(),
        }
    );
}

#[test]
fn market_pput_predicates() {
    market_event_preserves_truth("MarketCreated").expect("market event is preserve-only");
    market_event_preserves_truth("AMMSwapExecuted").expect("swap event is preserve-only");
    market_event_preserves_truth("MarketSettled").expect("settlement event is preserve-only");
    assert_eq!(
        market_event_preserves_truth("CandidateAccepted"),
        Err(MarketPputPredicateError::NotEconomyEvent(
            "CandidateAccepted".to_string()
        ))
    );

    let micro_id = format!("mu:{}", "a".repeat(64));
    market_settlement_event_is_micro(&micro_id).expect("settlement references Micro event");
    assert_eq!(
        market_settlement_event_is_micro("macro:ci:green"),
        Err(MarketPputPredicateError::InvalidSettlementEventId(
            "macro:ci:green".to_string()
        ))
    );

    no_pput_in_worker_prompt("Implement the capsule and run cargo test.")
        .expect("ordinary worker prompt is allowed");
    assert_eq!(
        no_pput_in_worker_prompt("Optimize VPPUT = progress / (tokens * wall_time)."),
        Err(MarketPputPredicateError::PputLeakage("VPPUT".to_string()))
    );
    assert_eq!(
        no_pput_in_worker_prompt("Use heldout_case_42 to tune the answer."),
        Err(MarketPputPredicateError::PputLeakage("heldout".to_string()))
    );
}
