use std::fs;
use std::path::PathBuf;

#[test]
fn final_handoff_references_heads_replay_market_pput_and_risks() {
    let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let handoff = repo.join("docs/handoff/AGENT_ECONOMY_RUNTIME_HANDOFF.md");
    let text = fs::read_to_string(&handoff)
        .unwrap_or_else(|error| panic!("handoff must exist at {}: {error}", handoff.display()));

    for required in [
        "tape_tip",
        "authorization_head",
        "accepted_head",
        "market projection hash",
        "wallet projection hash",
        "PPUT projection hash",
        "cargo test --workspace",
        "bash demo/demo_agent_economy_e2e.sh",
        "bash demo/demo_rescue_agent_economy.sh",
        "turing replay --verify",
        "turing audit market",
        "turing audit pput",
        "market projection",
        "price_not_truth=true",
        "PPUT projection snapshot write",
        "hidden_from_worker_prompt=true",
        "raw_formula_exposed=false",
        "Known Risks",
    ] {
        assert!(text.contains(required), "handoff missing {required:?}");
    }
}
