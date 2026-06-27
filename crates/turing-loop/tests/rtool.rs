use turing_contracts::registry::EventClass;
use turing_git_tape::append::{Append, AppendRequest};
use turing_git_tape::git;
use turing_loop::rtool;

#[test]
fn rtool_reads_tape_not_projection_truth() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path();
    git::init_sha256(repo).expect("init sha256 repo");

    let tape = Append::open(repo).expect("open tape");
    let genesis = tape
        .append(
            AppendRequest::new(
                "SystemConstitutionAccepted",
                "writer:genesis",
                serde_json::json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
            )
            .predicate_pass(),
        )
        .expect("append genesis");
    let market = tape
        .append(
            AppendRequest::new(
                "MarketCreated",
                "writer:market",
                serde_json::json!({"market_id": "mkt_demo", "pool_y": "1", "pool_n": "1"}),
            )
            .predicate_pass(),
        )
        .expect("append market");
    let cost = tape
        .append(
            AppendRequest::new(
                "CostEvent",
                "writer:pput",
                serde_json::json!({"run_id": "run_demo", "total_tokens": 7}),
            )
            .predicate_pass(),
        )
        .expect("append cost");

    let poisoned_projection = rtool::ProjectionCache {
        tape_tip: "mu:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff".to_string(),
        accepted_head: "mu:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
            .to_string(),
        market_event_count: 999,
        pput_event_count: 999,
    };

    let q = rtool::read_q(repo, Some(&poisoned_projection)).expect("read Q from tape");

    assert_eq!(q.head_set.tape_tip, cost.event_id);
    assert_eq!(q.head_set.accepted_head, genesis.event_id);
    assert_eq!(q.head_set.authorization_head, None);
    assert_eq!(q.replay_event_count, 3);
    assert_eq!(q.market.market_event_count, 1);
    assert_eq!(q.pput.cost_event_count, 1);
    assert_eq!(q.events.last().unwrap().event_id, cost.event_id);

    let market_event = q
        .events
        .iter()
        .find(|event| event.event_id == market.event_id)
        .expect("market event captured");
    assert_eq!(market_event.event_type, "MarketCreated");
    assert_eq!(market_event.class, EventClass::Economy);
}
