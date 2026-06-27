use turing_pput::{
    CostEvent, GroundTruthResult, PputProjection, PputRunInput, ProposalRecord, Split,
    WorkerPromptShield,
};

#[test]
fn cost_event_counts_tokens_stdout_and_wall_time() {
    let cost = CostEvent::new(
        "run_a",
        "problem_a",
        Split::Heldout,
        "agent_worker",
        "branch_failed",
        "wc_1",
        3,
        4,
        2,
        1,
        100,
        b"tool stdout",
    )
    .expect("cost event");

    assert_eq!(cost.schema_id, "cost_event.v1");
    assert_eq!(cost.total_tokens, 10);
    assert_eq!(cost.tool_stdout_tokens, 1);
    assert_eq!(cost.wall_time_ms, 100);
    assert!(cost.tool_stdout_hash.starts_with("sha256:"));
    assert!(cost.counted_in_total);
}

#[test]
fn failed_branches_count_toward_cost_and_progress_requires_golden_path() {
    let costs = vec![
        CostEvent::new(
            "run_a",
            "problem_a",
            Split::Heldout,
            "agent_worker",
            "branch_failed",
            "wc_fail",
            3,
            4,
            2,
            1,
            100,
            b"failed stdout",
        )
        .expect("failed cost"),
        CostEvent::new(
            "run_a",
            "problem_a",
            Split::Heldout,
            "agent_worker",
            "branch_gold",
            "wc_gold",
            2,
            2,
            1,
            0,
            100,
            b"",
        )
        .expect("gold cost"),
    ];
    let proposals = vec![
        ProposalRecord::new("branch_failed", GroundTruthResult::Fail, false),
        ProposalRecord::new("branch_gold", GroundTruthResult::Pass, true),
    ];

    let accounted = PputRunInput {
        run_id: "run_a".to_string(),
        problem_id: "problem_a".to_string(),
        split: Split::Heldout,
        costs,
        proposals,
        verified: true,
    }
    .account()
    .expect("PPUT accounted");

    assert_eq!(accounted.schema_id, "pput_accounted.v1");
    assert_eq!(accounted.total_run_token_count, 15);
    assert_eq!(accounted.golden_path_token_count, 5);
    assert_eq!(accounted.total_wall_time_ms, 200);
    assert_eq!(accounted.failed_branch_count, 1);
    assert_eq!(accounted.progress, 1);
    assert_eq!(accounted.vpput_raw, "0.000333333");
    assert!(accounted.hidden_from_worker_prompt);
}

#[test]
fn pput_projection_rebuilds_from_tape_and_prompt_shield_blocks_leakage() {
    let costs = vec![
        CostEvent::new(
            "run_b",
            "problem_b",
            Split::Dogfood,
            "agent_worker",
            "branch_one",
            "wc_1",
            1,
            1,
            1,
            1,
            50,
            b"stdout",
        )
        .expect("cost"),
    ];

    let projection = PputProjection::from_tape_events(&costs).expect("projection");
    assert_eq!(projection.source, "micro_tape_only");
    assert_eq!(projection.total_tokens, 4);
    assert_eq!(projection.total_wall_time_ms, 50);

    assert!(WorkerPromptShield::validate("Fix the file and report pass/fail.").is_ok());
    assert!(WorkerPromptShield::validate("Optimize PPUT on heldout ids.").is_err());
}
