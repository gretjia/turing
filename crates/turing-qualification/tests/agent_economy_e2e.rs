use turing_qualification::{
    RescueDemoReport, run_new_project_agent_economy_demo, run_rescue_agent_economy_demo,
};

#[test]
fn new_project_agent_economy_e2e() {
    let report = run_new_project_agent_economy_demo().expect("new project demo report");

    assert!(report.micro_git_exists);
    assert!(report.tape_tip.starts_with("mu:"));
    assert_eq!(report.market_created_count, 1);
    assert_eq!(report.budget_allocated_count, 1);
    assert_eq!(report.worker_receipt_count, 1);
    assert_eq!(report.macro_observation_count, 1);
    assert_eq!(report.pput_accounted_count, 1);
    assert_eq!(report.market_settled_count, 1);
    assert_eq!(report.accepted_head, report.candidate_accepted_event_id);
    assert_ne!(report.accepted_head, report.market_settled_event_id);
    assert_eq!(report.market_projection_status, "settled");
    assert_eq!(report.pput_progress, 1);
    assert!(report.projection_rebuild_hash.starts_with("sha256:"));
    assert!(report.no_pput_prompt_leakage);
}

#[test]
fn rescue_project_agent_economy_e2e() {
    let report: RescueDemoReport = run_rescue_agent_economy_demo().expect("rescue demo report");

    assert!(report.micro_git_exists);
    assert_eq!(report.failure_node_count, 1);
    assert_eq!(report.broadcast_rule_count, 1);
    assert_eq!(report.failure_class, "NO_DIFF");
    assert_eq!(
        report.accepted_head_after_failure,
        report.accepted_head_before_failure
    );
    assert!(report.recovery_capsule_proposed);
    assert!(report.broadcast_summary_abstract);
}
