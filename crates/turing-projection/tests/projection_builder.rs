use serde_json::json;
use turing_projection::{
    CommandSpec, ConfirmationRoute, HeadConsistency, OperatorHeads, OperatorState,
    OperatorToolManifest, OperatorViewSnapshot, ProductionApprovalRoutePolicy, ProjectionBuilder,
    ProjectionError, ProjectionEvent, ProjectionSource, RawTapeEvent, SideEffectClass, TuiCommand,
    TuiProjectionClient, TypedVerb, WorkItemStage, derive_work_items,
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
        Vec::new(),
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
    assert!(
        snapshot.work_items.is_none(),
        "no work_items passed in ⇒ legacy snapshot shape (field omitted, not an empty array)"
    );
}

#[test]
fn work_items_absent_leaves_snapshot_hash_unchanged_from_legacy_shape() {
    // The preimage must mirror `skip_serializing_if` exactly: passing an empty `work_items`
    // Vec (⇒ `None` ⇒ omitted key) must hash identically to a snapshot built before this
    // atom existed — the shadow-rebuild self-consistency checks in
    // `tools/hci/audit_projection_integrity.py` / FCE-R2 hash "the whole JSON object minus
    // `snapshot_hash`", so a phantom `"work_items": null` preimage key would desync them.
    let heads = OperatorHeads::new(
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        Some("mu:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
        "mu:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    )
    .expect("valid heads");

    let with_empty_vec = OperatorViewSnapshot::from_guarded_heads(
        "/workspace/project",
        "/workspace/project/.turingos/micro.git",
        "turing replay --verify",
        heads.clone(),
        Vec::new(),
    )
    .expect("snapshot with empty work_items");

    let json = serde_json::to_value(&with_empty_vec).expect("snapshot JSON");
    assert!(
        json.as_object().expect("object").get("work_items").is_none(),
        "an empty work_items Vec must serialize with the key omitted entirely: {json}"
    );
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

fn event(event_type: &str, payload: serde_json::Value) -> RawTapeEvent {
    RawTapeEvent {
        event_type: event_type.to_string(),
        payload,
    }
}

#[test]
fn derive_work_items_is_empty_for_events_with_no_capsule_lifecycle() {
    let events = vec![
        event(
            "SystemConstitutionAccepted",
            json!({"constitution_digest": "sha256:aa"}),
        ),
        event(
            "GoalStateProposed",
            json!({"goal_id": "goal_x", "intent": "x"}),
        ),
    ];
    assert!(derive_work_items(&events).is_empty());
}

#[test]
fn derive_work_items_ignores_a_bare_proposal_with_no_further_progress() {
    // WorkCapsuleBuilt alone never yields a work item — there is no valid closed-enum stage
    // below `authorized`.
    let events = vec![event(
        "WorkCapsuleBuilt",
        json!({"capsule_id": "wc_only_proposed", "title": "never dispatched"}),
    )];
    assert!(derive_work_items(&events).is_empty());
}

#[test]
fn derive_work_items_matches_the_liar_fixture_shape() {
    // Mirrors spec §6: Capsule A (the liar, claimed/no receipt), Capsule B (the honest one,
    // receipt matched + accepted), Item C (blocked, machine-readable reason).
    let events = vec![
        event(
            "WorkCapsuleBuilt",
            json!({"capsule_id": "wc_liar_a", "title": "Capsule A (the liar)"}),
        ),
        event("WorkerDispatchAuthorized", json!({"capsule_id": "wc_liar_a"})),
        event("WorkerRunStarted", json!({"capsule_id": "wc_liar_a"})),
        event("WorkerDispatched", json!({"capsule_id": "wc_liar_a"})),
        event(
            "WorkCapsuleBuilt",
            json!({"capsule_id": "wc_liar_b", "title": "Capsule B (the honest one)"}),
        ),
        event("WorkerDispatchAuthorized", json!({"capsule_id": "wc_liar_b"})),
        event("WorkerRunStarted", json!({"capsule_id": "wc_liar_b"})),
        event("WorkerDispatched", json!({"capsule_id": "wc_liar_b"})),
        event(
            "WorkerReceiptImported",
            json!({"capsule_id": "wc_liar_b", "receipt_id": "rcp_liar_b"}),
        ),
        event("CandidateAccepted", json!({"capsule_id": "wc_liar_b"})),
        event(
            "WorkCapsuleBuilt",
            json!({"capsule_id": "wc_liar_c", "title": "Item C (the blocked one)"}),
        ),
        event("WorkerDispatchAuthorized", json!({"capsule_id": "wc_liar_c"})),
        event(
            "FailureNode",
            json!({"capsule_id": "wc_liar_c", "blocked_reason": "AUTH_REQUIRED"}),
        ),
    ];

    let items = derive_work_items(&events);
    assert_eq!(items.len(), 3);

    let a = &items[0];
    assert_eq!(a.id, "wc_liar_a");
    assert_eq!(a.title, "Capsule A (the liar)");
    assert_eq!(a.stage, WorkItemStage::AwaitingReceipt);
    assert!(a.claimed_complete);
    assert!(a.receipt.is_none());
    assert!(a.blocked_reason.is_none());

    let b = &items[1];
    assert_eq!(b.id, "wc_liar_b");
    assert_eq!(b.title, "Capsule B (the honest one)");
    assert_eq!(b.stage, WorkItemStage::Accepted);
    assert!(b.claimed_complete);
    let receipt = b.receipt.as_ref().expect("capsule B has a matched receipt");
    assert_eq!(receipt.receipt_id, "rcp_liar_b");
    assert!(receipt.matched);
    assert!(b.blocked_reason.is_none());

    let c = &items[2];
    assert_eq!(c.id, "wc_liar_c");
    assert_eq!(c.title, "Item C (the blocked one)");
    assert_eq!(c.stage, WorkItemStage::Authorized);
    assert!(!c.claimed_complete);
    assert!(c.receipt.is_none());
    assert_eq!(c.blocked_reason.as_deref(), Some("AUTH_REQUIRED"));

    // Header contract (spec 2.2): claimed complete counts every item with claimed_complete,
    // accepted world state counts only the closed Accepted stage, and the "no receipt" delta
    // is claimed-but-receiptless.
    let claimed = items.iter().filter(|item| item.claimed_complete).count();
    let accepted = items
        .iter()
        .filter(|item| item.stage == WorkItemStage::Accepted)
        .count();
    let no_receipt = items
        .iter()
        .filter(|item| item.claimed_complete && item.receipt.is_none())
        .count();
    assert_eq!(claimed, 2);
    assert_eq!(accepted, 1);
    assert_eq!(no_receipt, 1);
}

#[test]
fn derive_work_items_glyph_ascii_and_label_are_the_closed_enum() {
    assert_eq!(WorkItemStage::Authorized.glyph(), "\u{25cf}");
    assert_eq!(WorkItemStage::Authorized.ascii_glyph(), "*");
    assert_eq!(WorkItemStage::Authorized.label(), "AUTHORIZED");

    assert_eq!(WorkItemStage::PendingExecution.glyph(), "\u{25d0}");
    assert_eq!(WorkItemStage::PendingExecution.ascii_glyph(), "o");
    assert_eq!(WorkItemStage::PendingExecution.label(), "PENDING EXECUTION");

    assert_eq!(WorkItemStage::AwaitingReceipt.glyph(), "\u{25cc}");
    assert_eq!(WorkItemStage::AwaitingReceipt.ascii_glyph(), ".");
    assert_eq!(WorkItemStage::AwaitingReceipt.label(), "AWAITING RECEIPT");

    assert_eq!(WorkItemStage::ReceiptMatched.glyph(), "\u{2713}");
    assert_eq!(WorkItemStage::ReceiptMatched.ascii_glyph(), "v");
    assert_eq!(WorkItemStage::ReceiptMatched.label(), "RECEIPT MATCHED");

    assert_eq!(WorkItemStage::Accepted.glyph(), "\u{25a0}");
    assert_eq!(WorkItemStage::Accepted.ascii_glyph(), "#");
    assert_eq!(WorkItemStage::Accepted.label(), "ACCEPTED WORLD STATE");
}

#[test]
fn work_items_serialize_with_the_contract_closed_stage_strings() {
    let events = vec![
        event("WorkCapsuleBuilt", json!({"capsule_id": "wc_x"})),
        event("WorkerDispatchAuthorized", json!({"capsule_id": "wc_x"})),
    ];
    let items = derive_work_items(&events);
    let json = serde_json::to_value(&items).expect("work items JSON");
    assert_eq!(json[0]["stage"], "authorized");
    assert_eq!(json[0]["id"], "wc_x");
    assert_eq!(json[0]["title"], "wc_x");
    assert_eq!(json[0]["claimed_complete"], false);
    assert!(json[0]["receipt"].is_null());
    assert!(json[0]["blocked_reason"].is_null());
}
