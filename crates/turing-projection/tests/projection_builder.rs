use turing_projection::{
    CommandSpec, ConfirmationRoute, HeadConsistency, OperatorHeads, OperatorState,
    OperatorToolManifest, OperatorViewSnapshot, ProductionApprovalRoutePolicy, ProjectionBuilder,
    ProjectionError, ProjectionEvent, ProjectionSource, SideEffectClass, TuiCommand,
    TuiProjectionClient, TypedVerb,
};

#[test]
fn projection_rebuild_is_stable_and_tape_only() {
    let events = vec![
        ProjectionEvent::new(
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "MarketCreated",
            "mkt_demo",
        ),
        ProjectionEvent::new(
            "mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "PPUTAccounted",
            "run_demo",
        ),
    ];

    let first = ProjectionBuilder::from_source(ProjectionSource::MicroTape(events.clone()))
        .build()
        .expect("projection");
    let rebuilt = ProjectionBuilder::from_source(ProjectionSource::MicroTape(events))
        .build()
        .expect("rebuilt projection");

    assert_eq!(first.schema_id, "projection.v1");
    assert_eq!(first.source, "micro_tape_only");
    assert_eq!(first.projection_hash, rebuilt.projection_hash);
    assert_eq!(first.market_event_count, 1);
    assert_eq!(first.pput_event_count, 1);
    assert!(!first.can_write_truth);
}

#[test]
fn tui_projection_client_emits_typed_commands_only() {
    let client = TuiProjectionClient::new();
    let command = client.approve_candidate("candidate_latest");
    assert_eq!(
        command,
        TuiCommand::ApproveCandidate {
            candidate_id: "candidate_latest".to_string()
        }
    );
    assert!(!client.can_write_micro_truth());
}

#[test]
fn projection_copy_does_not_treat_macro_green_as_accepted() {
    let rendered = ProjectionBuilder::render_macro_status("PR open and CI passed");
    assert!(!rendered.contains("verified PR"));
    assert!(!rendered.contains("CI passed therefore accepted"));
    assert!(rendered.contains("external evidence"));
}

#[test]
fn operator_snapshot_is_shared_contract_from_guarded_heads() {
    let heads = OperatorHeads::new(
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        Some("mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
        "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    )
    .expect("valid heads");

    let snapshot = OperatorViewSnapshot::from_guarded_heads(
        "/workspace/project",
        "/workspace/project/.turingos/micro.git",
        "turing replay --verify",
        heads.clone(),
    )
    .expect("snapshot");

    assert_eq!(snapshot.schema_id, "operator_view_snapshot.v1");
    assert_eq!(snapshot.source.source_kind, "guarded_micro_tape_read");
    assert_eq!(
        snapshot.source.projection_version,
        "operator_view_snapshot.v1"
    );
    assert_eq!(snapshot.source.rebuild_command, "turing replay --verify");
    assert!(!snapshot.source.can_write_truth);
    assert_eq!(snapshot.heads, heads);
    assert_eq!(snapshot.head_consistency, HeadConsistency::Consistent);
    assert_eq!(snapshot.operator_state, OperatorState::Healthy);
    assert_eq!(
        snapshot
            .lanes
            .iter()
            .map(|lane| lane.name.as_str())
            .collect::<Vec<_>>(),
        vec!["append", "authorization", "accepted"]
    );
    assert!(
        snapshot
            .warnings
            .iter()
            .any(|warning| warning.code == "NO_HITL_STATUS_CEILING")
    );
    assert!(
        snapshot
            .safe_commands
            .iter()
            .any(|command| command.verb == TypedVerb::VIEW_STATUS)
    );
    assert_eq!(snapshot.next_sovereign_action, "no human approval pending");
    assert!(snapshot.snapshot_hash.starts_with("sha256:"));
}

#[test]
fn operator_snapshot_rejects_caller_supplied_projection_events() {
    let error = OperatorViewSnapshot::from_projection_events_forbidden(vec![ProjectionEvent::new(
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "CandidateAccepted",
        "forged_candidate",
    )])
    .expect_err("projection events are not an operator snapshot source");

    assert_eq!(
        error,
        ProjectionError::CallerSuppliedProjectionEventsForbidden
    );
}

#[test]
fn typed_commands_cover_closed_verb_set_and_boundaries() {
    let specs = CommandSpec::all();
    let verbs = specs.iter().map(|spec| spec.verb).collect::<Vec<_>>();

    assert_eq!(
        verbs,
        vec![
            TypedVerb::VIEW_STATUS,
            TypedVerb::VIEW_PANOVIEW,
            TypedVerb::EXPLAIN_EVENT,
            TypedVerb::EXPLAIN_BLOCKER,
            TypedVerb::REPLAY_VERIFY,
            TypedVerb::AUDIT_INVARIANTS,
            TypedVerb::PROPOSE_INTENT,
            TypedVerb::PROPOSE_GOAL,
            TypedVerb::PROPOSE_CAPSULE,
            TypedVerb::APPROVE_CAPSULE,
            TypedVerb::DISPATCH_WORKER,
            TypedVerb::OBSERVE_CAPSULE,
            TypedVerb::REJECT_CANDIDATE,
            TypedVerb::REQUEST_MACRO_AUTH,
            TypedVerb::APPROVE_CANDIDATE,
            TypedVerb::HELP,
        ]
    );

    let view_status = CommandSpec::get(TypedVerb::VIEW_STATUS).expect("VIEW_STATUS");
    assert_eq!(view_status.side_effect_class, SideEffectClass::ReadOnly);
    assert!(!view_status.approval_required);
    assert!(view_status.dry_run_default);
    assert!(!view_status.writes_truth);
    assert_eq!(view_status.confirmation_route, ConfirmationRoute::None);

    let approve_candidate =
        CommandSpec::get(TypedVerb::APPROVE_CANDIDATE).expect("APPROVE_CANDIDATE");
    assert_eq!(
        approve_candidate.side_effect_class,
        SideEffectClass::SovereignMutation
    );
    assert!(approve_candidate.approval_required);
    assert!(approve_candidate.dry_run_default);
    assert!(!approve_candidate.writes_truth);
    assert_eq!(
        approve_candidate.confirmation_route,
        ConfirmationRoute::HumanSignatureRequired
    );
    assert_eq!(
        approve_candidate.expected_receipt,
        "approval_required_or_human_signature_required"
    );
}

#[test]
fn tool_manifest_exposes_only_closed_operator_tools() {
    let manifest = OperatorToolManifest::closed_v1();
    assert_eq!(manifest.schema_id, "operator_tool_manifest.v1");
    assert!(!manifest.can_evaluate_predicates);
    assert!(!manifest.can_move_heads);
    assert!(!manifest.can_run_shell);
    let manifest_json = serde_json::to_value(&manifest).expect("manifest JSON");
    assert_eq!(manifest_json["can_autonomous_dispatch"], false);
    assert_eq!(manifest.commands.len(), CommandSpec::all().len());
    assert!(
        manifest
            .commands
            .iter()
            .all(|command| CommandSpec::get(command.verb).is_some())
    );
}

#[test]
fn production_approval_routes_reject_test_and_local_signing() {
    assert!(ProductionApprovalRoutePolicy::allows("os-keyring"));
    assert!(ProductionApprovalRoutePolicy::allows("hardware"));
    assert!(!ProductionApprovalRoutePolicy::allows("in-memory-test"));
    assert!(!ProductionApprovalRoutePolicy::allows("local-file-dev"));
}
