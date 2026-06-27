use turing_contracts::envelope::PredicateProduct;
use turing_predicate::{PredicateCheck, PredicateKernel, PredicateReport};

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
