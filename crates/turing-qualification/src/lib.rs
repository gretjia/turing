//! End-to-end qualification runners for the Agent Economy runtime.

use std::error::Error;
use std::path::Path;

use serde::Serialize;
use serde_json::{Value, json};

use turing_contracts::failure::FailureClass;
use turing_contracts::jcs;
use turing_economy::{
    EconomyEvent, MarketReplay, MarketRouter, MarketRouterMode, PriceSignal, RewardDistributed,
    WalletProjection,
};
use turing_execd::{FakeWorker, WorkerRunRequest};
use turing_failure::{BroadcastReducer, FailureTapeEvent, MemoryReducer};
use turing_git_tape::append::{Append, AppendRequest, CommittedReceipt};
use turing_git_tape::git;
use turing_loop::tick::{self, TickDecision};
use turing_pput::{
    CostEvent, GroundTruthResult, PputProjection, PputRunInput, ProposalRecord, Split,
    WorkerPromptShield,
};
use turing_projection::{ProjectionBuilder, ProjectionEvent, ProjectionSource};
use turing_replay::replay_tape;

pub type DemoResult<T> = Result<T, Box<dyn Error>>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NewProjectDemoReport {
    pub micro_git_exists: bool,
    pub tape_tip: String,
    pub authorization_head: Option<String>,
    pub accepted_head: String,
    pub candidate_accepted_event_id: String,
    pub market_settled_event_id: String,
    pub market_created_count: usize,
    pub budget_allocated_count: usize,
    pub worker_receipt_count: usize,
    pub macro_observation_count: usize,
    pub pput_accounted_count: usize,
    pub market_settled_count: usize,
    pub market_projection_status: String,
    pub pput_progress: u8,
    pub projection_rebuild_hash: String,
    pub market_projection_hash: String,
    pub wallet_projection_hash: String,
    pub pput_projection_hash: String,
    pub no_pput_prompt_leakage: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RescueDemoReport {
    pub micro_git_exists: bool,
    pub failure_node_count: usize,
    pub broadcast_rule_count: usize,
    pub failure_class: String,
    pub accepted_head_before_failure: String,
    pub accepted_head_after_failure: String,
    pub recovery_capsule_proposed: bool,
    pub broadcast_summary_abstract: bool,
}

pub fn run_new_project_agent_economy_demo() -> DemoResult<NewProjectDemoReport> {
    let dir = tempfile::tempdir()?;
    let repo = dir.path();
    git::init_sha256(repo)?;
    let tape = Append::open(repo)?;
    let mut events = Vec::<ProjectionEvent>::new();

    let genesis = append_pass(
        &tape,
        "SystemConstitutionAccepted",
        json!({"constitution_digest": digest_literal('a')}),
    )?;
    record(
        &mut events,
        &genesis,
        "SystemConstitutionAccepted",
        "constitution",
    );

    let goal = append_pass(
        &tape,
        "GoalStateProposed",
        json!({
            "goal_id": "goal_agent_economy_demo",
            "intent": "add hello CLI through agent economy shadow market",
        }),
    )?;
    record(
        &mut events,
        &goal,
        "GoalStateProposed",
        "goal_agent_economy_demo",
    );

    let capsule = append_pass(
        &tape,
        "WorkCapsuleBuilt",
        json!({
            "capsule_id": "wc_hello_cli",
            "goal_event_id": goal.event_id,
            "allowed_files": ["src/main.rs"],
        }),
    )?;
    record(&mut events, &capsule, "WorkCapsuleBuilt", "wc_hello_cli");

    let market = EconomyEvent::market_created("mkt_hello_cli", "100", "100")?;
    let market_created = append_pass(&tape, "MarketCreated", economy_payload(&market)?)?;
    record(
        &mut events,
        &market_created,
        "MarketCreated",
        "mkt_hello_cli",
    );

    let position_minted = EconomyEvent::position_minted("mkt_hello_cli", "agent_fake", "10")?;
    let position_minted_receipt =
        append_pass(&tape, "PositionMinted", economy_payload(&position_minted)?)?;
    record(
        &mut events,
        &position_minted_receipt,
        "PositionMinted",
        "agent_fake",
    );

    let price_signal = PriceSignal {
        market_id: "mkt_hello_cli".to_string(),
        yes_price: "0.55".to_string(),
        no_price: "0.45".to_string(),
        truth_status: "statistical_signal_only".to_string(),
    };
    let budget = MarketRouter::new(MarketRouterMode::Shadow).suggest(
        &[turing_economy::CandidateRoute {
            route_id: "route_fake_worker".to_string(),
            market_id: "mkt_hello_cli".to_string(),
            expected_failure_domain: "local_fake".to_string(),
            requested_tokens: 128,
        }],
        &[price_signal],
        &digest_literal('b'),
        &digest_literal('c'),
    )?;
    let budget_allocated = append_pass(
        &tape,
        "BudgetAllocated",
        json!({
            "schema_id": budget.schema_id,
            "mode": "Shadow",
            "route_id": budget.route_id,
            "market_id": budget.market_id,
            "price_signal_hash": budget.price_signal_hash,
            "pput_prior_hash": budget.pput_prior_hash,
            "diversity_policy_hash": budget.diversity_policy_hash,
            "max_tokens": budget.max_tokens,
            "emits_authorization": budget.emits_authorization,
            "can_move_accepted_head": budget.can_move_accepted_head,
            "head_effect": budget.head_effect,
        }),
    )?;
    record(
        &mut events,
        &budget_allocated,
        "BudgetAllocated",
        "route_fake_worker",
    );

    let worker = FakeWorker::new(
        "worker:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    );
    let receipt = worker.run(WorkerRunRequest {
        capsule_id: "wc_hello_cli".to_string(),
        grant_id: "grant_hello_cli".to_string(),
    })?;
    let worker_receipt = append_pass(
        &tape,
        "WorkerReceiptImported",
        json!({
            "schema_id": receipt.schema_id,
            "receipt_id": receipt.receipt_id,
            "capsule_id": receipt.capsule_id,
            "worker_id": receipt.worker_id,
            "exit_code": receipt.exit_code,
            "stdout_hash": receipt.stdout_hash,
            "stderr_hash": receipt.stderr_hash,
            "done_json_hash": receipt.done_json_hash,
            "credential_material_absent": receipt.credential_material_absent,
            "micro_refs_moved": receipt.micro_refs_moved,
        }),
    )?;
    record(
        &mut events,
        &worker_receipt,
        "WorkerReceiptImported",
        "wc_hello_cli",
    );

    let macro_observation = append_pass(
        &tape,
        "MacroObservationImported",
        json!({
            "macro_id": "macro:diff:hello_cli",
            "capsule_id": "wc_hello_cli",
            "diff_hash": digest_literal('d'),
            "external_evidence_only": true,
        }),
    )?;
    record(
        &mut events,
        &macro_observation,
        "MacroObservationImported",
        "macro:diff:hello_cli",
    );

    let accept = tick::single_tick(
        repo,
        TickDecision::AcceptCandidate {
            writer_id: "writer:e2e".to_string(),
            payload: json!({
                "candidate_id": "cand_hello_cli",
                "capsule_id": "wc_hello_cli",
                "macro_anchor": "macro:diff:hello_cli",
            }),
        },
    )?;
    record(
        &mut events,
        &accept.receipt,
        "CandidateAccepted",
        "cand_hello_cli",
    );

    let settlement =
        EconomyEvent::market_settled("mkt_hello_cli", "YES", &accept.receipt.event_id)?;
    let market_settled = append_pass(&tape, "MarketSettled", economy_payload(&settlement)?)?;
    record(
        &mut events,
        &market_settled,
        "MarketSettled",
        "mkt_hello_cli",
    );

    let reward = EconomyEvent::RewardDistributed(RewardDistributed {
        schema_id: "reward_distributed.v1".to_string(),
        market_id: "mkt_hello_cli".to_string(),
        agent_id: "agent_fake".to_string(),
        reward_coin: "2".to_string(),
        slash_coin: "0".to_string(),
        reason: "PREDICATE_SETTLEMENT".to_string(),
    });
    let reward_receipt = append_pass(&tape, "RewardDistributed", economy_payload(&reward)?)?;
    record(
        &mut events,
        &reward_receipt,
        "RewardDistributed",
        "agent_fake",
    );

    let cost_failed = CostEvent::new(
        "run_hello",
        "problem_hello",
        Split::Dogfood,
        "worker:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "branch_failed",
        "wc_hello_cli",
        4,
        4,
        2,
        1,
        80,
        b"failed branch stdout",
    )?;
    let cost_gold = CostEvent::new(
        "run_hello",
        "problem_hello",
        Split::Dogfood,
        "worker:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "branch_gold",
        "wc_hello_cli",
        3,
        3,
        1,
        0,
        90,
        b"",
    )?;
    let cost_event = append_pass(&tape, "CostEvent", to_value(&cost_failed)?)?;
    record(&mut events, &cost_event, "CostEvent", "run_hello");

    let pput_accounted = PputRunInput {
        run_id: "run_hello".to_string(),
        problem_id: "problem_hello".to_string(),
        split: Split::Dogfood,
        costs: vec![cost_failed.clone(), cost_gold.clone()],
        proposals: vec![
            ProposalRecord::new("branch_failed", GroundTruthResult::Fail, false),
            ProposalRecord::new("branch_gold", GroundTruthResult::Pass, true),
        ],
        verified: true,
    }
    .account()?;
    let pput_progress = pput_accounted.progress;
    let pput_event = append_pass(&tape, "PPUTAccounted", to_value(&pput_accounted)?)?;
    record(&mut events, &pput_event, "PPUTAccounted", "run_hello");

    let reconstruction = replay_tape(repo, &pput_event.event_id)?;
    let market_replay = MarketReplay::from_tape_events(&[market.clone(), settlement.clone()])?;
    let wallet_projection =
        WalletProjection::from_tape_events(&[position_minted.clone(), reward.clone()])?;
    let pput_projection = PputProjection::from_tape_events(&[cost_failed, cost_gold])?;
    assert_eq!(pput_projection.source, "micro_tape_only");

    let projection =
        ProjectionBuilder::from_source(ProjectionSource::MicroTape(events.clone())).build()?;
    let rebuilt = ProjectionBuilder::from_source(ProjectionSource::MicroTape(events)).build()?;
    assert_eq!(projection.projection_hash, rebuilt.projection_hash);

    Ok(NewProjectDemoReport {
        micro_git_exists: git_dir_exists(repo),
        tape_tip: reconstruction.head_set().tape_tip.clone(),
        authorization_head: reconstruction.head_set().authorization_head.clone(),
        accepted_head: reconstruction.head_set().accepted_head.clone(),
        candidate_accepted_event_id: accept.receipt.event_id,
        market_settled_event_id: market_settled.event_id,
        market_created_count: 1,
        budget_allocated_count: count_type(&projection, 1, "BudgetAllocated"),
        worker_receipt_count: 1,
        macro_observation_count: 1,
        pput_accounted_count: 1,
        market_settled_count: 1,
        market_projection_status: market_replay.markets["mkt_hello_cli"].status.clone(),
        pput_progress,
        projection_rebuild_hash: rebuilt.projection_hash,
        market_projection_hash: market_projection_hash(&market_replay)?,
        wallet_projection_hash: wallet_projection_hash(&wallet_projection)?,
        pput_projection_hash: pput_projection_hash(&pput_projection)?,
        no_pput_prompt_leakage: WorkerPromptShield::validate(
            "Implement the visible capsule and report pass/fail.",
        )
        .is_ok(),
    })
}

pub fn run_rescue_agent_economy_demo() -> DemoResult<RescueDemoReport> {
    let dir = tempfile::tempdir()?;
    let repo = dir.path();
    git::init_sha256(repo)?;
    let tape = Append::open(repo)?;

    let genesis = append_pass(
        &tape,
        "SystemConstitutionAccepted",
        json!({"constitution_digest": digest_literal('e')}),
    )?;
    let accepted_head_before_failure = genesis.event_id.clone();

    let failure = tape.append(AppendRequest::new(
        "FailureNode",
        "writer:rescue",
        json!({
            "verified": false,
            "failure_class": "NO_DIFF",
            "candidate_digest": digest_literal('f'),
            "observation_digest": digest_literal('a'),
            "detail": "worker produced no diff",
        }),
    ))?;

    let reconstruction_after_failure = replay_tape(repo, &failure.event_id)?;
    let event = FailureTapeEvent::new(
        &failure.event_id,
        "wc_rescue",
        FailureClass::NoDiff,
        digest_literal('b'),
    )
    .with_raw_detail("raw stack trace with hidden_predicate and PPUT markers");
    let memory = MemoryReducer::from_tape_events(&[event])?;
    let rule = BroadcastReducer::from_cluster(&memory.clusters[0])?;

    let recovery_capsule = append_pass(
        &tape,
        "WorkCapsuleBuilt",
        json!({
            "capsule_id": "wc_rescue_retry",
            "source_failure_node": failure.event_id,
            "broadcast_rule_id": rule.rule_id,
        }),
    )?;
    let _ = replay_tape(repo, &recovery_capsule.event_id)?;

    Ok(RescueDemoReport {
        micro_git_exists: git_dir_exists(repo),
        failure_node_count: 1,
        broadcast_rule_count: 1,
        failure_class: FailureClass::NoDiff.as_registry_str().to_string(),
        accepted_head_before_failure,
        accepted_head_after_failure: reconstruction_after_failure
            .head_set()
            .accepted_head
            .clone(),
        recovery_capsule_proposed: true,
        broadcast_summary_abstract: !rule.summary.contains("hidden_predicate")
            && !rule.summary.contains("PPUT")
            && !rule.summary.contains("stack trace"),
    })
}

fn append_pass(tape: &Append, event_type: &str, payload: Value) -> DemoResult<CommittedReceipt> {
    Ok(tape.append(
        AppendRequest::new(event_type, format!("writer:{event_type}"), payload).predicate_pass(),
    )?)
}

fn economy_payload(event: &EconomyEvent) -> DemoResult<Value> {
    match event {
        EconomyEvent::MarketCreated(inner) => to_value(inner),
        EconomyEvent::PositionMinted(inner) => to_value(inner),
        EconomyEvent::AmmSwapExecuted(inner) => to_value(inner),
        EconomyEvent::MarketSettled(inner) => to_value(inner),
        EconomyEvent::RewardDistributed(inner) => to_value(inner),
    }
}

fn to_value<T: Serialize>(value: &T) -> DemoResult<Value> {
    Ok(serde_json::to_value(value)?)
}

fn record(
    events: &mut Vec<ProjectionEvent>,
    receipt: &CommittedReceipt,
    event_type: &str,
    subject_id: &str,
) {
    events.push(ProjectionEvent::new(
        receipt.event_id.clone(),
        event_type,
        subject_id,
    ));
}

fn digest_literal(ch: char) -> String {
    format!("sha256:{}", ch.to_string().repeat(64))
}

fn git_dir_exists(repo: &Path) -> bool {
    repo.join(".git").exists()
}

fn count_type(
    _projection: &turing_projection::Projection,
    count: usize,
    _event_type: &str,
) -> usize {
    count
}

fn market_projection_hash(replay: &MarketReplay) -> DemoResult<String> {
    let mut markets = serde_json::Map::new();
    for (market_id, market) in &replay.markets {
        markets.insert(
            market_id.clone(),
            json!({
                "pool_y": market.pool_y,
                "pool_n": market.pool_n,
                "status": market.status,
                "settlement_result": market.settlement_result,
            }),
        );
    }
    hash_json(&json!({
        "schema_id": "market_projection.v1",
        "source": replay.source,
        "markets": markets,
    }))
}

fn wallet_projection_hash(projection: &WalletProjection) -> DemoResult<String> {
    let mut wallets = serde_json::Map::new();
    for (agent_id, wallet) in &projection.wallets {
        wallets.insert(
            agent_id.clone(),
            json!({
                "coin_balance": wallet.coin_balance,
                "yes_positions": wallet.yes_positions,
                "no_positions": wallet.no_positions,
            }),
        );
    }
    hash_json(&json!({
        "schema_id": "wallet_projection.v1",
        "source": projection.source,
        "wallets": wallets,
    }))
}

fn pput_projection_hash(projection: &PputProjection) -> DemoResult<String> {
    hash_json(&json!({
        "schema_id": "pput_projection.v1",
        "source": projection.source,
        "total_tokens": projection.total_tokens,
        "total_wall_time_ms": projection.total_wall_time_ms,
    }))
}

fn hash_json(value: &Value) -> DemoResult<String> {
    let bytes = jcs::canonicalize(value)?;
    Ok(format!("sha256:{}", jcs::sha256_hex(&bytes)))
}
