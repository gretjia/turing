use turing_projection::{
    ProjectionBuilder, ProjectionEvent, ProjectionSource, TuiCommand, TuiProjectionClient,
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
