use turing_contracts::goal::{GoalRequirement, GoalState, GoalValidationError, MachineCheck};

#[test]
fn goal_state_requires_machine_predicates() {
    let predicate_goal = GoalState::new("goal_demo", "ship a replayable runtime").with_must_have(
        GoalRequirement::must_have("replay passes")
            .with_machine_check(MachineCheck::predicate("predicate.replay.verify")),
    );
    predicate_goal
        .validate()
        .expect("predicate-backed must_have is valid");

    let pcp_goal = GoalState::new("goal_demo_pcp", "ship a replayable runtime").with_must_have(
        GoalRequirement::must_have("architecture law holds")
            .with_machine_check(MachineCheck::pcp("pcp.single_loop_purity")),
    );
    pcp_goal.validate().expect("PCP-backed must_have is valid");

    let language_only = GoalState::new("goal_bad", "ship a replayable runtime")
        .with_must_have(GoalRequirement::must_have("make it robust"));
    assert_eq!(
        language_only.validate(),
        Err(GoalValidationError::MustHaveMissingMachineCheck {
            index: 0,
            requirement: "make it robust".to_string(),
        })
    );

    let empty_predicate = GoalState::new("goal_empty", "ship a replayable runtime").with_must_have(
        GoalRequirement::must_have("replay passes").with_machine_check(MachineCheck::predicate("")),
    );
    assert_eq!(
        empty_predicate.validate(),
        Err(GoalValidationError::EmptyMachineCheckId {
            requirement_index: 0,
            check_index: 0,
        })
    );
}
