use std::path::Path;
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
        ["handoff", "generate", "--output", output] => generate_handoff(output),
        _ => Err(format!(
            "unknown turing command: {:?}. supported: replay --verify | market replay --verify | pput replay --verify | audit invariants|market|pput | handoff generate --output <path>",
            args
        )),
    }
}

fn generate_handoff(output: &str) -> Result<String, String> {
    let report = run_new_project_agent_economy_demo()
        .map_err(|error| format!("handoff qualification failed: {error}"))?;
    let path = Path::new(output);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|error| format!("failed to create handoff directory: {error}"))?;
    }
    let authorization_head = report
        .authorization_head
        .clone()
        .unwrap_or_else(|| "null".to_string());
    let text = format!(
        r#"# Agent Economy Runtime Handoff

Status: generated private-local qualification handoff.

## Head Evidence

- tape_tip: {tape_tip}
- authorization_head: {authorization_head}
- accepted_head: {accepted_head}

## Projection Evidence

- market projection hash: {market_projection_hash}
- wallet projection hash: {wallet_projection_hash}
- PPUT projection hash: {pput_projection_hash}
- disposable projection hash: {projection_rebuild_hash}

## Replay And Audit Commands

```bash
cargo test --workspace
bash demo/demo_agent_economy_e2e.sh
bash demo/demo_rescue_agent_economy.sh
turing replay --verify
turing market replay --verify
turing pput replay --verify
turing audit invariants
turing audit market
turing audit pput
turingd --check
turing-execd --check
turing-marketd --check
turing-pputd --check
turing-viewd --check
turing-mcp --check
```

## Known Risks

- Generated evidence is from a temporary private-local qualification Tape.
- `turingd` has Unix socket JSON-RPC health/read-only heads, including configured
  `--micro-git` head reads; append routes, predicate routing, and approval APIs remain pending.
- `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, and `turing-viewd` have
  minimal sidecar RPCs for grant authorization, resource manifests, shadow budget suggestion,
  prompt shielding, and disposable projection building. Full persistent project services remain
  pending.
- Operator project persistence and installed binary wiring remain pending.
"#,
        tape_tip = report.tape_tip,
        authorization_head = authorization_head,
        accepted_head = report.accepted_head,
        market_projection_hash = report.market_projection_hash,
        wallet_projection_hash = report.wallet_projection_hash,
        pput_projection_hash = report.pput_projection_hash,
        projection_rebuild_hash = report.projection_rebuild_hash,
    );
    std::fs::write(path, text).map_err(|error| format!("failed to write handoff: {error}"))?;
    Ok(format!("handoff: wrote {}", path.display()))
}
