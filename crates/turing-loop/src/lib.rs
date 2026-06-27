//! Single Loop read surface.
//!
//! This crate intentionally does not own a controller yet. M4-A01 starts with the read
//! side: reconstruct Q from the native Git Micro Tape and treat projection caches as
//! disposable hints, never truth.

pub mod rtool {
    use std::collections::BTreeSet;
    use std::path::Path;

    use serde_json::Value;

    use turing_contracts::envelope::{HeadSet, MicroEventEnvelope, PredicateProduct};
    use turing_contracts::jcs::JcsError;
    use turing_contracts::registry::{self, EventClass};
    use turing_git_tape::append::{commit_parents, committed_body_bytes};
    use turing_git_tape::git::{self, GitError};
    use turing_replay::{self, ReplayError};

    const REF_TAPE_TIP: &str = "refs/turingos/tape_tip";

    const MARKET_EVENT_TYPES: &[&str] = &[
        "MarketCreated",
        "MarketLiquidityAdded",
        "PositionMinted",
        "AgentBidSubmitted",
        "AMMSwapExecuted",
        "BudgetAllocated",
        "MarketPriceBroadcast",
        "MarketSettled",
        "RewardDistributed",
    ];

    const COST_EVENT_TYPES: &[&str] = &["CostEvent", "BranchCostEvent", "ToolStdoutCostEvent"];

    /// Disposable projection data a caller may already have. `read_q` accepts it only to
    /// keep the API ready for projection-aware callers; none of these fields are trusted.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct ProjectionCache {
        pub tape_tip: String,
        pub accepted_head: String,
        pub market_event_count: usize,
        pub pput_event_count: usize,
    }

    /// The Single Loop's read-state snapshot, reconstructed from Tape.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct QRead {
        pub head_set: HeadSet,
        pub replay_event_count: usize,
        pub market: MarketProjection,
        pub pput: PputSummary,
        pub events: Vec<ReadEvent>,
    }

    /// Market projection summary derived from committed events.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct MarketProjection {
        pub market_event_count: usize,
    }

    /// Shielded PPUT summary derived from committed cost events.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct PputSummary {
        pub cost_event_count: usize,
    }

    /// One committed event as visible to the read phase.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct ReadEvent {
        pub event_id: String,
        pub event_type: String,
        pub class: EventClass,
        pub predicate_product: PredicateProduct,
    }

    /// Errors returned by `read_q`.
    #[derive(Debug)]
    pub enum ReadError {
        Git(GitError),
        Replay(ReplayError),
        Body(JcsError),
        Malformed(String),
        UnknownEventType(String),
        MergeCommit { event_id: String, parents: usize },
        CyclicChain(String),
    }

    impl std::fmt::Display for ReadError {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            match self {
                ReadError::Git(e) => write!(f, "rtool git error: {e}"),
                ReadError::Replay(e) => write!(f, "rtool replay error: {e}"),
                ReadError::Body(e) => write!(f, "rtool body error: {e}"),
                ReadError::Malformed(m) => write!(f, "rtool malformed body: {m}"),
                ReadError::UnknownEventType(t) => {
                    write!(f, "UNKNOWN_EVENT_TYPE: {t:?} is not in the closed registry")
                }
                ReadError::MergeCommit { event_id, parents } => write!(
                    f,
                    "corrupt Tape: event {event_id} is a merge commit ({parents} parents)"
                ),
                ReadError::CyclicChain(id) => {
                    write!(f, "corrupt Tape: parent chain revisits event {id}")
                }
            }
        }
    }

    impl std::error::Error for ReadError {
        fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
            match self {
                ReadError::Git(e) => Some(e),
                ReadError::Replay(e) => Some(e),
                ReadError::Body(e) => Some(e),
                _ => None,
            }
        }
    }

    impl From<GitError> for ReadError {
        fn from(e: GitError) -> Self {
            ReadError::Git(e)
        }
    }

    impl From<ReplayError> for ReadError {
        fn from(e: ReplayError) -> Self {
            ReadError::Replay(e)
        }
    }

    impl From<JcsError> for ReadError {
        fn from(e: JcsError) -> Self {
            ReadError::Body(e)
        }
    }

    /// Reconstruct Q from the Git Micro Tape. Projection data is deliberately ignored:
    /// projection can be deleted and rebuilt, so it cannot supply load-bearing state.
    pub fn read_q(
        repo: &Path,
        projection_cache: Option<&ProjectionCache>,
    ) -> Result<QRead, ReadError> {
        let _ = projection_cache;

        let tape_tip = normalize_id(&git::rev_parse(repo, REF_TAPE_TIP)?);
        let reconstruction = turing_replay::replay_tape(repo, &tape_tip)?;
        let event_ids = walk_to_genesis(repo, &tape_tip)?;

        let mut events = Vec::with_capacity(event_ids.len());
        let mut market_event_count = 0;
        let mut cost_event_count = 0;

        for event_id in event_ids {
            let env = read_envelope(repo, &event_id)?;
            let row = registry::registry(&env.event_type)
                .ok_or_else(|| ReadError::UnknownEventType(env.event_type.clone()))?;

            if MARKET_EVENT_TYPES.contains(&env.event_type.as_str()) {
                market_event_count += 1;
            }
            if COST_EVENT_TYPES.contains(&env.event_type.as_str()) {
                cost_event_count += 1;
            }

            events.push(ReadEvent {
                event_id,
                event_type: env.event_type,
                class: row.class,
                predicate_product: env.predicate_product,
            });
        }

        Ok(QRead {
            head_set: reconstruction.head_set().clone(),
            replay_event_count: reconstruction.event_count(),
            market: MarketProjection { market_event_count },
            pput: PputSummary { cost_event_count },
            events,
        })
    }

    fn walk_to_genesis(repo: &Path, tip: &str) -> Result<Vec<String>, ReadError> {
        let mut chain_tip_first: Vec<String> = Vec::new();
        let mut seen: BTreeSet<String> = BTreeSet::new();
        let mut cursor = normalize_id(tip);

        loop {
            if !seen.insert(cursor.clone()) {
                return Err(ReadError::CyclicChain(cursor));
            }
            let parents = commit_parents(repo, &cursor)?;
            chain_tip_first.push(cursor.clone());
            match parents.as_slice() {
                [] => break,
                [parent] => cursor = normalize_id(parent),
                many => {
                    return Err(ReadError::MergeCommit {
                        event_id: cursor,
                        parents: many.len(),
                    });
                }
            }
        }

        chain_tip_first.reverse();
        Ok(chain_tip_first)
    }

    fn read_envelope(repo: &Path, event_id: &str) -> Result<MicroEventEnvelope, ReadError> {
        let bytes = committed_body_bytes(repo, event_id)?;
        let value: Value = serde_json::from_slice(&bytes).map_err(|e| {
            ReadError::Malformed(format!("committed body of {event_id} not JSON: {e}"))
        })?;
        MicroEventEnvelope::from_jcs_value(&value).map_err(ReadError::Body)
    }

    fn normalize_id(id: &str) -> String {
        match id.split_once(':') {
            Some((_, tail)) => format!("mu:{tail}"),
            None => format!("mu:{id}"),
        }
    }
}
