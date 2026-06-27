# Agent Economy Runtime Handoff

Status: qualification checkpoint, not full product completion.

This handoff records the current Greenfield Rust substrate state for
`TuringOS_Agent_Economy_Runtime_Greenfield_v1_0`. The implementation currently has
native SHA-256 Micro Tape, replay, Single Loop tick, worker receipts, macro anchors,
predicate gates, evidence/approval, failure memory, Agent Economy substrate,
MarketRouter shadow mode, hidden PPUT accounting, disposable projection, integration
queue gates, and two local e2e qualification demos.

## Head Evidence

The e2e qualification runner creates a fresh private-local Micro Tape and verifies:

- `tape_tip`: reconstructed from the final appended Micro event in the demo Tape.
- `authorization_head`: preserved unless an authorization event is appended.
- `accepted_head`: advances only on `CandidateAccepted` after predicate PASS.

The runner also verifies that `MarketSettled` is `PRESERVE` and does not become
`accepted_head`.

## Projection Evidence

- market projection hash: required final handoff field; current code verifies market
  replay from Tape through `turing-economy::MarketReplay`.
- wallet projection hash: required final handoff field; current code verifies wallet
  replay from Tape through `turing-economy::WalletProjection` unit coverage.
- PPUT projection hash: required final handoff field; current code verifies PPUT replay
  from Tape through `turing-pput::PputProjection`.
- disposable projection hash: verified by
  `turing-qualification::run_new_project_agent_economy_demo()` via
  `projection_rebuild_hash`.

## Replay And Audit Commands

Current executable commands:

```bash
cargo test --workspace
bash demo/demo_agent_economy_e2e.sh
bash demo/demo_rescue_agent_economy.sh
cargo run -p turing-cli -- replay --verify
cargo run -p turing-cli -- market replay --verify
cargo run -p turing-cli -- pput replay --verify
cargo run -p turing-cli -- audit invariants
cargo run -p turing-cli -- audit market
cargo run -p turing-cli -- audit pput
```

CLI parity commands exposed by the `turing` binary target:

```bash
turing replay --verify
turing market replay --verify
turing pput replay --verify
turing audit invariants
turing audit market
turing audit pput
```

## Current Coverage

- New-project e2e: `bash demo/demo_agent_economy_e2e.sh`
- Rescue-project e2e: `bash demo/demo_rescue_agent_economy.sh`
- Full Rust workspace: `cargo test --workspace`

## Known Risks

- The `turing` CLI exists as a Rust binary target, but packaging/install wiring is not done.
- `turingd`, `turing-marketd`, `turing-pputd`, `turing-viewd`, and `turing-mcp` are not yet
  wired as long-running daemons.
- Market projection hash, wallet projection hash, and PPUT projection hash are verified
  through Rust projection/replay APIs but not yet emitted as persistent handoff fields by
  a CLI generator.
- Demo tapes are temporary private-local qualification tapes; a persistent operator
  project handoff still needs a concrete project data directory and stable Micro refs.
- The final halt condition is not satisfied until CLI replay/audit commands, daemon wiring,
  persistent handoff generation, and full product shell are complete.
