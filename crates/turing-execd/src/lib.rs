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
            let worker_id = worker_id.into();
            if !super::is_hash_worker_id(&worker_id) {
                return Err(WorkerProfileError::InvalidWorkerId(worker_id));
            }
            Ok(WorkerProfile {
                worker_id,
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
        InvalidWorkerId(String),
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
                WorkerProfileError::InvalidWorkerId(worker_id) => write!(
                    f,
                    "WorkerProfile worker_id must match worker:sha256:<64 lowercase hex>, got {worker_id:?}"
                ),
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

fn is_hash_worker_id(worker_id: &str) -> bool {
    let Some(hex) = worker_id.strip_prefix("worker:sha256:") else {
        return false;
    };
    hex.len() == 64
        && hex
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

pub mod capability {
    use std::path::{Component, Path};

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct CapabilityGrant {
        pub grant_id: String,
        pub capsule_id: String,
        pub agent_id: String,
        pub market_id: Option<String>,
        pub budget: Budget,
        pub scope: CapabilityScope,
        pub risk: Risk,
        pub authorization_event: Option<String>,
        pub signature_route: SignatureRoute,
    }

    impl CapabilityGrant {
        pub fn authorize(&self, request: &ToolRequest) -> Result<(), GrantError> {
            if !self.scope.allowed_tools.contains(&request.tool) {
                return Err(GrantError::ToolDenied(request.tool.clone()));
            }

            if let Some(path) = request.path.as_deref() {
                validate_relative_path(path)?;
                if self
                    .scope
                    .forbidden_paths
                    .iter()
                    .any(|forbidden| path_is_within(path, forbidden))
                {
                    return Err(GrantError::ForbiddenPath(path.to_string()));
                }
                if !self
                    .scope
                    .allowed_paths
                    .iter()
                    .any(|allowed| path_is_within(path, allowed))
                {
                    return Err(GrantError::PathOutsideScope(path.to_string()));
                }
            }

            if request.requested_tool_call_index > self.budget.max_tool_calls {
                return Err(GrantError::ToolCallBudgetExceeded {
                    requested: request.requested_tool_call_index,
                    max: self.budget.max_tool_calls,
                });
            }
            if request.mutated_files_after > self.budget.max_mutated_files {
                return Err(GrantError::MutatedFileBudgetExceeded {
                    requested: request.mutated_files_after,
                    max: self.budget.max_mutated_files,
                });
            }
            if request.needs_network && self.scope.network == NetworkScope::Denied {
                return Err(GrantError::NetworkDenied);
            }
            if request.action == ActionClass::IrreversibleMacro
                && (self.authorization_event.is_none()
                    || self.signature_route == SignatureRoute::None)
            {
                return Err(GrantError::IrreversibleActionNeedsAuthorization);
            }

            Ok(())
        }
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct Budget {
        pub max_tokens: u64,
        pub max_wall_time_ms: u64,
        pub max_tool_calls: u64,
        pub max_mutated_files: u64,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct CapabilityScope {
        pub allowed_paths: Vec<String>,
        pub forbidden_paths: Vec<String>,
        pub allowed_tools: Vec<String>,
        pub network: NetworkScope,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum NetworkScope {
        Denied,
        Allowlist,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum RiskClass {
        P0,
        P1,
        P2,
        P3,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub struct Risk {
        pub risk_class: RiskClass,
        pub human_before_dispatch: bool,
        pub human_before_accept: bool,
        pub human_before_merge: bool,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum SignatureRoute {
        None,
        OsKeyring,
        HardwareFuture,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum ActionClass {
        FileRead,
        FileWrite,
        Command,
        IrreversibleMacro,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct ToolRequest {
        pub tool: String,
        pub path: Option<String>,
        pub action: ActionClass,
        pub mutates: bool,
        pub requested_tool_call_index: u64,
        pub mutated_files_after: u64,
        pub needs_network: bool,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum GrantError {
        ToolDenied(String),
        PathTraversal(String),
        ForbiddenPath(String),
        PathOutsideScope(String),
        ToolCallBudgetExceeded { requested: u64, max: u64 },
        MutatedFileBudgetExceeded { requested: u64, max: u64 },
        NetworkDenied,
        IrreversibleActionNeedsAuthorization,
    }

    impl std::fmt::Display for GrantError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                GrantError::ToolDenied(tool) => write!(f, "tool {tool:?} is outside grant scope"),
                GrantError::PathTraversal(path) => {
                    write!(f, "path {path:?} escapes the worktree")
                }
                GrantError::ForbiddenPath(path) => write!(f, "path {path:?} is forbidden"),
                GrantError::PathOutsideScope(path) => {
                    write!(f, "path {path:?} is outside allowed scope")
                }
                GrantError::ToolCallBudgetExceeded { requested, max } => {
                    write!(
                        f,
                        "tool call budget exceeded: requested {requested}, max {max}"
                    )
                }
                GrantError::MutatedFileBudgetExceeded { requested, max } => write!(
                    f,
                    "mutated file budget exceeded: requested {requested}, max {max}"
                ),
                GrantError::NetworkDenied => write!(f, "network access denied by grant"),
                GrantError::IrreversibleActionNeedsAuthorization => {
                    write!(
                        f,
                        "irreversible macro action requires authorization and signature"
                    )
                }
            }
        }
    }

    impl std::error::Error for GrantError {}

    fn validate_relative_path(path: &str) -> Result<(), GrantError> {
        let parsed = Path::new(path);
        for component in parsed.components() {
            match component {
                Component::ParentDir | Component::RootDir | Component::Prefix(_) => {
                    return Err(GrantError::PathTraversal(path.to_string()));
                }
                Component::CurDir | Component::Normal(_) => {}
            }
        }
        Ok(())
    }

    fn path_is_within(path: &str, root: &str) -> bool {
        let path = Path::new(path);
        let root = Path::new(root);
        path == root || path.starts_with(root)
    }
}

#[cfg(unix)]
pub mod process {
    use std::io;
    use std::os::unix::process::CommandExt;
    use std::process::{Command, Stdio};
    use std::thread;
    use std::time::{Duration, Instant};

    use turing_contracts::jcs;

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct ProcessSpec {
        pub program: String,
        pub args: Vec<String>,
        pub timeout: Duration,
        pub term_grace: Duration,
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum TimeoutClass {
        None,
        Soft,
        Hard,
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct ProcessGroupReceipt {
        pub timeout_class: TimeoutClass,
        pub term_sent: bool,
        pub kill_sent: bool,
        pub no_orphans: bool,
        pub exit_code: Option<i32>,
        pub stdout_hash: String,
        pub stderr_hash: String,
        pub elapsed: Duration,
    }

    #[derive(Debug)]
    pub enum ProcessError {
        Spawn(io::Error),
        Wait(io::Error),
        Signal(io::Error),
    }

    impl std::fmt::Display for ProcessError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                ProcessError::Spawn(e) => write!(f, "process spawn failed: {e}"),
                ProcessError::Wait(e) => write!(f, "process wait failed: {e}"),
                ProcessError::Signal(e) => write!(f, "process-group signal failed: {e}"),
            }
        }
    }

    impl std::error::Error for ProcessError {}

    #[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
    pub struct ProcessGroupRunner;

    impl ProcessGroupRunner {
        #[must_use]
        pub fn new() -> Self {
            ProcessGroupRunner
        }

        pub fn run(&self, spec: ProcessSpec) -> Result<ProcessGroupReceipt, ProcessError> {
            let start = Instant::now();
            let mut child = Command::new(&spec.program)
                .args(&spec.args)
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .process_group(0)
                .spawn()
                .map_err(ProcessError::Spawn)?;
            let pgid = child.id();

            let mut term_sent = false;
            let mut kill_sent = false;
            let mut timeout_class = TimeoutClass::None;

            loop {
                if child.try_wait().map_err(ProcessError::Wait)?.is_some() {
                    break;
                }
                if start.elapsed() >= spec.timeout {
                    term_sent = true;
                    timeout_class = TimeoutClass::Soft;
                    signal_group(pgid, "-TERM").map_err(ProcessError::Signal)?;
                    thread::sleep(spec.term_grace);
                    if child.try_wait().map_err(ProcessError::Wait)?.is_none() {
                        kill_sent = true;
                        timeout_class = TimeoutClass::Hard;
                        signal_group(pgid, "-KILL").map_err(ProcessError::Signal)?;
                    }
                    break;
                }
                thread::sleep(Duration::from_millis(10));
            }

            let output = child.wait_with_output().map_err(ProcessError::Wait)?;
            let no_orphans = wait_for_empty_group(pgid, Duration::from_secs(1));

            Ok(ProcessGroupReceipt {
                timeout_class,
                term_sent,
                kill_sent,
                no_orphans,
                exit_code: output.status.code(),
                stdout_hash: hash_bytes(&output.stdout),
                stderr_hash: hash_bytes(&output.stderr),
                elapsed: start.elapsed(),
            })
        }
    }

    fn signal_group(pgid: u32, signal: &str) -> io::Result<()> {
        let status = Command::new("kill")
            .arg(signal)
            .arg("--")
            .arg(format!("-{pgid}"))
            .status()?;
        if status.success() {
            Ok(())
        } else {
            Err(io::Error::other(format!(
                "kill {signal} process group {pgid} exited with {status}"
            )))
        }
    }

    fn wait_for_empty_group(pgid: u32, timeout: Duration) -> bool {
        let start = Instant::now();
        while start.elapsed() < timeout {
            if process_group_empty(pgid) {
                return true;
            }
            thread::sleep(Duration::from_millis(10));
        }
        process_group_empty(pgid)
    }

    fn process_group_empty(pgid: u32) -> bool {
        match Command::new("kill")
            .arg("-0")
            .arg("--")
            .arg(format!("-{pgid}"))
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
        {
            Ok(status) => !status.success(),
            Err(_) => false,
        }
    }

    fn hash_bytes(bytes: &[u8]) -> String {
        format!("sha256:{}", jcs::sha256_hex(bytes))
    }
}

pub mod macro_worktree {
    use std::path::{Path, PathBuf};
    use std::process::Command;

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct MacroWorktreeManager {
        repo_root: PathBuf,
        worktrees_root: PathBuf,
    }

    impl MacroWorktreeManager {
        #[must_use]
        pub fn new(repo_root: impl AsRef<Path>, worktrees_root: impl AsRef<Path>) -> Self {
            MacroWorktreeManager {
                repo_root: repo_root.as_ref().to_path_buf(),
                worktrees_root: worktrees_root.as_ref().to_path_buf(),
            }
        }

        pub fn create_for_capsule(
            &self,
            capsule_id: &str,
        ) -> Result<MacroWorktree, MacroWorktreeError> {
            let safe_capsule_id = safe_capsule_id(capsule_id)?;
            let path = self.worktrees_root.join(&safe_capsule_id);
            if path == self.repo_root {
                return Err(MacroWorktreeError::NotIsolated(path));
            }
            std::fs::create_dir_all(&self.worktrees_root)
                .map_err(MacroWorktreeError::CreateWorktreeRoot)?;

            let branch = format!("turingos/{safe_capsule_id}");
            run_git(
                &self.repo_root,
                &[
                    "worktree",
                    "add",
                    "-B",
                    &branch,
                    path.to_str()
                        .ok_or_else(|| MacroWorktreeError::NonUtf8Path(path.clone()))?,
                    "HEAD",
                ],
            )?;

            Ok(MacroWorktree {
                capsule_id: safe_capsule_id,
                path,
                branch,
            })
        }
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct MacroWorktree {
        pub capsule_id: String,
        pub path: PathBuf,
        pub branch: String,
    }

    impl MacroWorktree {
        #[must_use]
        pub fn is_isolated_from(&self, repo_root: &Path) -> bool {
            self.path != repo_root
        }
    }

    #[derive(Debug)]
    pub enum MacroWorktreeError {
        EmptyCapsuleId,
        UnsafeCapsuleId(String),
        NotIsolated(PathBuf),
        NonUtf8Path(PathBuf),
        CreateWorktreeRoot(std::io::Error),
        Git { args: Vec<String>, stderr: String },
    }

    impl std::fmt::Display for MacroWorktreeError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                MacroWorktreeError::EmptyCapsuleId => write!(f, "capsule_id must not be empty"),
                MacroWorktreeError::UnsafeCapsuleId(id) => {
                    write!(f, "unsafe capsule_id for worktree path: {id:?}")
                }
                MacroWorktreeError::NotIsolated(path) => {
                    write!(f, "worktree path {path:?} is not isolated from repo root")
                }
                MacroWorktreeError::NonUtf8Path(path) => write!(f, "non-UTF-8 path {path:?}"),
                MacroWorktreeError::CreateWorktreeRoot(e) => {
                    write!(f, "failed to create worktree root: {e}")
                }
                MacroWorktreeError::Git { args, stderr } => {
                    write!(f, "git {args:?} failed: {}", stderr.trim())
                }
            }
        }
    }

    impl std::error::Error for MacroWorktreeError {
        fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
            match self {
                MacroWorktreeError::CreateWorktreeRoot(e) => Some(e),
                _ => None,
            }
        }
    }

    fn safe_capsule_id(capsule_id: &str) -> Result<String, MacroWorktreeError> {
        if capsule_id.is_empty() {
            return Err(MacroWorktreeError::EmptyCapsuleId);
        }
        let safe = capsule_id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-');
        if !safe {
            return Err(MacroWorktreeError::UnsafeCapsuleId(capsule_id.to_string()));
        }
        Ok(capsule_id.to_string())
    }

    fn run_git(repo: &Path, args: &[&str]) -> Result<(), MacroWorktreeError> {
        let output = Command::new("git")
            .arg("-C")
            .arg(repo)
            .args(args)
            .env("GIT_CONFIG_NOSYSTEM", "1")
            .env("GIT_CONFIG_GLOBAL", "/dev/null")
            .env("GIT_TERMINAL_PROMPT", "0")
            .output()
            .map_err(|e| MacroWorktreeError::Git {
                args: args.iter().map(|a| (*a).to_string()).collect(),
                stderr: e.to_string(),
            })?;
        if output.status.success() {
            Ok(())
        } else {
            Err(MacroWorktreeError::Git {
                args: args.iter().map(|a| (*a).to_string()).collect(),
                stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
            })
        }
    }
}

pub mod macro_anchor {
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum MacroAnchorKind {
        Diff,
        Branch,
        Pr,
        Ci,
        TuringDone,
    }

    impl MacroAnchorKind {
        #[must_use]
        pub fn as_str(self) -> &'static str {
            match self {
                MacroAnchorKind::Diff => "diff",
                MacroAnchorKind::Branch => "branch",
                MacroAnchorKind::Pr => "pr",
                MacroAnchorKind::Ci => "ci",
                MacroAnchorKind::TuringDone => "turing_done",
            }
        }

        fn parse(raw: &str) -> Result<Self, MacroAnchorError> {
            match raw {
                "diff" => Ok(MacroAnchorKind::Diff),
                "branch" => Ok(MacroAnchorKind::Branch),
                "pr" => Ok(MacroAnchorKind::Pr),
                "ci" => Ok(MacroAnchorKind::Ci),
                "turing_done" => Ok(MacroAnchorKind::TuringDone),
                other => Err(MacroAnchorError::UnknownKind(other.to_string())),
            }
        }
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct MacroAnchor {
        raw: String,
        kind: MacroAnchorKind,
    }

    impl MacroAnchor {
        pub fn new(kind: MacroAnchorKind, object: &str) -> Result<Self, MacroAnchorError> {
            if object.is_empty() {
                return Err(MacroAnchorError::EmptyObject);
            }
            if object.starts_with("mu:") {
                return Err(MacroAnchorError::MicroIdentityRejected);
            }
            MacroAnchor::parse(&format!("macro:{}:{object}", kind.as_str()))
        }

        pub fn parse(raw: &str) -> Result<Self, MacroAnchorError> {
            if raw.starts_with("mu:") {
                return Err(MacroAnchorError::MicroIdentityRejected);
            }
            let rest = raw
                .strip_prefix("macro:")
                .ok_or_else(|| MacroAnchorError::MissingMacroPrefix(raw.to_string()))?;
            let (kind_raw, object) = rest
                .split_once(':')
                .ok_or_else(|| MacroAnchorError::Malformed(raw.to_string()))?;
            if object.is_empty() {
                return Err(MacroAnchorError::EmptyObject);
            }
            if object.starts_with("mu:") {
                return Err(MacroAnchorError::MicroIdentityRejected);
            }
            let kind = MacroAnchorKind::parse(kind_raw)?;
            Ok(MacroAnchor {
                raw: raw.to_string(),
                kind,
            })
        }

        #[must_use]
        pub fn as_str(&self) -> &str {
            &self.raw
        }

        #[must_use]
        pub fn kind(&self) -> MacroAnchorKind {
            self.kind
        }

        #[must_use]
        pub fn is_micro_identity(&self) -> bool {
            self.raw.starts_with("mu:")
        }
    }

    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum MacroAnchorError {
        MicroIdentityRejected,
        MissingMacroPrefix(String),
        UnknownKind(String),
        EmptyObject,
        Malformed(String),
    }

    impl std::fmt::Display for MacroAnchorError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                MacroAnchorError::MicroIdentityRejected => {
                    write!(f, "macro anchor cannot be a Micro mu: identity")
                }
                MacroAnchorError::MissingMacroPrefix(raw) => {
                    write!(f, "macro anchor {raw:?} must start with macro:")
                }
                MacroAnchorError::UnknownKind(kind) => {
                    write!(f, "unknown macro anchor kind {kind:?}")
                }
                MacroAnchorError::EmptyObject => write!(f, "macro anchor object must not be empty"),
                MacroAnchorError::Malformed(raw) => write!(f, "malformed macro anchor {raw:?}"),
            }
        }
    }

    impl std::error::Error for MacroAnchorError {}
}

use serde_json::json;
use turing_contracts::jcs;
use workers::{
    AuthSurface, DispatchPurpose, FailureDomain, Provenance, WorkerKind, WorkerProfile,
    WorkerProfileError,
};

const FIXED_RECEIPT_TIME: &str = "2026-01-01T00:00:00Z";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkerRunRequest {
    pub capsule_id: String,
    pub grant_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ManualCompletion {
    pub stdout: String,
    pub stderr: String,
    pub diff: Option<String>,
    pub done_json: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExecutionReceipt {
    pub schema_id: String,
    pub receipt_id: String,
    pub capsule_id: String,
    pub worker_id: String,
    pub grant_id: String,
    pub started_at: String,
    pub finished_at: String,
    pub exit_code: Option<i32>,
    pub timeout_class: String,
    pub stdout_hash: String,
    pub stderr_hash: String,
    pub diff_hash: Option<String>,
    pub done_json_hash: Option<String>,
    pub observer_measurement_hash: String,
    pub observation_agreement: String,
    pub provenance: Provenance,
    pub credential_material_absent: bool,
    pub micro_refs_moved: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkerRunError {
    Profile(WorkerProfileError),
    ReceiptHash(String),
    HiddenWorkerPromptMarker(String),
}

impl std::fmt::Display for WorkerRunError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WorkerRunError::Profile(e) => write!(f, "worker profile error: {e}"),
            WorkerRunError::ReceiptHash(e) => write!(f, "receipt hash error: {e}"),
            WorkerRunError::HiddenWorkerPromptMarker(marker) => {
                write!(f, "worker prompt contains hidden marker {marker:?}")
            }
        }
    }
}

impl std::error::Error for WorkerRunError {}

impl From<WorkerProfileError> for WorkerRunError {
    fn from(e: WorkerProfileError) -> Self {
        WorkerRunError::Profile(e)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FakeWorker {
    profile: WorkerProfile,
}

impl FakeWorker {
    #[must_use]
    pub fn new(worker_id: impl Into<String>) -> Self {
        Self::try_new(worker_id).expect("built-in FULL local fake worker profile is valid")
    }

    pub fn try_new(worker_id: impl Into<String>) -> Result<Self, WorkerRunError> {
        let profile = try_full_local_profile(worker_id, WorkerKind::Fake, "fake")?;
        Ok(FakeWorker { profile })
    }

    #[must_use]
    pub fn profile(&self) -> &WorkerProfile {
        &self.profile
    }

    pub fn run(&self, request: WorkerRunRequest) -> Result<ExecutionReceipt, WorkerRunError> {
        build_receipt(
            &self.profile,
            request,
            "fake worker completed\n",
            "",
            None,
            Some(r#"{"status":"done","worker":"fake"}"#),
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ManualCopyPasteWorker {
    profile: WorkerProfile,
}

impl ManualCopyPasteWorker {
    #[must_use]
    pub fn new(worker_id: impl Into<String>) -> Self {
        Self::try_new(worker_id).expect("built-in FULL local manual worker profile is valid")
    }

    pub fn try_new(worker_id: impl Into<String>) -> Result<Self, WorkerRunError> {
        let profile = try_full_local_profile(worker_id, WorkerKind::Manual, "manual")?;
        Ok(ManualCopyPasteWorker { profile })
    }

    #[must_use]
    pub fn profile(&self) -> &WorkerProfile {
        &self.profile
    }

    pub fn complete(
        &self,
        request: WorkerRunRequest,
        completion: ManualCompletion,
    ) -> Result<ExecutionReceipt, WorkerRunError> {
        build_receipt(
            &self.profile,
            request,
            &completion.stdout,
            &completion.stderr,
            completion.diff.as_deref(),
            completion.done_json.as_deref(),
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrokHeadlessConfig {
    pub binary: String,
    pub output_format: String,
}

impl Default for GrokHeadlessConfig {
    fn default() -> Self {
        GrokHeadlessConfig {
            binary: "grok".to_string(),
            output_format: "plain".to_string(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrokHeadlessRequest {
    pub capsule_id: String,
    pub worktree: String,
    pub visible_capsule: String,
    pub model: String,
    pub max_turns: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrokHeadlessCommandPlan {
    pub argv: Vec<String>,
    pub prompt: String,
    pub prompt_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrokHeadlessWorker {
    profile: WorkerProfile,
    config: GrokHeadlessConfig,
}

impl GrokHeadlessWorker {
    #[must_use]
    pub fn worker_id_for(model: &str) -> String {
        let value = json!({
            "schema_id": "worker_identity_seed.v1",
            "provider": "grok",
            "kind": "CommandTemplate",
            "model": model,
            "thinking_mode": "no_plan_no_memory_no_subagents_plain_output",
        });
        let bytes = jcs::canonicalize(&value).expect("worker identity seed is canonical JSON");
        format!("worker:sha256:{}", jcs::sha256_hex(&bytes))
    }

    pub fn try_new(worker_id: impl Into<String>) -> Result<Self, WorkerRunError> {
        Self::try_new_with_config(worker_id, GrokHeadlessConfig::default())
    }

    pub fn try_new_with_config(
        worker_id: impl Into<String>,
        config: GrokHeadlessConfig,
    ) -> Result<Self, WorkerRunError> {
        let profile = WorkerProfile::vendor_bundle(
            worker_id,
            WorkerKind::CommandTemplate,
            vec![DispatchPurpose::PrimaryExecution],
            vec!["code_edit".to_string(), "test_run".to_string()],
            FailureDomain {
                provider: "grok".to_string(),
                auth_surface: AuthSurface::LocalCli,
                network_required: true,
            },
        )?;
        Ok(GrokHeadlessWorker { profile, config })
    }

    #[must_use]
    pub fn profile(&self) -> &WorkerProfile {
        &self.profile
    }

    pub fn command_plan(
        &self,
        request: GrokHeadlessRequest,
    ) -> Result<GrokHeadlessCommandPlan, WorkerRunError> {
        reject_hidden_worker_prompt_markers(&request.visible_capsule)?;
        let prompt = build_grok_visible_prompt(&request);
        let prompt_hash = hash_str(&prompt);
        let argv = vec![
            self.config.binary.clone(),
            "-p".to_string(),
            prompt.clone(),
            "--cwd".to_string(),
            request.worktree,
            "--output-format".to_string(),
            self.config.output_format.clone(),
            "--model".to_string(),
            request.model,
            "--always-approve".to_string(),
            "--disable-web-search".to_string(),
            "--no-plan".to_string(),
            "--no-memory".to_string(),
            "--no-subagents".to_string(),
            "--max-turns".to_string(),
            request.max_turns.to_string(),
            "--verbatim".to_string(),
        ];
        Ok(GrokHeadlessCommandPlan {
            argv,
            prompt,
            prompt_hash,
        })
    }
}

fn reject_hidden_worker_prompt_markers(prompt: &str) -> Result<(), WorkerRunError> {
    let lower = prompt.to_ascii_lowercase();
    for marker in [
        "hidden predicate",
        "hidden predicates",
        "pput",
        "heldout",
        "golden path",
        "raw failure log",
        "metric file",
    ] {
        if lower.contains(marker) {
            return Err(WorkerRunError::HiddenWorkerPromptMarker(marker.to_string()));
        }
    }
    Ok(())
}

fn build_grok_visible_prompt(request: &GrokHeadlessRequest) -> String {
    format!(
        concat!(
            "You are a TuringOS headless Macro Worker.\n",
            "Capsule: {capsule_id}\n",
            "Do not output chain-of-thought, private scratchpads, or model deliberation.\n",
            "TuringOS Micro Tape records the external progress trace; report only observable edits, commands, and results.\n",
            "Use only the visible capsule below.\n\n",
            "{visible_capsule}\n"
        ),
        capsule_id = request.capsule_id,
        visible_capsule = request.visible_capsule
    )
}

fn try_full_local_profile(
    worker_id: impl Into<String>,
    kind: WorkerKind,
    provider: &str,
) -> Result<WorkerProfile, WorkerProfileError> {
    WorkerProfile::new(
        worker_id,
        kind,
        Provenance::Full,
        vec![DispatchPurpose::OfflineBootstrap],
        vec!["test_run".to_string(), "doc_update".to_string()],
        Some(FailureDomain {
            provider: provider.to_string(),
            auth_surface: AuthSurface::None,
            network_required: false,
        }),
    )
}

fn build_receipt(
    profile: &WorkerProfile,
    request: WorkerRunRequest,
    stdout: &str,
    stderr: &str,
    diff: Option<&str>,
    done_json: Option<&str>,
) -> Result<ExecutionReceipt, WorkerRunError> {
    let stdout_hash = hash_str(stdout);
    let stderr_hash = hash_str(stderr);
    let diff_hash = diff.map(hash_str);
    let done_json_hash = done_json.map(hash_str);
    let observer_measurement_hash = hash_str(&format!(
        "{stdout_hash}|{stderr_hash}|{}|{}",
        diff_hash.as_deref().unwrap_or("null"),
        done_json_hash.as_deref().unwrap_or("null")
    ));
    let receipt_id = receipt_id(
        &request,
        &profile.worker_id,
        &stdout_hash,
        &stderr_hash,
        diff_hash.as_deref(),
        done_json_hash.as_deref(),
    )?;

    Ok(ExecutionReceipt {
        schema_id: "execution_receipt.v1".to_string(),
        receipt_id,
        capsule_id: request.capsule_id,
        worker_id: profile.worker_id.clone(),
        grant_id: request.grant_id,
        started_at: FIXED_RECEIPT_TIME.to_string(),
        finished_at: FIXED_RECEIPT_TIME.to_string(),
        exit_code: Some(0),
        timeout_class: "none".to_string(),
        stdout_hash,
        stderr_hash,
        diff_hash,
        done_json_hash,
        observer_measurement_hash,
        observation_agreement: "Match".to_string(),
        provenance: profile.provenance,
        credential_material_absent: true,
        micro_refs_moved: false,
    })
}

fn receipt_id(
    request: &WorkerRunRequest,
    worker_id: &str,
    stdout_hash: &str,
    stderr_hash: &str,
    diff_hash: Option<&str>,
    done_json_hash: Option<&str>,
) -> Result<String, WorkerRunError> {
    let value = json!({
        "schema_id": "execution_receipt_identity.v1",
        "capsule_id": request.capsule_id,
        "grant_id": request.grant_id,
        "worker_id": worker_id,
        "stdout_hash": stdout_hash,
        "stderr_hash": stderr_hash,
        "diff_hash": diff_hash,
        "done_json_hash": done_json_hash,
    });
    let bytes =
        jcs::canonicalize(&value).map_err(|e| WorkerRunError::ReceiptHash(e.to_string()))?;
    Ok(format!("rcp_{}", jcs::sha256_hex(&bytes)))
}

fn hash_str(s: &str) -> String {
    format!("sha256:{}", jcs::sha256_hex(s.as_bytes()))
}
