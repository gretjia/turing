use serde_json::json;
use turing_git_tape::append::{Append, AppendRequest, committed_body_bytes};
use turing_git_tape::git;

#[test]
fn append_derives_authority_epoch_from_tape_tip() {
    let dir = tempfile::tempdir().expect("temp dir");
    let repo = dir.path().join("micro.git");
    std::fs::create_dir(&repo).expect("create micro git dir");
    git::init_sha256(&repo).expect("init micro git");

    let tape = Append::open(&repo).expect("open tape");
    tape.append(
        AppendRequest::new(
            "SystemConstitutionAccepted",
            "writer:genesis",
            json!({"constitution_digest": "sha256:".to_string() + &"a".repeat(64)}),
        )
        .predicate_pass(),
    )
    .expect("append genesis");

    let amended = tape
        .append(
            AppendRequest::new(
                "ProjectLawAmended",
                "writer:authority",
                json!({
                        "amendment_kind": "AUTHORITY_TRANSFER",
                        "human_signed": true,
                        "new_authority_epoch": 1
                }),
            )
            .predicate_pass(),
        )
        .expect("append authority transfer");

    let body = committed_body_bytes(&repo, &amended.event_id).expect("read amended body");
    let amended_body: serde_json::Value = serde_json::from_slice(&body).expect("json");
    assert_eq!(amended_body["authority_epoch"], 0);

    let follow_up = tape
        .append(
            AppendRequest::new(
                "MarketCreated",
                "writer:goal",
                json!({
                    "schema_id": "market_created.v1",
                    "event_type": "MarketCreated",
                    "head_effect": "PRESERVE",
                    "market_id": "mkt_after_epoch",
                    "initial_pool_y": "10",
                    "initial_pool_n": "10",
                    "k": "100",
                    "truth_status": "statistical_signal_only"
                }),
            )
            .predicate_pass(),
        )
        .expect("append follow-up");

    let follow_up_body = committed_body_bytes(&repo, &follow_up.event_id).expect("read body");
    let follow_up_body: serde_json::Value = serde_json::from_slice(&follow_up_body).expect("json");
    assert_eq!(follow_up_body["authority_epoch"], 1);
}
