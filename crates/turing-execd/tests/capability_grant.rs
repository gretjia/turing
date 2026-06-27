use turing_execd::capability::{
    ActionClass, Budget, CapabilityGrant, CapabilityScope, GrantError, NetworkScope, Risk,
    RiskClass, SignatureRoute, ToolRequest,
};

#[test]
fn capability_grant_scope_enforced() {
    let grant = CapabilityGrant {
        grant_id: "cg_demo".to_string(),
        capsule_id: "wc_demo".to_string(),
        agent_id: "agent_demo".to_string(),
        market_id: None,
        budget: Budget {
            max_tokens: 1000,
            max_wall_time_ms: 30_000,
            max_tool_calls: 2,
            max_mutated_files: 1,
        },
        scope: CapabilityScope {
            allowed_paths: vec!["src".to_string(), "tests".to_string()],
            forbidden_paths: vec!["src/secrets".to_string()],
            allowed_tools: vec!["read_file".to_string(), "apply_patch".to_string()],
            network: NetworkScope::Denied,
        },
        risk: Risk {
            risk_class: RiskClass::P3,
            human_before_dispatch: false,
            human_before_accept: false,
            human_before_merge: true,
        },
        authorization_event: None,
        signature_route: SignatureRoute::None,
    };

    grant
        .authorize(&ToolRequest {
            tool: "apply_patch".to_string(),
            path: Some("src/main.rs".to_string()),
            action: ActionClass::FileWrite,
            mutates: true,
            requested_tool_call_index: 2,
            mutated_files_after: 1,
            needs_network: false,
        })
        .expect("allowed write within scope");

    assert_eq!(
        grant.authorize(&ToolRequest {
            tool: "apply_patch".to_string(),
            path: Some("src/secrets/key.txt".to_string()),
            action: ActionClass::FileWrite,
            mutates: true,
            requested_tool_call_index: 1,
            mutated_files_after: 1,
            needs_network: false,
        }),
        Err(GrantError::ForbiddenPath("src/secrets/key.txt".to_string()))
    );
    assert_eq!(
        grant.authorize(&ToolRequest {
            tool: "apply_patch".to_string(),
            path: Some("../outside.rs".to_string()),
            action: ActionClass::FileWrite,
            mutates: true,
            requested_tool_call_index: 1,
            mutated_files_after: 1,
            needs_network: false,
        }),
        Err(GrantError::PathTraversal("../outside.rs".to_string()))
    );
    assert_eq!(
        grant.authorize(&ToolRequest {
            tool: "run_command".to_string(),
            path: Some("src/main.rs".to_string()),
            action: ActionClass::Command,
            mutates: false,
            requested_tool_call_index: 1,
            mutated_files_after: 0,
            needs_network: false,
        }),
        Err(GrantError::ToolDenied("run_command".to_string()))
    );
    assert_eq!(
        grant.authorize(&ToolRequest {
            tool: "read_file".to_string(),
            path: Some("src/main.rs".to_string()),
            action: ActionClass::FileRead,
            mutates: false,
            requested_tool_call_index: 3,
            mutated_files_after: 0,
            needs_network: false,
        }),
        Err(GrantError::ToolCallBudgetExceeded {
            requested: 3,
            max: 2
        })
    );
    assert_eq!(
        grant.authorize(&ToolRequest {
            tool: "read_file".to_string(),
            path: Some("src/main.rs".to_string()),
            action: ActionClass::FileRead,
            mutates: false,
            requested_tool_call_index: 1,
            mutated_files_after: 0,
            needs_network: true,
        }),
        Err(GrantError::NetworkDenied)
    );
    assert_eq!(
        grant.authorize(&ToolRequest {
            tool: "apply_patch".to_string(),
            path: Some("src/main.rs".to_string()),
            action: ActionClass::IrreversibleMacro,
            mutates: true,
            requested_tool_call_index: 1,
            mutated_files_after: 1,
            needs_network: false,
        }),
        Err(GrantError::IrreversibleActionNeedsAuthorization)
    );
}
