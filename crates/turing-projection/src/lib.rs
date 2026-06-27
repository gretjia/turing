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
    Canonicalization(String),
}

impl std::fmt::Display for ProjectionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProjectionError::InvalidMicroEventId(id) => write!(f, "invalid Micro event id {id:?}"),
            ProjectionError::Canonicalization(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for ProjectionError {}
