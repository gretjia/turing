use std::process::ExitCode;

use turing_qualification::{run_new_project_agent_economy_demo, run_rescue_agent_economy_demo};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let words: Vec<&str> = args.iter().map(String::as_str).collect();

    match dispatch(&words) {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(message) => {
            eprintln!("{message}");
            ExitCode::from(2)
        }
    }
}

fn dispatch(args: &[&str]) -> Result<String, String> {
    match args {
        ["replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("replay verify failed: {error}"))?;
            Ok(format!(
                "replay: verified tape_tip={} accepted_head={} qualification=private-local",
                report.tape_tip, report.accepted_head
            ))
        }
        ["market", "replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("market replay failed: {error}"))?;
            Ok(format!(
                "market replay: verified status={} market_settled_count={} price_not_truth=true",
                report.market_projection_status, report.market_settled_count
            ))
        }
        ["pput", "replay", "--verify"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("pput replay failed: {error}"))?;
            Ok(format!(
                "pput replay: verified progress={} hidden_from_worker_prompt=true",
                report.pput_progress
            ))
        }
        ["audit", "invariants"] => {
            let new_project = run_new_project_agent_economy_demo()
                .map_err(|error| format!("invariant audit failed: {error}"))?;
            let rescue = run_rescue_agent_economy_demo()
                .map_err(|error| format!("invariant audit failed: {error}"))?;
            Ok(format!(
                "audit invariants: pass accepted_head={} failure_preserved_head={}",
                new_project.accepted_head, rescue.accepted_head_after_failure
            ))
        }
        ["audit", "market"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("market audit failed: {error}"))?;
            Ok(format!(
                "audit market: pass settled={} accepted_head_not_market_settlement=true",
                report.market_settled_count
            ))
        }
        ["audit", "pput"] => {
            let report = run_new_project_agent_economy_demo()
                .map_err(|error| format!("pput audit failed: {error}"))?;
            Ok(format!(
                "audit pput: pass progress={} no_pput_prompt_leakage={}",
                report.pput_progress, report.no_pput_prompt_leakage
            ))
        }
        _ => Err(format!(
            "unknown turing command: {:?}. supported: replay --verify | market replay --verify | pput replay --verify | audit invariants|market|pput",
            args
        )),
    }
}
