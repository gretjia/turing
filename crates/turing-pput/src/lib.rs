//! Hidden PPUT cost accounting and projection reducers.
//!
//! This crate produces hidden evaluator records. It never writes worker-visible
//! objectives; ordinary worker prompts should only receive pass/fail and abstract
//! repair guidance.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use turing_contracts::jcs;

const M1C_PRICE_TABLE_DIGEST: &str =
    "sha256:38847526b4322ad2e7178845730d52aa44661bb33d668428b934a6d29969af0a";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Split {
    Adaptation,
    MetaValidation,
    Heldout,
    Dogfood,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CostEvent {
    pub schema_id: String,
    #[serde(skip_serializing)]
    pub event_type: String,
    #[serde(skip_serializing)]
    pub head_effect: String,
    pub run_id: String,
    pub problem_id: String,
    pub split: Split,
    pub agent_id: String,
    pub branch_id: String,
    pub capsule_id: String,
    pub receipt_id: String,
    pub worker: CostWorker,
    pub usage: CostUsage,
    pub cost: CostAmount,
    #[serde(skip_serializing)]
    pub prompt_tokens: u64,
    #[serde(skip_serializing)]
    pub completion_tokens: u64,
    #[serde(skip_serializing)]
    pub tool_tokens: u64,
    #[serde(skip_serializing)]
    pub tool_stdout_tokens: u64,
    #[serde(skip_serializing)]
    pub total_tokens: u64,
    pub wall_time_ms: u64,
    pub tool_stdout_hash: String,
    pub counted_in_total: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CostWorker {
    pub adapter_kind: String,
    pub provider: String,
    pub model_id_requested: String,
    pub model_id_resolved: String,
    pub endpoint: String,
    pub request_id: String,
    pub response_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CostUsage {
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub tool_tokens: u64,
    pub tool_stdout_tokens: u64,
    pub total_tokens: u64,
    pub provider_usage_raw_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CostAmount {
    pub cost_source_kind: String,
    pub cost_microusd: u64,
    pub price_table_digest: String,
    pub bound_kind: Option<String>,
}

impl CostEvent {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        run_id: impl Into<String>,
        problem_id: impl Into<String>,
        split: Split,
        agent_id: impl Into<String>,
        branch_id: impl Into<String>,
        capsule_id: impl Into<String>,
        prompt_tokens: u64,
        completion_tokens: u64,
        tool_tokens: u64,
        tool_stdout_tokens: u64,
        wall_time_ms: u64,
        tool_stdout: &[u8],
    ) -> Result<Self, PputError> {
        let total_tokens = prompt_tokens
            .checked_add(completion_tokens)
            .and_then(|v| v.checked_add(tool_tokens))
            .and_then(|v| v.checked_add(tool_stdout_tokens))
            .ok_or(PputError::TokenOverflow)?;
        let run_id = run_id.into();
        let problem_id = problem_id.into();
        let agent_id = agent_id.into();
        let branch_id = branch_id.into();
        let capsule_id = capsule_id.into();
        let tool_stdout_hash = format!("sha256:{}", jcs::sha256_hex(tool_stdout));
        let receipt_material = format!("{run_id}:{branch_id}:{tool_stdout_hash}");
        let receipt_id = format!("rcpt:{}", jcs::sha256_hex(receipt_material.as_bytes()));
        let usage_material = format!(
            "{prompt_tokens}:{completion_tokens}:{tool_tokens}:{tool_stdout_tokens}:{total_tokens}"
        );
        let provider_usage_raw_sha256 =
            format!("sha256:{}", jcs::sha256_hex(usage_material.as_bytes()));
        Ok(CostEvent {
            schema_id: "turingos.cost_event.v2".to_string(),
            event_type: "CostEvent".to_string(),
            head_effect: "PRESERVE".to_string(),
            run_id,
            problem_id,
            split,
            agent_id,
            branch_id,
            capsule_id,
            receipt_id,
            worker: CostWorker {
                adapter_kind: "fake".to_string(),
                provider: "fixture".to_string(),
                model_id_requested: "fixture-model".to_string(),
                model_id_resolved: "fixture-model-20260702".to_string(),
                endpoint: "fixture://pput".to_string(),
                request_id: "req_fixture_pput".to_string(),
                response_sha256: tool_stdout_hash.clone(),
            },
            usage: CostUsage {
                prompt_tokens,
                completion_tokens,
                tool_tokens,
                tool_stdout_tokens,
                total_tokens,
                provider_usage_raw_sha256,
            },
            cost: CostAmount {
                cost_source_kind: "fixture".to_string(),
                cost_microusd: 0,
                price_table_digest: M1C_PRICE_TABLE_DIGEST.to_string(),
                bound_kind: None,
            },
            prompt_tokens,
            completion_tokens,
            tool_tokens,
            tool_stdout_tokens,
            total_tokens,
            wall_time_ms,
            tool_stdout_hash,
            counted_in_total: true,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum GroundTruthResult {
    Pass,
    Fail,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProposalRecord {
    pub schema_id: String,
    pub branch_id: String,
    pub ground_truth_result: GroundTruthResult,
    pub is_on_golden_path: bool,
}

impl ProposalRecord {
    #[must_use]
    pub fn new(
        branch_id: impl Into<String>,
        ground_truth_result: GroundTruthResult,
        is_on_golden_path: bool,
    ) -> Self {
        ProposalRecord {
            schema_id: "pput_proposal_record.v1".to_string(),
            branch_id: branch_id.into(),
            ground_truth_result,
            is_on_golden_path,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PputRunInput {
    pub run_id: String,
    pub problem_id: String,
    pub split: Split,
    pub costs: Vec<CostEvent>,
    pub proposals: Vec<ProposalRecord>,
    pub verified: bool,
}

impl PputRunInput {
    pub fn account(self) -> Result<PPUTAccounted, PputError> {
        let total_run_token_count = self
            .costs
            .iter()
            .try_fold(0_u64, |acc, cost| acc.checked_add(cost.total_tokens))
            .ok_or(PputError::TokenOverflow)?;
        let total_wall_time_ms = self
            .costs
            .iter()
            .try_fold(0_u64, |acc, cost| acc.checked_add(cost.wall_time_ms))
            .ok_or(PputError::WallTimeOverflow)?;
        let total_run_cost_microusd = self
            .costs
            .iter()
            .try_fold(0_u64, |acc, cost| acc.checked_add(cost.cost.cost_microusd))
            .ok_or(PputError::TokenOverflow)?;

        let golden_branches: BTreeSet<&str> = self
            .proposals
            .iter()
            .filter(|proposal| {
                proposal.is_on_golden_path
                    && proposal.ground_truth_result == GroundTruthResult::Pass
            })
            .map(|proposal| proposal.branch_id.as_str())
            .collect();
        let golden_path_token_count = self
            .costs
            .iter()
            .filter(|cost| golden_branches.contains(cost.branch_id.as_str()))
            .try_fold(0_u64, |acc, cost| acc.checked_add(cost.total_tokens))
            .ok_or(PputError::TokenOverflow)?;

        let failed_branch_count = self
            .proposals
            .iter()
            .filter(|proposal| proposal.ground_truth_result != GroundTruthResult::Pass)
            .count() as u64;
        let progress = u8::from(self.verified && !golden_branches.is_empty());
        let denominator = total_run_token_count
            .checked_mul(total_wall_time_ms)
            .ok_or(PputError::TokenOverflow)?;
        let vpput_raw = if progress == 0 || denominator == 0 {
            "0".to_string()
        } else {
            decimal_ratio(1, denominator)
        };

        Ok(PPUTAccounted {
            schema_id: "pput_accounted.v1".to_string(),
            event_type: "PPUTAccounted".to_string(),
            head_effect: "PRESERVE".to_string(),
            run_id: self.run_id,
            problem_id: self.problem_id,
            split: self.split,
            solved: progress == 1,
            verified: self.verified,
            golden_path_token_count,
            total_run_token_count,
            total_run_cost_microusd,
            total_wall_time_ms,
            progress,
            vpput_raw,
            failed_branch_count,
            hidden_from_worker_prompt: true,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PPUTAccounted {
    pub schema_id: String,
    pub event_type: String,
    pub head_effect: String,
    pub run_id: String,
    pub problem_id: String,
    pub split: Split,
    pub solved: bool,
    pub verified: bool,
    pub golden_path_token_count: u64,
    pub total_run_token_count: u64,
    pub total_run_cost_microusd: u64,
    pub total_wall_time_ms: u64,
    pub progress: u8,
    pub vpput_raw: String,
    pub failed_branch_count: u64,
    pub hidden_from_worker_prompt: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PputProjection {
    pub source: String,
    pub total_tokens: u64,
    pub total_wall_time_ms: u64,
}

impl PputProjection {
    pub fn from_tape_events(costs: &[CostEvent]) -> Result<Self, PputError> {
        let total_tokens = costs
            .iter()
            .try_fold(0_u64, |acc, cost| acc.checked_add(cost.total_tokens))
            .ok_or(PputError::TokenOverflow)?;
        let total_wall_time_ms = costs
            .iter()
            .try_fold(0_u64, |acc, cost| acc.checked_add(cost.wall_time_ms))
            .ok_or(PputError::WallTimeOverflow)?;
        Ok(PputProjection {
            source: "micro_tape_only".to_string(),
            total_tokens,
            total_wall_time_ms,
        })
    }
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct WorkerPromptShield;

impl WorkerPromptShield {
    pub fn validate(prompt: &str) -> Result<(), PputError> {
        let lower = prompt.to_ascii_lowercase();
        for marker in [
            "pput",
            "vpput",
            "heldout",
            "golden path",
            "progress /",
            "hidden evaluator",
        ] {
            if lower.contains(marker) {
                return Err(PputError::WorkerPromptLeakage(marker.to_string()));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PputError {
    TokenOverflow,
    WallTimeOverflow,
    WorkerPromptLeakage(String),
}

impl std::fmt::Display for PputError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PputError::TokenOverflow => write!(f, "token accounting overflow"),
            PputError::WallTimeOverflow => write!(f, "wall time accounting overflow"),
            PputError::WorkerPromptLeakage(marker) => {
                write!(f, "worker prompt leaks hidden PPUT marker {marker:?}")
            }
        }
    }
}

impl std::error::Error for PputError {}

fn decimal_ratio(numerator: u64, denominator: u64) -> String {
    let scaled = (u128::from(numerator) * 1_000_000_000_u128) / u128::from(denominator);
    let whole = scaled / 1_000_000_000_u128;
    let mut fraction = format!("{:09}", scaled % 1_000_000_000_u128);
    while fraction.ends_with('0') {
        fraction.pop();
    }
    if fraction.is_empty() {
        whole.to_string()
    } else {
        format!("{whole}.{fraction}")
    }
}
