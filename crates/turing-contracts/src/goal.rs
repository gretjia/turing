//! GoalState contract surface.
//!
//! M5-A01 binds the constitution-facing rule that a GoalState cannot be accepted on
//! prose alone: every `must_have` requirement needs at least one machine-checkable
//! predicate or PCP check. Human summaries may explain intent, but they are not truth
//! gates.

use serde::{Deserialize, Serialize};

use crate::jcs::{self, JcsError};

pub const GOAL_STATE_SCHEMA_ID: &str = "goal_state.v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GoalState {
    pub schema_id: String,
    pub goal_id: String,
    pub objective: String,
    pub must_haves: Vec<GoalRequirement>,
    pub anti_goals: Vec<String>,
}

impl GoalState {
    #[must_use]
    pub fn new(goal_id: impl Into<String>, objective: impl Into<String>) -> Self {
        GoalState {
            schema_id: GOAL_STATE_SCHEMA_ID.to_string(),
            goal_id: goal_id.into(),
            objective: objective.into(),
            must_haves: Vec::new(),
            anti_goals: Vec::new(),
        }
    }

    #[must_use]
    pub fn with_must_have(mut self, requirement: GoalRequirement) -> Self {
        self.must_haves.push(requirement);
        self
    }

    #[must_use]
    pub fn with_anti_goal(mut self, anti_goal: impl Into<String>) -> Self {
        self.anti_goals.push(anti_goal.into());
        self
    }

    pub fn validate(&self) -> Result<(), GoalValidationError> {
        if self.schema_id != GOAL_STATE_SCHEMA_ID {
            return Err(GoalValidationError::WrongSchemaId {
                actual: self.schema_id.clone(),
            });
        }

        for (requirement_index, requirement) in self.must_haves.iter().enumerate() {
            if requirement.machine_checks.is_empty() {
                return Err(GoalValidationError::MustHaveMissingMachineCheck {
                    index: requirement_index,
                    requirement: requirement.text.clone(),
                });
            }

            for (check_index, check) in requirement.machine_checks.iter().enumerate() {
                if check.id().trim().is_empty() {
                    return Err(GoalValidationError::EmptyMachineCheckId {
                        requirement_index,
                        check_index,
                    });
                }
            }
        }

        Ok(())
    }

    pub fn to_jcs_bytes(&self) -> Result<Vec<u8>, JcsError> {
        let value =
            serde_json::to_value(self).expect("GoalState serializes to a JSON object infallibly");
        jcs::canonicalize(&value)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GoalRequirement {
    pub text: String,
    pub machine_checks: Vec<MachineCheck>,
}

impl GoalRequirement {
    #[must_use]
    pub fn must_have(text: impl Into<String>) -> Self {
        GoalRequirement {
            text: text.into(),
            machine_checks: Vec::new(),
        }
    }

    #[must_use]
    pub fn with_machine_check(mut self, check: MachineCheck) -> Self {
        self.machine_checks.push(check);
        self
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", deny_unknown_fields)]
pub enum MachineCheck {
    #[serde(rename = "PREDICATE")]
    Predicate { predicate_id: String },
    #[serde(rename = "PCP")]
    Pcp { check_id: String },
}

impl MachineCheck {
    #[must_use]
    pub fn predicate(predicate_id: impl Into<String>) -> Self {
        MachineCheck::Predicate {
            predicate_id: predicate_id.into(),
        }
    }

    #[must_use]
    pub fn pcp(check_id: impl Into<String>) -> Self {
        MachineCheck::Pcp {
            check_id: check_id.into(),
        }
    }

    #[must_use]
    pub fn id(&self) -> &str {
        match self {
            MachineCheck::Predicate { predicate_id } => predicate_id,
            MachineCheck::Pcp { check_id } => check_id,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GoalValidationError {
    WrongSchemaId {
        actual: String,
    },
    MustHaveMissingMachineCheck {
        index: usize,
        requirement: String,
    },
    EmptyMachineCheckId {
        requirement_index: usize,
        check_index: usize,
    },
}

impl std::fmt::Display for GoalValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            GoalValidationError::WrongSchemaId { actual } => write!(
                f,
                "GoalState schema_id must be {GOAL_STATE_SCHEMA_ID:?}, got {actual:?}"
            ),
            GoalValidationError::MustHaveMissingMachineCheck { index, requirement } => write!(
                f,
                "GoalState must_have[{index}] {requirement:?} lacks a predicate or PCP check"
            ),
            GoalValidationError::EmptyMachineCheckId {
                requirement_index,
                check_index,
            } => write!(
                f,
                "GoalState must_have[{requirement_index}].machine_checks[{check_index}] has an empty id"
            ),
        }
    }
}

impl std::error::Error for GoalValidationError {}
