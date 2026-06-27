//! Executor daemon contracts.
//!
//! M6 starts with WorkerProfile validation. The profile describes dispatch routing and
//! provenance; it deliberately does not mint constitutional agent roles.

pub mod workers {
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum WorkerKind {
        CommandTemplate,
        ServerSession,
        Fake,
        Manual,
        ApiToolLoop,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum Provenance {
        Full,
        RepoLevel,
        Partial,
        OutsideGovernance,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum DispatchPurpose {
        PrimaryExecution,
        CapabilitySecondary,
        ProviderContinuity,
        OfflineBootstrap,
    }

    impl DispatchPurpose {
        pub fn parse(raw: &str) -> Result<Self, WorkerProfileError> {
            let normalized = raw.trim().to_ascii_uppercase();
            let lower = raw.trim().to_ascii_lowercase();
            if lower.contains("worker_role") {
                return Err(WorkerProfileError::ForbiddenWorkerRoleTerm(raw.to_string()));
            }
            if lower.contains("backup") {
                return Err(WorkerProfileError::ForbiddenBackupTerm(raw.to_string()));
            }

            match normalized.as_str() {
                "PRIMARY_EXECUTION" => Ok(DispatchPurpose::PrimaryExecution),
                "CAPABILITY_SECONDARY" => Ok(DispatchPurpose::CapabilitySecondary),
                "PROVIDER_CONTINUITY" => Ok(DispatchPurpose::ProviderContinuity),
                "OFFLINE_BOOTSTRAP" => Ok(DispatchPurpose::OfflineBootstrap),
                _ => Err(WorkerProfileError::UnknownDispatchPurpose(raw.to_string())),
            }
        }
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum AuthSurface {
        LocalCli,
        ApiKey,
        None,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct FailureDomain {
        pub provider: String,
        pub auth_surface: AuthSurface,
        pub network_required: bool,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct WorkerProfile {
        pub worker_id: String,
        pub kind: WorkerKind,
        pub provenance: Provenance,
        pub dispatch_purpose: Vec<DispatchPurpose>,
        pub capabilities: Vec<String>,
        pub failure_domain: FailureDomain,
    }

    impl WorkerProfile {
        pub fn new(
            worker_id: impl Into<String>,
            kind: WorkerKind,
            provenance: Provenance,
            dispatch_purpose: Vec<DispatchPurpose>,
            capabilities: Vec<String>,
            failure_domain: Option<FailureDomain>,
        ) -> Result<Self, WorkerProfileError> {
            if dispatch_purpose.is_empty() {
                return Err(WorkerProfileError::MissingDispatchPurpose);
            }
            let failure_domain = failure_domain.ok_or(WorkerProfileError::MissingFailureDomain)?;
            Ok(WorkerProfile {
                worker_id: worker_id.into(),
                kind,
                provenance,
                dispatch_purpose,
                capabilities,
                failure_domain,
            })
        }

        pub fn vendor_bundle(
            worker_id: impl Into<String>,
            kind: WorkerKind,
            dispatch_purpose: Vec<DispatchPurpose>,
            capabilities: Vec<String>,
            failure_domain: FailureDomain,
        ) -> Result<Self, WorkerProfileError> {
            WorkerProfile::new(
                worker_id,
                kind,
                Provenance::Partial,
                dispatch_purpose,
                capabilities,
                Some(failure_domain),
            )
        }

        #[must_use]
        pub fn contract_field_names() -> [&'static str; 6] {
            [
                "worker_id",
                "kind",
                "provenance",
                "dispatch_purpose",
                "capabilities",
                "failure_domain",
            ]
        }
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum WorkerProfileError {
        MissingDispatchPurpose,
        MissingFailureDomain,
        ForbiddenBackupTerm(String),
        ForbiddenWorkerRoleTerm(String),
        UnknownDispatchPurpose(String),
    }

    impl std::fmt::Display for WorkerProfileError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                WorkerProfileError::MissingDispatchPurpose => {
                    write!(f, "WorkerProfile dispatch_purpose must not be empty")
                }
                WorkerProfileError::MissingFailureDomain => {
                    write!(f, "WorkerProfile failure_domain is required")
                }
                WorkerProfileError::ForbiddenBackupTerm(term) => {
                    write!(f, "WorkerProfile forbids backup wording: {term:?}")
                }
                WorkerProfileError::ForbiddenWorkerRoleTerm(term) => {
                    write!(f, "WorkerProfile forbids worker_role wording: {term:?}")
                }
                WorkerProfileError::UnknownDispatchPurpose(term) => {
                    write!(f, "unknown dispatch_purpose {term:?}")
                }
            }
        }
    }

    impl std::error::Error for WorkerProfileError {}
}
