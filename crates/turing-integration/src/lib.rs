//! Integration queue CAS admission and macro merge gates.

use std::collections::BTreeSet;

use turing_contracts::identity::MicroOid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntegrationCandidate {
    pub atom_id: String,
    pub expected_integration_head: String,
    pub candidate_head: String,
    pub touched_paths: Vec<String>,
}

impl IntegrationCandidate {
    #[must_use]
    pub fn new(
        atom_id: impl Into<String>,
        expected_integration_head: impl Into<String>,
        candidate_head: impl Into<String>,
        touched_paths: Vec<String>,
    ) -> Self {
        IntegrationCandidate {
            atom_id: atom_id.into(),
            expected_integration_head: expected_integration_head.into(),
            candidate_head: candidate_head.into(),
            touched_paths,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntegrationQueue {
    integration_head: String,
    admitted_atoms: Vec<String>,
    admitted_paths: BTreeSet<String>,
}

impl IntegrationQueue {
    pub fn new(integration_head: impl Into<String>) -> Result<Self, AdmissionError> {
        let integration_head = integration_head.into();
        validate_micro_id(&integration_head)?;
        Ok(IntegrationQueue {
            integration_head,
            admitted_atoms: Vec::new(),
            admitted_paths: BTreeSet::new(),
        })
    }

    pub fn admit(&mut self, candidate: IntegrationCandidate) -> Result<(), AdmissionError> {
        validate_micro_id(&candidate.expected_integration_head)?;
        validate_micro_id(&candidate.candidate_head)?;
        if candidate.expected_integration_head != self.integration_head {
            return Err(AdmissionError::StaleCandidate {
                atom_id: candidate.atom_id,
                expected: self.integration_head.clone(),
                observed: candidate.expected_integration_head,
            });
        }
        if let Some(path) = candidate
            .touched_paths
            .iter()
            .find(|path| self.admitted_paths.contains(*path))
        {
            return Err(AdmissionError::PathConflict {
                atom_id: candidate.atom_id,
                path: path.clone(),
            });
        }

        for path in &candidate.touched_paths {
            self.admitted_paths.insert(path.clone());
        }
        self.admitted_atoms.push(candidate.atom_id);
        self.integration_head = candidate.candidate_head;
        Ok(())
    }

    #[must_use]
    pub fn integration_head(&self) -> &str {
        &self.integration_head
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DriftState {
    pub commits_ahead_main: u64,
    pub hours_since_last_sync: u64,
    pub unmerged_atoms: u64,
}

impl DriftState {
    #[must_use]
    pub fn blocks_new_admission(&self) -> bool {
        self.commits_ahead_main > 20 || self.hours_since_last_sync > 72 || self.unmerged_atoms > 5
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MergeAuthorization {
    pub schema_id: String,
    pub authorization_event_id: String,
    pub moves_authorization_head: bool,
    pub moves_accepted_head: bool,
    pub auto_merge_main: bool,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct MainMergeGate;

impl MainMergeGate {
    pub fn authorize(
        human_route_valid: bool,
        authorization_event_id: &str,
    ) -> Result<MergeAuthorization, AdmissionError> {
        if !human_route_valid {
            return Err(AdmissionError::HumanRouteRequired);
        }
        validate_micro_id(authorization_event_id)?;
        Ok(MergeAuthorization {
            schema_id: "macro_merge_authorization.v1".to_string(),
            authorization_event_id: authorization_event_id.to_string(),
            moves_authorization_head: true,
            moves_accepted_head: false,
            auto_merge_main: false,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AdmissionError {
    InvalidMicroId(String),
    StaleCandidate {
        atom_id: String,
        expected: String,
        observed: String,
    },
    PathConflict {
        atom_id: String,
        path: String,
    },
    HumanRouteRequired,
}

impl std::fmt::Display for AdmissionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AdmissionError::InvalidMicroId(id) => write!(f, "invalid Micro id {id:?}"),
            AdmissionError::StaleCandidate {
                atom_id,
                expected,
                observed,
            } => write!(
                f,
                "stale integration candidate {atom_id:?}: expected {expected}, observed {observed}"
            ),
            AdmissionError::PathConflict { atom_id, path } => {
                write!(f, "integration candidate {atom_id:?} conflicts on {path:?}")
            }
            AdmissionError::HumanRouteRequired => write!(f, "main merge requires human route"),
        }
    }
}

impl std::error::Error for AdmissionError {}

fn validate_micro_id(id: &str) -> Result<(), AdmissionError> {
    MicroOid::parse(id)
        .map(|_| ())
        .map_err(|_| AdmissionError::InvalidMicroId(id.to_string()))
}
