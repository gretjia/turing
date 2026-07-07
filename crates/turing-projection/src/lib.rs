//! Disposable projection builder and typed view commands.
//!
//! Projections are disposable views. They can be rebuilt from Micro Tape and never
//! expose a direct write path to Micro truth.

use serde::{Deserialize, Serialize};
use turing_contracts::identity::MicroOid;
use turing_contracts::jcs;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProjectionEvent {
    pub event_id: String,
    pub event_type: String,
    pub subject_id: String,
}

impl ProjectionEvent {
    #[must_use]
    pub fn new(
        event_id: impl Into<String>,
        event_type: impl Into<String>,
        subject_id: impl Into<String>,
    ) -> Self {
        ProjectionEvent {
            event_id: event_id.into(),
            event_type: event_type.into(),
            subject_id: subject_id.into(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProjectionSource {
    MicroTape(Vec<ProjectionEvent>),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectionBuilder {
    source: ProjectionSource,
}

impl ProjectionBuilder {
    #[must_use]
    pub fn from_source(source: ProjectionSource) -> Self {
        ProjectionBuilder { source }
    }

    pub fn build(&self) -> Result<Projection, ProjectionError> {
        let ProjectionSource::MicroTape(events) = &self.source;
        let mut sorted = events.clone();
        sorted.sort_by(|a, b| a.event_id.cmp(&b.event_id));
        for event in &sorted {
            if MicroOid::parse(&event.event_id).is_err() {
                return Err(ProjectionError::InvalidMicroEventId(event.event_id.clone()));
            }
        }
        let market_event_count = sorted
            .iter()
            .filter(|event| event.event_type.starts_with("Market"))
            .count();
        let pput_event_count = sorted
            .iter()
            .filter(|event| event.event_type.starts_with("PPUT") || event.event_type == "CostEvent")
            .count();
        let preimage = serde_json::json!({
            "schema_id": "projection.v1",
            "source": "micro_tape_only",
            "events": sorted,
            "market_event_count": market_event_count,
            "pput_event_count": pput_event_count,
            "can_write_truth": false,
        });
        let bytes = jcs::canonicalize(&preimage)
            .map_err(|error| ProjectionError::Canonicalization(error.to_string()))?;
        Ok(Projection {
            schema_id: "projection.v1".to_string(),
            source: "micro_tape_only".to_string(),
            event_count: events.len(),
            market_event_count,
            pput_event_count,
            can_write_truth: false,
            projection_hash: format!("sha256:{}", jcs::sha256_hex(&bytes)),
        })
    }

    #[must_use]
    pub fn render_macro_status(status: &str) -> String {
        format!(
            "{status}; macro result is external evidence until Micro predicate/approval accepts it"
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorSnapshotSource {
    pub project_root: String,
    pub micro_repo: String,
    pub source_kind: String,
    pub projection_version: String,
    pub rebuild_command: String,
    pub can_write_truth: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorHeads {
    pub tape_tip: String,
    pub authorization_head: Option<String>,
    pub accepted_head: String,
}

impl OperatorHeads {
    pub fn new(
        tape_tip: impl Into<String>,
        authorization_head: Option<impl Into<String>>,
        accepted_head: impl Into<String>,
    ) -> Result<Self, ProjectionError> {
        let heads = OperatorHeads {
            tape_tip: tape_tip.into(),
            authorization_head: authorization_head.map(Into::into),
            accepted_head: accepted_head.into(),
        };
        MicroOid::parse(&heads.tape_tip)
            .map_err(|_| ProjectionError::InvalidMicroEventId(heads.tape_tip.clone()))?;
        if let Some(authorization_head) = &heads.authorization_head {
            MicroOid::parse(authorization_head)
                .map_err(|_| ProjectionError::InvalidMicroEventId(authorization_head.clone()))?;
        }
        MicroOid::parse(&heads.accepted_head)
            .map_err(|_| ProjectionError::InvalidMicroEventId(heads.accepted_head.clone()))?;
        Ok(heads)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HeadConsistency {
    Consistent,
    Inconsistent,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OperatorState {
    NotBooted,
    Healthy,
    NeedsApproval,
    PendingExecution,
    AwaitingReceipt,
    EvidenceMissing,
    Blocked,
    Failed,
    StaleProjection,
    ReplayRequired,
    OutsideGovernanceObserved,
    Unknown,
}

impl OperatorState {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            OperatorState::NotBooted => "NotBooted",
            OperatorState::Healthy => "Healthy",
            OperatorState::NeedsApproval => "NeedsApproval",
            OperatorState::PendingExecution => "PendingExecution",
            OperatorState::AwaitingReceipt => "AwaitingReceipt",
            OperatorState::EvidenceMissing => "EvidenceMissing",
            OperatorState::Blocked => "Blocked",
            OperatorState::Failed => "Failed",
            OperatorState::StaleProjection => "StaleProjection",
            OperatorState::ReplayRequired => "ReplayRequired",
            OperatorState::OutsideGovernanceObserved => "OutsideGovernanceObserved",
            OperatorState::Unknown => "Unknown",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorLane {
    pub name: String,
    pub head: Option<String>,
    pub meaning: String,
}

/// The closed per-item lifecycle enum (design spec `m6_hci/DESIGN_UX_UI_DETAIL_20260705.md`
/// §2.1). Fixed glyph + fixed ASCII fallback + fixed verbatim label per stage; ordered by
/// lifecycle progression so [`WorkItemStage::rank`] can decide "did this item advance".
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkItemStage {
    Authorized,
    PendingExecution,
    AwaitingReceipt,
    ReceiptMatched,
    Accepted,
}

impl WorkItemStage {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            WorkItemStage::Authorized => "authorized",
            WorkItemStage::PendingExecution => "pending_execution",
            WorkItemStage::AwaitingReceipt => "awaiting_receipt",
            WorkItemStage::ReceiptMatched => "receipt_matched",
            WorkItemStage::Accepted => "accepted",
        }
    }

    /// The closed-bucket unicode glyph (spec 2.1 table, column 2).
    #[must_use]
    pub fn glyph(self) -> &'static str {
        match self {
            WorkItemStage::Authorized => "\u{25cf}",
            WorkItemStage::PendingExecution => "\u{25d0}",
            WorkItemStage::AwaitingReceipt => "\u{25cc}",
            WorkItemStage::ReceiptMatched => "\u{2713}",
            WorkItemStage::Accepted => "\u{25a0}",
        }
    }

    /// The closed-bucket ASCII fallback (spec 2.1 table, column 3).
    #[must_use]
    pub fn ascii_glyph(self) -> &'static str {
        match self {
            WorkItemStage::Authorized => "*",
            WorkItemStage::PendingExecution => "o",
            WorkItemStage::AwaitingReceipt => ".",
            WorkItemStage::ReceiptMatched => "v",
            WorkItemStage::Accepted => "#",
        }
    }

    /// The fixed, verbatim label (spec 2.1 table, column 4) — always printed; a renderer may
    /// add color as a third channel but never color-only (color is never load-bearing).
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            WorkItemStage::Authorized => "AUTHORIZED",
            WorkItemStage::PendingExecution => "PENDING EXECUTION",
            WorkItemStage::AwaitingReceipt => "AWAITING RECEIPT",
            WorkItemStage::ReceiptMatched => "RECEIPT MATCHED",
            WorkItemStage::Accepted => "ACCEPTED WORLD STATE",
        }
    }

    /// Every closed stage, lifecycle order — the fold order for the roll-up sentence (spec
    /// 2.4) so a stage with zero items is skippable without hand-sorting.
    #[must_use]
    pub fn all() -> [WorkItemStage; 5] {
        [
            WorkItemStage::Authorized,
            WorkItemStage::PendingExecution,
            WorkItemStage::AwaitingReceipt,
            WorkItemStage::ReceiptMatched,
            WorkItemStage::Accepted,
        ]
    }
}

/// The `receipt` field of a [`WorkItem`] — present only once a `WorkerReceiptImported` event
/// matching this item's `capsule_id` is on tape (`matched` is always `true` when this is
/// `Some`; there is no modeled "receipt present but unmatched" state).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkItemReceipt {
    pub receipt_id: String,
    pub matched: bool,
}

/// One row of the PER-ITEM SNAPSHOT CONTRACT — `operator_view_snapshot.v1`'s additive
/// `work_items` array (design spec §1 atom F3, §2, §6).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkItem {
    pub id: String,
    pub title: String,
    pub stage: WorkItemStage,
    pub claimed_complete: bool,
    pub receipt: Option<WorkItemReceipt>,
    pub blocked_reason: Option<String>,
}

/// One raw Micro Tape event, as read by a guarded tape walk (event_type + payload only —
/// heads/hashes/predicate-product are the reducer's business, not the per-item derivation's).
/// This is the input [`derive_work_items`] folds over; callers build it from a real tape walk
/// (never caller-synthesized truth — the walk itself must come from a guarded MicroTape read).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RawTapeEvent {
    pub event_type: String,
    pub payload: serde_json::Value,
}

/// Derive the closed per-item `work_items` view from a raw Micro Tape walk (design spec §1
/// atom F3; receipt-matching raw material: `tape_has_worker_receipt`,
/// `turing-daemons/src/lib.rs:1732` — same field semantics reused here, not reinvented).
///
/// **Event-type mapping (documented per the task's "no new event types" rule):**
/// - `authorized`: `WorkerDispatchAuthorized` (AUTHORIZATION class; the registry's real
///   authorization-head-moving event for a capsule dispatch).
/// - `pending_execution`: `WorkerRunStarted` (RECEIPT class; the worker's run has begun, no
///   completion has been claimed yet).
/// - `awaiting_receipt` / `claimed_complete`: **`WorkerDispatched`** — the registry has no
///   dedicated "worker claims completion" event. `WorkerDispatched` is a real closed-registry
///   event (RECEIPT class) that today is only ever used as an off-tape JSON-RPC
///   `receipt_type` label (`crates/turing-daemons/src/lib.rs:979`), never actually appended
///   to a tape. It is the closest existing event whose registry class already models "the
///   worker's own report" as distinct from the verified counterparty import
///   (`WorkerReceiptImported`), so this atom repurposes it as the tape-visible "claimed
///   complete, no receipt yet" record (spec §6's "the liar" capsule).
/// - `receipt_matched`: `WorkerReceiptImported` carrying `capsule_id` + `receipt_id` — the
///   same fields `tape_has_worker_receipt` matches on.
/// - `accepted`: `CandidateAccepted` (SOVEREIGN_ACCEPT class) carrying `capsule_id`.
/// - `title`: an optional `title` field on `WorkCapsuleBuilt`'s payload (falls back to the
///   bare `capsule_id` — the closed registry payload for `WorkCapsuleBuilt` has no title
///   field today, so this is additive/optional, never a hard requirement).
/// - `blocked_reason`: `FailureNode` carrying `capsule_id` and `blocked_reason` (or
///   `failure_class` as a fallback) on its payload. **Known limitation**: the real
///   `failure_node_payload.v1` schema (`turing_contracts::failure::FailureNodePayload`) has
///   no `capsule_id` field, so correlating a production `FailureNode` to one work item needs
///   that field added to the schema in a future atom; this derivation only picks up a
///   `FailureNode` when the field happens to be present (as the liar fixture's blocked item
///   carries it), and is a no-op otherwise (never a guess, never a crash).
///
/// An item is only emitted once at least one of the five stage-mapped events above has been
/// seen for its `capsule_id` — a bare `WorkCapsuleBuilt` proposal with no further progress
/// never appears (there is no valid closed-enum stage below `authorized`). Items are returned
/// in first-stage-reached (tape) order.
#[must_use]
pub fn derive_work_items(events: &[RawTapeEvent]) -> Vec<WorkItem> {
    #[derive(Default)]
    struct Builder {
        title: Option<String>,
        stage: Option<WorkItemStage>,
        claimed_complete: bool,
        receipt: Option<WorkItemReceipt>,
        blocked_reason: Option<String>,
    }

    fn get_or_insert<'a>(
        builders: &'a mut std::collections::HashMap<String, Builder>,
        order: &mut Vec<String>,
        capsule_id: &str,
    ) -> &'a mut Builder {
        if !builders.contains_key(capsule_id) {
            order.push(capsule_id.to_string());
        }
        builders.entry(capsule_id.to_string()).or_default()
    }

    fn upgrade(current: &mut Option<WorkItemStage>, candidate: WorkItemStage) {
        let should_upgrade = match current {
            None => true,
            Some(existing) => candidate > *existing,
        };
        if should_upgrade {
            *current = Some(candidate);
        }
    }

    let mut order: Vec<String> = Vec::new();
    let mut builders: std::collections::HashMap<String, Builder> = std::collections::HashMap::new();

    for event in events {
        let Some(capsule_id) = event.payload.get("capsule_id").and_then(serde_json::Value::as_str)
        else {
            continue;
        };
        match event.event_type.as_str() {
            "WorkCapsuleBuilt" => {
                let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                if let Some(title) = event.payload.get("title").and_then(serde_json::Value::as_str)
                {
                    entry.title = Some(title.to_string());
                }
            }
            "WorkerDispatchAuthorized" => {
                let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                upgrade(&mut entry.stage, WorkItemStage::Authorized);
            }
            "WorkerRunStarted" => {
                let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                upgrade(&mut entry.stage, WorkItemStage::PendingExecution);
            }
            "WorkerDispatched" => {
                let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                upgrade(&mut entry.stage, WorkItemStage::AwaitingReceipt);
                entry.claimed_complete = true;
            }
            "WorkerReceiptImported" => {
                if let Some(receipt_id) =
                    event.payload.get("receipt_id").and_then(serde_json::Value::as_str)
                {
                    let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                    upgrade(&mut entry.stage, WorkItemStage::ReceiptMatched);
                    entry.claimed_complete = true;
                    entry.receipt = Some(WorkItemReceipt {
                        receipt_id: receipt_id.to_string(),
                        matched: true,
                    });
                }
            }
            "CandidateAccepted" => {
                let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                upgrade(&mut entry.stage, WorkItemStage::Accepted);
                entry.claimed_complete = true;
            }
            "FailureNode" => {
                let reason = event
                    .payload
                    .get("blocked_reason")
                    .and_then(serde_json::Value::as_str)
                    .or_else(|| {
                        event
                            .payload
                            .get("failure_class")
                            .and_then(serde_json::Value::as_str)
                    });
                if let Some(reason) = reason {
                    let entry = get_or_insert(&mut builders, &mut order, capsule_id);
                    entry.blocked_reason = Some(reason.to_string());
                }
            }
            _ => {}
        }
    }

    order
        .into_iter()
        .filter_map(|id| {
            let builder = builders.remove(&id)?;
            let stage = builder.stage?;
            Some(WorkItem {
                title: builder.title.unwrap_or_else(|| id.clone()),
                id,
                stage,
                claimed_complete: builder.claimed_complete,
                receipt: builder.receipt,
                blocked_reason: builder.blocked_reason,
            })
        })
        .collect()
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorWarning {
    pub code: String,
    pub severity: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorViewSnapshot {
    pub schema_id: String,
    pub source: OperatorSnapshotSource,
    pub heads: OperatorHeads,
    pub head_consistency: HeadConsistency,
    pub operator_state: OperatorState,
    pub lanes: Vec<OperatorLane>,
    pub active_work: Vec<String>,
    pub evidence: Vec<String>,
    pub failures: Vec<String>,
    pub warnings: Vec<OperatorWarning>,
    pub next_sovereign_action: String,
    pub safe_commands: Vec<CommandSpec>,
    /// PER-ITEM SNAPSHOT CONTRACT v1 (additive, optional): per-capsule lifecycle state
    /// derived by [`derive_work_items`] from a raw tape walk. `None` — the field is omitted
    /// from JSON entirely (`skip_serializing_if`) — means *legacy snapshot*: either the
    /// source tape carried no derivable per-item events, or the caller didn't attempt
    /// derivation (e.g. the synthetic qualification demo tape, whose events don't share a
    /// stable capsule-id across its dispatch/receipt/accept steps). Renderers must fall back
    /// to today's single-track view whenever this is `None`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub work_items: Option<Vec<WorkItem>>,
    pub snapshot_hash: String,
}

impl OperatorViewSnapshot {
    pub fn from_guarded_heads(
        project_root: impl Into<String>,
        micro_repo: impl Into<String>,
        rebuild_command: impl Into<String>,
        heads: OperatorHeads,
        work_items: Vec<WorkItem>,
    ) -> Result<Self, ProjectionError> {
        Self::from_heads_with_source_kind(
            "guarded_micro_tape_read",
            project_root,
            micro_repo,
            rebuild_command,
            heads,
            work_items,
        )
    }

    pub fn from_deterministic_replay(
        project_root: impl Into<String>,
        micro_repo: impl Into<String>,
        rebuild_command: impl Into<String>,
        heads: OperatorHeads,
        work_items: Vec<WorkItem>,
    ) -> Result<Self, ProjectionError> {
        Self::from_heads_with_source_kind(
            "deterministic_replay",
            project_root,
            micro_repo,
            rebuild_command,
            heads,
            work_items,
        )
    }

    pub fn from_projection_events_forbidden(
        _events: Vec<ProjectionEvent>,
    ) -> Result<Self, ProjectionError> {
        Err(ProjectionError::CallerSuppliedProjectionEventsForbidden)
    }

    fn from_heads_with_source_kind(
        source_kind: &str,
        project_root: impl Into<String>,
        micro_repo: impl Into<String>,
        rebuild_command: impl Into<String>,
        heads: OperatorHeads,
        work_items: Vec<WorkItem>,
    ) -> Result<Self, ProjectionError> {
        let work_items = if work_items.is_empty() {
            None
        } else {
            Some(work_items)
        };
        let lanes = vec![
            OperatorLane {
                name: "append".to_string(),
                head: Some(heads.tape_tip.clone()),
                meaning: "latest MicroTape append; every event moves this head".to_string(),
            },
            OperatorLane {
                name: "authorization".to_string(),
                head: heads.authorization_head.clone(),
                meaning: "latest authorization event; permission, not completion".to_string(),
            },
            OperatorLane {
                name: "accepted".to_string(),
                head: Some(heads.accepted_head.clone()),
                meaning: "latest sovereign accept event from replay-derived head movement"
                    .to_string(),
            },
        ];
        let warnings = vec![OperatorWarning {
            code: "NO_HITL_STATUS_CEILING".to_string(),
            severity: "warning".to_string(),
            message:
                "local no-HITL gates can report IMPLEMENTER_ADDRESSED only; no human ratification"
                    .to_string(),
        }];
        let source = OperatorSnapshotSource {
            project_root: project_root.into(),
            micro_repo: micro_repo.into(),
            source_kind: source_kind.to_string(),
            projection_version: "operator_view_snapshot.v1".to_string(),
            rebuild_command: rebuild_command.into(),
            can_write_truth: false,
        };
        let mut snapshot = OperatorViewSnapshot {
            schema_id: "operator_view_snapshot.v1".to_string(),
            source,
            heads,
            head_consistency: HeadConsistency::Consistent,
            operator_state: OperatorState::Healthy,
            lanes,
            active_work: vec!["no active worker dispatch in this read-only snapshot".to_string()],
            evidence: vec![
                "heads read through guarded MicroTape/replay path".to_string(),
                "renderer may format snapshot but may not derive new truth".to_string(),
            ],
            failures: Vec::new(),
            warnings,
            next_sovereign_action: "no human approval pending".to_string(),
            safe_commands: CommandSpec::all(),
            work_items,
            snapshot_hash: String::new(),
        };
        let mut preimage = serde_json::json!({
            "schema_id": snapshot.schema_id,
            "source": snapshot.source,
            "heads": snapshot.heads,
            "head_consistency": snapshot.head_consistency,
            "operator_state": snapshot.operator_state,
            "lanes": snapshot.lanes,
            "active_work": snapshot.active_work,
            "evidence": snapshot.evidence,
            "failures": snapshot.failures,
            "warnings": snapshot.warnings,
            "next_sovereign_action": snapshot.next_sovereign_action,
            "safe_commands": snapshot.safe_commands,
        });
        // Mirror the `skip_serializing_if` on `work_items` exactly: a legacy (`None`)
        // snapshot must hash byte-identically to before this atom (the preimage above is
        // untouched), and a populated snapshot's preimage must contain exactly the key the
        // JSON serialization carries — never a phantom `"work_items": null` the wire format
        // never emits (that would desync `tools/hci/audit_projection_integrity.py`'s and
        // `FCE-R2`'s shadow-rebuild self-consistency check, both of which hash "the whole
        // JSON object minus `snapshot_hash`").
        if let Some(work_items) = &snapshot.work_items {
            preimage["work_items"] = serde_json::to_value(work_items)
                .map_err(|error| ProjectionError::Canonicalization(error.to_string()))?;
        }
        let bytes = jcs::canonicalize(&preimage)
            .map_err(|error| ProjectionError::Canonicalization(error.to_string()))?;
        snapshot.snapshot_hash = format!("sha256:{}", jcs::sha256_hex(&bytes));
        Ok(snapshot)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TypedVerb {
    ViewStatus,
    ViewPanoview,
    ExplainEvent,
    ExplainBlocker,
    ReplayVerify,
    AuditInvariants,
    ProposeIntent,
    ProposeGoal,
    ProposeCapsule,
    ApproveCapsule,
    DispatchWorker,
    ObserveCapsule,
    RejectCandidate,
    RequestMacroAuth,
    ApproveCandidate,
    Help,
}

#[allow(non_upper_case_globals)]
impl TypedVerb {
    pub const VIEW_STATUS: Self = Self::ViewStatus;
    pub const VIEW_PANOVIEW: Self = Self::ViewPanoview;
    pub const EXPLAIN_EVENT: Self = Self::ExplainEvent;
    pub const EXPLAIN_BLOCKER: Self = Self::ExplainBlocker;
    pub const REPLAY_VERIFY: Self = Self::ReplayVerify;
    pub const AUDIT_INVARIANTS: Self = Self::AuditInvariants;
    pub const PROPOSE_INTENT: Self = Self::ProposeIntent;
    pub const PROPOSE_GOAL: Self = Self::ProposeGoal;
    pub const PROPOSE_CAPSULE: Self = Self::ProposeCapsule;
    pub const APPROVE_CAPSULE: Self = Self::ApproveCapsule;
    pub const DISPATCH_WORKER: Self = Self::DispatchWorker;
    pub const OBSERVE_CAPSULE: Self = Self::ObserveCapsule;
    pub const REJECT_CANDIDATE: Self = Self::RejectCandidate;
    pub const REQUEST_MACRO_AUTH: Self = Self::RequestMacroAuth;
    pub const APPROVE_CANDIDATE: Self = Self::ApproveCandidate;
    pub const HELP: Self = Self::Help;

    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            TypedVerb::ViewStatus => "VIEW_STATUS",
            TypedVerb::ViewPanoview => "VIEW_PANOVIEW",
            TypedVerb::ExplainEvent => "EXPLAIN_EVENT",
            TypedVerb::ExplainBlocker => "EXPLAIN_BLOCKER",
            TypedVerb::ReplayVerify => "REPLAY_VERIFY",
            TypedVerb::AuditInvariants => "AUDIT_INVARIANTS",
            TypedVerb::ProposeIntent => "PROPOSE_INTENT",
            TypedVerb::ProposeGoal => "PROPOSE_GOAL",
            TypedVerb::ProposeCapsule => "PROPOSE_CAPSULE",
            TypedVerb::ApproveCapsule => "APPROVE_CAPSULE",
            TypedVerb::DispatchWorker => "DISPATCH_WORKER",
            TypedVerb::ObserveCapsule => "OBSERVE_CAPSULE",
            TypedVerb::RejectCandidate => "REJECT_CANDIDATE",
            TypedVerb::RequestMacroAuth => "REQUEST_MACRO_AUTH",
            TypedVerb::ApproveCandidate => "APPROVE_CANDIDATE",
            TypedVerb::Help => "HELP",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SideEffectClass {
    ReadOnly,
    ProposalOnly,
    Authorization,
    WorkerDispatch,
    Observation,
    SovereignMutation,
}

impl SideEffectClass {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            SideEffectClass::ReadOnly => "read_only",
            SideEffectClass::ProposalOnly => "proposal_only",
            SideEffectClass::Authorization => "authorization",
            SideEffectClass::WorkerDispatch => "worker_dispatch",
            SideEffectClass::Observation => "observation",
            SideEffectClass::SovereignMutation => "sovereign_mutation",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConfirmationRoute {
    None,
    ApprovalRequired,
    HumanSignatureRequired,
}

impl ConfirmationRoute {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            ConfirmationRoute::None => "none",
            ConfirmationRoute::ApprovalRequired => "approval_required",
            ConfirmationRoute::HumanSignatureRequired => "human_signature_required",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CommandSpec {
    pub schema_id: String,
    pub verb: TypedVerb,
    pub side_effect_class: SideEffectClass,
    pub source_heads: Vec<String>,
    pub preconditions: Vec<String>,
    pub risk_class: String,
    pub confirmation_route: ConfirmationRoute,
    pub approval_required: bool,
    pub dry_run_default: bool,
    pub writes_truth: bool,
    pub expected_receipt: String,
    pub replay_command: String,
}

impl CommandSpec {
    #[must_use]
    pub fn all() -> Vec<Self> {
        vec![
            spec(
                TypedVerb::ViewStatus,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ViewPanoview,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ExplainEvent,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ExplainBlocker,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ReplayVerify,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::AuditInvariants,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ProposeIntent,
                SideEffectClass::ProposalOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ProposeGoal,
                SideEffectClass::ProposalOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ProposeCapsule,
                SideEffectClass::ProposalOnly,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::ApproveCapsule,
                SideEffectClass::SovereignMutation,
                true,
                ConfirmationRoute::HumanSignatureRequired,
            ),
            spec(
                TypedVerb::DispatchWorker,
                SideEffectClass::WorkerDispatch,
                true,
                ConfirmationRoute::ApprovalRequired,
            ),
            spec(
                TypedVerb::ObserveCapsule,
                SideEffectClass::Observation,
                false,
                ConfirmationRoute::None,
            ),
            spec(
                TypedVerb::RejectCandidate,
                SideEffectClass::Authorization,
                true,
                ConfirmationRoute::ApprovalRequired,
            ),
            spec(
                TypedVerb::RequestMacroAuth,
                SideEffectClass::Authorization,
                true,
                ConfirmationRoute::HumanSignatureRequired,
            ),
            spec(
                TypedVerb::ApproveCandidate,
                SideEffectClass::SovereignMutation,
                true,
                ConfirmationRoute::HumanSignatureRequired,
            ),
            spec(
                TypedVerb::Help,
                SideEffectClass::ReadOnly,
                false,
                ConfirmationRoute::None,
            ),
        ]
    }

    #[must_use]
    pub fn get(verb: TypedVerb) -> Option<Self> {
        Self::all().into_iter().find(|spec| spec.verb == verb)
    }
}

fn spec(
    verb: TypedVerb,
    side_effect_class: SideEffectClass,
    approval_required: bool,
    confirmation_route: ConfirmationRoute,
) -> CommandSpec {
    CommandSpec {
        schema_id: "typed_command.v1".to_string(),
        verb,
        side_effect_class,
        source_heads: vec![
            "tape_tip".to_string(),
            "authorization_head".to_string(),
            "accepted_head".to_string(),
        ],
        preconditions: if approval_required {
            vec![
                "operator_view_snapshot.v1 is fresh".to_string(),
                "real approval event exists or command returns approval_required".to_string(),
            ]
        } else {
            vec!["operator_view_snapshot.v1 is fresh".to_string()]
        },
        risk_class: if approval_required { "P1" } else { "P0" }.to_string(),
        confirmation_route,
        approval_required,
        dry_run_default: true,
        writes_truth: false,
        expected_receipt: if approval_required {
            "approval_required_or_human_signature_required"
        } else {
            "read_only_receipt"
        }
        .to_string(),
        replay_command: "turing replay --verify".to_string(),
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorToolManifest {
    pub schema_id: String,
    pub commands: Vec<CommandSpec>,
    pub can_evaluate_predicates: bool,
    pub can_move_heads: bool,
    pub can_synthesize_approvals: bool,
    pub can_run_shell: bool,
    pub can_autonomous_dispatch: bool,
}

impl OperatorToolManifest {
    #[must_use]
    pub fn closed_v1() -> Self {
        OperatorToolManifest {
            schema_id: "operator_tool_manifest.v1".to_string(),
            commands: CommandSpec::all(),
            can_evaluate_predicates: false,
            can_move_heads: false,
            can_synthesize_approvals: false,
            can_run_shell: false,
            can_autonomous_dispatch: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorIntent {
    pub schema_id: String,
    pub utterance_digest: String,
    pub selected_verb: TypedVerb,
    pub confidence_basis: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorTurnTrace {
    pub schema_id: String,
    pub intent: OperatorIntent,
    pub typed_command: CommandSpec,
    pub manifest: OperatorToolManifest,
    pub advisory_confidence: String,
}

pub struct ProductionApprovalRoutePolicy;

impl ProductionApprovalRoutePolicy {
    #[must_use]
    pub fn allows(route: &str) -> bool {
        matches!(route, "os-keyring" | "hardware" | "hardware-future")
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Projection {
    pub schema_id: String,
    pub source: String,
    pub event_count: usize,
    pub market_event_count: usize,
    pub pput_event_count: usize,
    pub can_write_truth: bool,
    pub projection_hash: String,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct TuiProjectionClient;

impl TuiProjectionClient {
    #[must_use]
    pub fn new() -> Self {
        TuiProjectionClient
    }

    #[must_use]
    pub fn approve_candidate(&self, candidate_id: impl Into<String>) -> TuiCommand {
        TuiCommand::ApproveCandidate {
            candidate_id: candidate_id.into(),
        }
    }

    #[must_use]
    pub fn can_write_micro_truth(&self) -> bool {
        false
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TuiCommand {
    ApproveCandidate { candidate_id: String },
    RejectCandidate { candidate_id: String },
    DispatchCapsule { capsule_id: String },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProjectionError {
    InvalidMicroEventId(String),
    CallerSuppliedProjectionEventsForbidden,
    Canonicalization(String),
}

impl std::fmt::Display for ProjectionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProjectionError::InvalidMicroEventId(id) => write!(f, "invalid Micro event id {id:?}"),
            ProjectionError::CallerSuppliedProjectionEventsForbidden => write!(
                f,
                "operator_view_snapshot.v1 must be built from guarded MicroTape reads or deterministic replay"
            ),
            ProjectionError::Canonicalization(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for ProjectionError {}
