use turing_execd::workers::{
    AuthSurface, DispatchPurpose, FailureDomain, Provenance, WorkerKind, WorkerProfile,
    WorkerProfileError,
};

#[test]
fn worker_profile_no_backup_no_worker_role() {
    let vendor = WorkerProfile::vendor_bundle(
        "worker_codex_cli",
        WorkerKind::CommandTemplate,
        vec![DispatchPurpose::PrimaryExecution],
        vec!["code_edit".to_string(), "test_run".to_string()],
        FailureDomain {
            provider: "openai".to_string(),
            auth_surface: AuthSurface::LocalCli,
            network_required: true,
        },
    )
    .expect("vendor bundle profile");

    assert_eq!(vendor.provenance, Provenance::Partial);
    assert_eq!(
        WorkerProfile::contract_field_names(),
        [
            "worker_id",
            "kind",
            "provenance",
            "dispatch_purpose",
            "capabilities",
            "failure_domain",
        ]
    );
    assert!(
        !WorkerProfile::contract_field_names().contains(&"worker_role"),
        "dispatch_purpose is routing metadata, not a constitution role"
    );

    assert_eq!(
        DispatchPurpose::parse("PROVIDER_BACKUP"),
        Err(WorkerProfileError::ForbiddenBackupTerm(
            "PROVIDER_BACKUP".to_string()
        ))
    );
    assert_eq!(
        DispatchPurpose::parse("worker_role"),
        Err(WorkerProfileError::ForbiddenWorkerRoleTerm(
            "worker_role".to_string()
        ))
    );
    assert_eq!(
        WorkerProfile::new(
            "worker_missing_domain",
            WorkerKind::Fake,
            Provenance::Full,
            vec![DispatchPurpose::OfflineBootstrap],
            vec!["test_run".to_string()],
            None,
        ),
        Err(WorkerProfileError::MissingFailureDomain)
    );
}
