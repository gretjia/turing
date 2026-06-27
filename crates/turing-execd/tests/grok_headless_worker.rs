use turing_execd::workers::{AuthSurface, DispatchPurpose, Provenance, WorkerKind};
use turing_execd::{GrokHeadlessRequest, GrokHeadlessWorker, WorkerRunError};

#[test]
fn grok_worker_id_is_content_addressed_hash() {
    let id = GrokHeadlessWorker::worker_id_for("grok-code-fast-1");
    assert!(id.starts_with("worker:sha256:"));
    assert_eq!(id.len(), "worker:sha256:".len() + 64);
    assert_eq!(id, GrokHeadlessWorker::worker_id_for("grok-code-fast-1"));
    assert_ne!(id, GrokHeadlessWorker::worker_id_for("grok-code-fast-2"));
}

#[test]
fn grok_headless_command_forces_no_planning_and_minimal_reasoning() {
    let worker = GrokHeadlessWorker::try_new(GrokHeadlessWorker::worker_id_for("grok-code-fast-1"))
        .expect("valid grok worker");

    assert_eq!(worker.profile().kind, WorkerKind::CommandTemplate);
    assert_eq!(worker.profile().provenance, Provenance::Partial);
    assert_eq!(
        worker.profile().dispatch_purpose,
        vec![DispatchPurpose::PrimaryExecution]
    );
    assert_eq!(worker.profile().failure_domain.provider, "grok");
    assert_eq!(
        worker.profile().failure_domain.auth_surface,
        AuthSurface::LocalCli
    );
    assert!(worker.profile().failure_domain.network_required);

    let plan = worker
        .command_plan(GrokHeadlessRequest {
            capsule_id: "wc_demo".to_string(),
            worktree: "/tmp/turingos-mini-swe/wc_demo".to_string(),
            visible_capsule: "Fix the failing test. Allowed files: src/lib.rs.".to_string(),
            model: "grok-code-fast-1".to_string(),
            max_turns: 8,
        })
        .expect("grok command plan");

    assert_eq!(plan.argv[0], "grok");
    assert!(
        plan.argv
            .windows(2)
            .any(|w| w == ["--cwd", "/tmp/turingos-mini-swe/wc_demo"])
    );
    assert!(
        plan.argv
            .windows(2)
            .any(|w| w == ["--output-format", "json"])
    );
    assert!(
        plan.argv
            .windows(2)
            .any(|w| w == ["--reasoning-effort", "low"])
    );
    assert!(plan.argv.windows(2).any(|w| w == ["--effort", "low"]));
    assert!(plan.argv.windows(2).any(|w| w == ["--max-turns", "8"]));
    assert!(plan.argv.contains(&"--always-approve".to_string()));
    assert!(plan.argv.contains(&"--disable-web-search".to_string()));
    assert!(plan.argv.contains(&"--no-plan".to_string()));
    assert!(plan.argv.contains(&"--no-memory".to_string()));
    assert!(plan.argv.contains(&"--no-subagents".to_string()));
    assert!(plan.argv.contains(&"--verbatim".to_string()));

    assert!(plan.prompt.contains("Do not output chain-of-thought"));
    assert!(
        plan.prompt
            .contains("TuringOS Micro Tape records the external progress trace")
    );
    assert!(!plan.prompt.contains("hidden predicate"));
    assert!(!plan.prompt.contains("PPUT"));
    assert!(plan.prompt_hash.starts_with("sha256:"));
}

#[test]
fn grok_headless_rejects_hidden_prompt_markers() {
    let worker = GrokHeadlessWorker::try_new(GrokHeadlessWorker::worker_id_for("grok-code-fast-1"))
        .expect("valid grok worker");

    let err = worker
        .command_plan(GrokHeadlessRequest {
            capsule_id: "wc_leaky".to_string(),
            worktree: "/tmp/turingos-mini-swe/wc_leaky".to_string(),
            visible_capsule: "Use the hidden predicate and PPUT target.".to_string(),
            model: "grok-code-fast-1".to_string(),
            max_turns: 8,
        })
        .expect_err("hidden markers must fail closed");

    assert_eq!(
        err,
        WorkerRunError::HiddenWorkerPromptMarker("hidden predicate".to_string())
    );
}

#[test]
fn grok_headless_rejects_non_hash_worker_id() {
    assert!(matches!(
        GrokHeadlessWorker::try_new("grok-worker"),
        Err(WorkerRunError::Profile(_))
    ));
}
