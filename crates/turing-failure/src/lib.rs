//! Failure classification, memory, and abstract broadcast rules.
//!
//! Failure memory is derived from Micro Tape events. Broadcast rules deliberately
//! summarize failure classes and source ids; they never carry raw stack traces,
//! hidden predicates, or Goodhart-sensitive metric text.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use turing_contracts::failure::FailureClass;
use turing_contracts::identity::MicroOid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureSignals {
    pub exit_code: Option<i32>,
    pub stderr_excerpt: String,
    pub predicate_reject_class: Option<String>,
    pub tool_denied: bool,
    pub credential_signal: bool,
    pub sandbox_signal: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureClassification {
    pub failure_class: FailureClass,
    pub observed_signals: Vec<String>,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct FailureClassifier;

impl FailureClassifier {
    #[must_use]
    pub fn classify(signals: FailureSignals) -> FailureClassification {
        let mut observed = Vec::new();
        if let Some(exit_code) = signals.exit_code {
            observed.push(format!("exit_code:{exit_code}"));
        }
        if !signals.stderr_excerpt.is_empty() {
            observed.push("stderr_excerpt_present".to_string());
        }
        if let Some(reject) = signals.predicate_reject_class.as_deref() {
            observed.push(format!("predicate_reject_class:{reject}"));
        }
        if signals.tool_denied {
            observed.push("tool_denied".to_string());
        }
        if signals.credential_signal {
            observed.push("credential_signal".to_string());
        }
        if signals.sandbox_signal {
            observed.push("sandbox_signal".to_string());
        }

        let lower = signals.stderr_excerpt.to_ascii_lowercase();
        let failure_class = if signals.credential_signal || lower.contains("credential") {
            FailureClass::CredentialViolation
        } else if signals.sandbox_signal || lower.contains("sandbox") {
            FailureClass::SandboxViolation
        } else if signals.tool_denied || lower.contains("outside scope") {
            FailureClass::OverScope
        } else if matches!(signals.exit_code, Some(124)) || lower.contains("timeout") {
            FailureClass::TimeoutSoft
        } else if lower.contains("no diff") {
            FailureClass::NoDiff
        } else if lower.contains("schema") {
            FailureClass::OutputSchemaViolation
        } else if signals.exit_code.is_some_and(|code| code != 0) {
            FailureClass::UnknownNonzero
        } else {
            FailureClass::SemanticFailure
        };

        FailureClassification {
            failure_class,
            observed_signals: observed,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureTapeEvent {
    pub event_id: String,
    pub capsule_id: String,
    pub failure_class: FailureClass,
    pub detail_hash: String,
    pub raw_detail: Option<String>,
}

impl FailureTapeEvent {
    #[must_use]
    pub fn new(
        event_id: impl Into<String>,
        capsule_id: impl Into<String>,
        failure_class: FailureClass,
        detail_hash: impl Into<String>,
    ) -> Self {
        FailureTapeEvent {
            event_id: event_id.into(),
            capsule_id: capsule_id.into(),
            failure_class,
            detail_hash: detail_hash.into(),
            raw_detail: None,
        }
    }

    #[must_use]
    pub fn with_raw_detail(mut self, raw_detail: impl Into<String>) -> Self {
        self.raw_detail = Some(raw_detail.into());
        self
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureMemory {
    pub schema_id: String,
    pub source: String,
    pub clusters: Vec<FailureCluster>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureCluster {
    pub failure_class: FailureClass,
    pub count: usize,
    pub repeated: bool,
    pub capsule_ids: Vec<String>,
    pub source_failure_nodes: Vec<String>,
    pub detail_hashes: Vec<String>,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct MemoryReducer;

impl MemoryReducer {
    pub fn from_tape_events(events: &[FailureTapeEvent]) -> Result<FailureMemory, FailureError> {
        let mut grouped: BTreeMap<FailureClass, Group> = BTreeMap::new();

        for event in events {
            if MicroOid::parse(&event.event_id).is_err() {
                return Err(FailureError::InvalidFailureNodeId(event.event_id.clone()));
            }
            validate_digest(&event.detail_hash)?;
            let group = grouped.entry(event.failure_class).or_default();
            group.capsule_ids.insert(event.capsule_id.clone());
            group.source_failure_nodes.push(event.event_id.clone());
            group.detail_hashes.push(event.detail_hash.clone());
        }

        let clusters = grouped
            .into_iter()
            .map(|(failure_class, group)| {
                let count = group.source_failure_nodes.len();
                FailureCluster {
                    failure_class,
                    count,
                    repeated: count > 1,
                    capsule_ids: group.capsule_ids.into_iter().collect(),
                    source_failure_nodes: group.source_failure_nodes,
                    detail_hashes: group.detail_hashes,
                }
            })
            .collect();

        Ok(FailureMemory {
            schema_id: "failure_memory.v1".to_string(),
            source: "micro_tape_only".to_string(),
            clusters,
        })
    }
}

#[derive(Debug, Default)]
struct Group {
    capsule_ids: BTreeSet<String>,
    source_failure_nodes: Vec<String>,
    detail_hashes: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BroadcastRule {
    pub schema_id: String,
    pub rule_id: String,
    pub applies_to_capsules: Vec<String>,
    pub failure_class: FailureClass,
    pub summary: String,
    pub source_failure_nodes: Vec<String>,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct BroadcastReducer;

impl BroadcastReducer {
    pub fn from_cluster(cluster: &FailureCluster) -> Result<BroadcastRule, FailureError> {
        if cluster.source_failure_nodes.is_empty() {
            return Err(FailureError::EmptyCluster);
        }
        let summary = abstract_summary(cluster.failure_class, cluster.repeated);
        assert_no_forbidden_broadcast_text(&summary)?;
        Ok(BroadcastRule {
            schema_id: "broadcast_rule.v1".to_string(),
            rule_id: format!(
                "br_{}_{}",
                cluster.failure_class.as_registry_str().to_ascii_lowercase(),
                cluster.source_failure_nodes.len()
            ),
            applies_to_capsules: cluster.capsule_ids.clone(),
            failure_class: cluster.failure_class,
            summary,
            source_failure_nodes: cluster.source_failure_nodes.clone(),
        })
    }
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct RuleShield;

impl RuleShield {
    #[must_use]
    pub fn select_for_capsule(rules: &[BroadcastRule], capsule_id: &str) -> Vec<BroadcastRule> {
        rules
            .iter()
            .filter(|rule| {
                rule.applies_to_capsules
                    .iter()
                    .any(|candidate| candidate == capsule_id)
            })
            .cloned()
            .collect()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FailureError {
    InvalidFailureNodeId(String),
    InvalidDigest(String),
    EmptyCluster,
    ForbiddenBroadcastText(String),
}

impl std::fmt::Display for FailureError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FailureError::InvalidFailureNodeId(id) => write!(f, "invalid FailureNode id {id:?}"),
            FailureError::InvalidDigest(digest) => write!(f, "invalid digest {digest:?}"),
            FailureError::EmptyCluster => write!(f, "cannot broadcast an empty failure cluster"),
            FailureError::ForbiddenBroadcastText(marker) => {
                write!(
                    f,
                    "broadcast rule contains forbidden text marker {marker:?}"
                )
            }
        }
    }
}

impl std::error::Error for FailureError {}

fn abstract_summary(failure_class: FailureClass, repeated: bool) -> String {
    let base = match failure_class {
        FailureClass::AuthRequired => "Route this action to human authorization before retry.",
        FailureClass::TimeoutSoft
        | FailureClass::TimeoutHard
        | FailureClass::TimeoutOrNetworkRetry => {
            "Prefer a smaller command surface and explicit timeout budget before retry."
        }
        FailureClass::OutputSchemaViolation => {
            "Validate the declared output schema before dispatch completion."
        }
        FailureClass::NoDiff => "Require a concrete diff or a typed no-change explanation.",
        FailureClass::WrongDiff => "Recheck allowed files and expected patch scope before retry.",
        FailureClass::DirtyWorktree => "Start from a clean isolated worktree before dispatch.",
        FailureClass::AmbiguousMutation => "Split the mutation into a narrower capsule.",
        FailureClass::ResumeUnavailable => "Rebuild context from Tape before resuming the branch.",
        FailureClass::SteerRejected => "Wait for an amended human steer before continuing.",
        FailureClass::UnknownNonzero => {
            "Capture the failing command class and reduce command scope."
        }
        FailureClass::SemanticFailure => {
            "Re-evaluate acceptance intent before proposing another patch."
        }
        FailureClass::OverScope => "Narrow grants and allowed paths before retry.",
        FailureClass::CredentialViolation => {
            "Remove credential material from worker-visible context."
        }
        FailureClass::SandboxViolation => "Constrain execution to the declared sandbox profile.",
        FailureClass::ObserverMismatch => "Re-import macro evidence before predicate evaluation.",
    };
    if repeated {
        format!("Repeated pattern: {base}")
    } else {
        base.to_string()
    }
}

fn assert_no_forbidden_broadcast_text(text: &str) -> Result<(), FailureError> {
    let lower = text.to_ascii_lowercase();
    for marker in [
        "traceback",
        "hidden_predicate",
        "hidden predicate",
        "pput",
        "vpput",
        "progress /",
    ] {
        if lower.contains(marker) {
            return Err(FailureError::ForbiddenBroadcastText(marker.to_string()));
        }
    }
    Ok(())
}

fn validate_digest(value: &str) -> Result<(), FailureError> {
    let rest = value
        .strip_prefix("sha256:")
        .ok_or_else(|| FailureError::InvalidDigest(value.to_string()))?;
    if rest.len() != 64 || !rest.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(FailureError::InvalidDigest(value.to_string()));
    }
    Ok(())
}
