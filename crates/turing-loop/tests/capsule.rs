use serde_json::json;
use turing_loop::capsule::{
    CapsuleDraft, PrivateMicroContract, WorkCapsuleId, compile_visible_capsule,
};

#[test]
fn visible_capsule_hides_private_contract() {
    let draft = CapsuleDraft {
        capsule_id: WorkCapsuleId::new("wc_demo"),
        atom_id: "atom_demo".to_string(),
        task: "Edit src/main.rs so the CLI prints hello.".to_string(),
        allowed_files: vec!["src/main.rs".to_string()],
        acceptance_commands: vec!["cargo test -p demo".to_string()],
        private_contract: PrivateMicroContract {
            hidden_predicates: vec!["predicate.secret.acceptance.threshold".to_string()],
            pput_formula: "VPPUT = progress / (tokens * wall_time)".to_string(),
            heldout_ids: vec!["heldout_case_42".to_string()],
            raw_failure_logs: vec!["panic: secret stack trace".to_string()],
            budget_policy: json!({"max_tokens": 1000, "risk": "P3"}),
        },
    };

    let compiled = compile_visible_capsule(draft).expect("compile capsule");
    let visible = compiled.visible_capsule;
    let visible_text = visible.render_for_worker();

    assert_eq!(visible.capsule_id.as_str(), "wc_demo");
    assert_eq!(visible.atom_id, "atom_demo");
    assert!(visible_text.contains("Edit src/main.rs"));
    assert!(visible_text.contains("src/main.rs"));
    assert!(visible_text.contains("cargo test -p demo"));

    assert!(visible.private_contract_hash.starts_with("sha256:"));
    assert!(!visible_text.contains("predicate.secret.acceptance.threshold"));
    assert!(!visible_text.contains("VPPUT"));
    assert!(!visible_text.contains("heldout_case_42"));
    assert!(!visible_text.contains("secret stack trace"));
    assert!(!visible_text.contains("max_tokens"));

    assert_eq!(
        compiled.private_contract.hidden_predicates,
        ["predicate.secret.acceptance.threshold"]
    );
}
