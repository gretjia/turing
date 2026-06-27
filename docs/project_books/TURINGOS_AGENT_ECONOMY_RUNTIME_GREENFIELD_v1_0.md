# TuringOS Agent Economy Runtime Greenfield v1.0

Status: active execution baseline for `/goal TuringOS_Agent_Economy_Runtime_Greenfield_v1_0`.

This project book installs the Greenfield Agent Economy upgrade as the local P0 build law for the Rust workspace. It preserves the old Greenfield foundation where correct and upgrades it with the Agent Economy organization layer, AMM/CTF market substrate, WalletProjection, MarketRouter shadow mode, hidden PPUT accounting, and anti-Goodhart gates.

## Source Pack

This book is derived from:

- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/README.md`
- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/00_GAP_ANALYSIS.md`
- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/00_ABSORPTION_LEDGER.md`
- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/TURINGOS_GREENFIELD_ARCHITECTURE_AND_STACK.md`
- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/01_AGENT_ECONOMY_MARKET_PPUT_SPEC.md`
- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/02_MODULE_ATOM_SHIPGATE_EXECUTION_PLAN.md`
- `turingos_research/GREENFIELD_ARCHITECTURE_PLAN_AGENT_ECONOMY_RUNTIME_v1_0/03_ONE_SHOT_GOAL_COMMAND.md`

## One-Shot Goal

```text
/goal TuringOS_Agent_Economy_Runtime_Greenfield_v1_0
```

Mission:

Build the P0 private-local TuringOS Agent Economy Runtime on the Greenfield Rust substrate. Preserve native SHA-256 Git Micro Tape, three refs, 7-field append, Rust `turingd` / `turing-execd` / `turing-mcp`, Capability-Grant, Receipt, Evidence, Approval, and Replay. Upgrade the runtime with AMM/CTF markets, WalletProjection, MarketRouter shadow mode, hidden PPUT accounting, and price/PPUT anti-Goodhart gates.

## Governing Law

Conflict order:

1. Constitution: `# Turingos 宪法.md`
2. Product law: `Turing Agentic OS 白皮书 v0.6`
3. Phase-0 ratified Greenfield decisions
4. TuringOS Agent Economy Runtime v1.0
5. Old Greenfield docs
6. Implementation

Runtime law:

```text
Read -> Propose -> Verify -> Write/Reject -> Compress -> Broadcast/Shield -> Halt?
```

No module may create a second runtime loop. Market, PPUT, projection, MCP, TUI, and dashboard code are Single Loop subroutines or derived reducers only.

## North Star

Maximize held-out Verified PPUT under constitutional constraints.

Progress is credited only when a verified golden path exists. All failed branches, hidden trials, tool stdout, reranks, abandoned market bets, and wall time count as physical cost.

PPUT is hidden evaluation. It is not a Worker-visible objective and must not be included in ordinary Worker prompts.

## Core Thesis

```text
Predicate settles truth.
Signature settles sovereignty.
Tape settles memory.
Market settles attention.
PPUT settles progress efficiency.
Workers generate candidates.
Constitution governs everything.
```

Agent Economy is the organization layer. Parallel, A*, Beam, MCTS, and RL are strategy subsets inside the market. Price is a statistical signal, not truth.

## Process Topology

- `turingd`: sovereign kernel, Single Loop, Micro append, refs, predicates, approval route. It does not run arbitrary shell and does not call vendor model SDKs directly.
- `turing-execd`: Capability-Grant broker, sandbox, worker process groups, scoped environment, timeouts, receipts. It cannot move heads.
- `turing-mcp`: protocol edge with read-only resources and typed commands. It owns no truth.
- `turing-marketd`: derived market reducer, AMM/CTF, WalletProjection, MarketRouter shadow suggestions. It owns no truth and cannot move `accepted_head`.
- `turing-pputd`: hidden accountant for CostEvent, VPPUT, PPUT-M, heldout accounting, and anti-Goodhart checks. It cannot expose raw PPUT objectives to Workers.
- `turing-viewd`: projection and dashboard builder. Disposable; no truth.

## Sovereign Assets

Founder-owned sovereign assets:

1. Tape
2. Predicate
3. Capability-Grant
4. Receipt
5. Projection-Contract

Derived economic assets:

1. MarketProjection, derived from tape and never truth
2. PPUTAccounting, derived from tape and hidden from Workers

## Micro Tape Invariants

Micro Tape is a native SHA-256 bare Git repository using CLI plumbing unless a later ratified decision explicitly replaces it.

Refs:

```text
refs/turingos/tape_tip
refs/turingos/authorization_head
refs/turingos/accepted_head
```

Rules:

- `tape_tip` advances on all valid appends, including failures and economy events.
- `authorization_head` advances only on valid authorization events.
- `accepted_head` advances only on sovereign accept events.
- Authorization is permission, not completion.
- Macro artifacts are `macro:*` anchors, never Micro identities.

Every Micro append envelope carries:

```yaml
writer_id: string
authority_epoch: string
prev_tape_tip: string
accepted_head_before: string
head_effect: ADVANCE | PRESERVE
event_schema_id: string
payload_hash: sha256:<hex>
```

All economy events default to `head_effect: PRESERVE`.

## Canonical Data Rules

- Load-bearing keys are ASCII only.
- Non-ASCII values are allowed where they are human-facing content.
- No floats in load-bearing payloads.
- Money, price, ratios, and AMM values use fixed units or `decimal_string`.
- Content digests are `sha256(JCS(content))`.
- `jq -cS` is not a load-bearing canonicalization mechanism.

## Agent Economy Requirements

Market decides attention. Predicate decides truth. Signature decides sovereignty. Tape remembers all.

P0 is Market Shadow Mode:

- Market events, wallet projection, and PPUT accounting must exist.
- CapabilityProfileRouter still performs dispatch.
- MarketRouter only emits suggestions.
- No market event can authorize dispatch, merge, delete, release, or move `accepted_head`.

CTF invariant:

```text
1 Coin = 1 YES + 1 NO
```

CPMM invariant:

```text
poolY * poolN = k
```

Buy YES:

```text
dN = payC
dY = - payC * poolY / (payC + poolN)
getY = payC + payC * poolY / (payC + poolN)
priceY = payC / getY
poolY1 = poolY - payC * poolY / (payC + poolN)
poolN1 = poolN + payC
```

Buy NO is symmetric:

```text
dY = payC
dN = - payC * poolN / (payC + poolY)
getN = payC + payC * poolN / (payC + poolY)
priceN = payC / getN
poolN1 = poolN - payC * poolN / (payC + poolY)
poolY1 = poolY + payC
```

Market events to implement additively:

- `MarketCreated`
- `MarketLiquidityAdded`
- `PositionMinted`
- `AMMSwapExecuted`
- `AgentBidSubmitted`
- `BudgetAllocated`
- `MarketPriceBroadcast`
- `MarketSettled`
- `RewardDistributed`

WalletProjection is replay-derived only. Deleting projection state and replaying from tape must reproduce balances, YES/NO positions, rewards, slashes, and open markets.

## PPUT Requirements

Definitions:

```text
Progress_i = 1 iff verified golden path exists.
VPPUT_i = 1[GroundTruth(G_i)=1] / (C_i * T_i)
PPUT-M = 1_000_000 * VPPUT_i
```

Cost includes:

- all agents
- all branches
- failed proposals
- hidden trials
- reranks
- tool calls
- tool stdout context
- abandoned market bets
- replay and verification tool tokens
- wall time from first read to final accept

PPUT events:

- `CostEvent`
- `BranchCostEvent`
- `ToolStdoutCostEvent`
- `PPUTProposalRecord`
- `PPUTAccounted`
- `HeldoutGuardViolation`

Shield rules:

- Workers may see budget remaining, allowed commands, abstract failure rules, and pass/fail errors.
- Workers may not see raw VPPUT formula, heldout IDs, hidden evaluator thresholds, metric files, other branches' raw failure logs, or hidden predicates.

## Strategy Layer

| Strategy | Market identity | Allowed | Forbidden |
|---|---|---|---|
| Parallel | flat-price market | cold-start exploration | final organization theory |
| A* | bidder/path quote policy | dependency/cost path | predicate replacement |
| Beam | candidate reranker | text/patch/command ranking | execution authority |
| MCTS | local market tree | bounded simulation | global runtime control |
| RL | future portfolio policy | route/budget/tool selection | merge/delete/publish/heads |
| Human approval | sovereign route | high-risk authorization | price bypass |

## Atom Execution Loop

Every Atom follows:

1. Intent: restate atom contract, allowed files, forbidden files, and risk.
2. Acceptance first: write or identify runnable acceptance commands before code.
3. Market: create or reuse AgentMarket; seed flat liquidity if cold; allocate suggestion budget only.
4. Implement: Worker modifies only allowed Macro worktree files.
5. Simplify: remove bloat without semantic change.
6. Verify: run tests, predicates, replay, market audit, and PPUT audit relevant to the Atom.
7. Mini-Recovery: on failure, classify FailureClass, append FailureNode, patch minimally, rerun.
8. Reflect: extract abstract BroadcastRule only; do not broadcast raw logs.
9. Ship: commit Atom, record receipts, update handoff when requested.
10. Halt check: halt only if GoalState predicates pass, no open P0/P1 sovereign risk remains, heads are final, replay passes, market/PPUT projections replay, and handoff exists.

## Do Not Build

- No MarketLoop or PPUTLoop.
- No market sidecar, pputd, viewd, TUI, MCP, or projection truth ownership.
- No PPUT formula in Worker prompts.
- No raw failure-log broadcast.
- No price, PPUT, CI green, PR open, HTTP 200, vendor approval, or `exit_code=0` as accepted truth.
- No RL direct merge, delete, publish, credential, or head advancement.
- No credential material on tape, logs, receipts, prompts, CAS, or projections.
- No real-money semantics in P0.
- No floats in load-bearing market or PPUT payloads.
- No non-ASCII load-bearing keys.

## Rust Workspace Target Layout

```text
crates/
  turing-contracts/
  turing-git-tape/
  turing-predicate/
  turing-approval/
  turing-evidence/
  turing-capability/
  turing-execd/
  turing-market/
  turing-pput/
  turing-loop/
  turing-mcp/
  turing-view/
  turing-cli/

daemons/
  turingd/
  turing-execd/
  turing-mcp/
  turing-marketd/
  turing-pputd/

docs/
  adr/
  specs/
  project_books/
  handoff/

tests/
  unit/
  integration/
  e2e/
  audit/
  fixtures/

demo/
  demo_agent_economy_e2e.sh
  demo_rescue_agent_economy.sh
```

## Module Roadmap

| Module | Goal | Core output |
|---|---|---|
| M0 | Law + ADR + package harness | project book, `/goal`, ADRs |
| M1 | Canonical codec | JCS/no-float/ASCII keys |
| M2 | Git Micro Tape | SHA-256 bare repo, refs, append, replay |
| M3 | Event registry | 46+ additive economy events |
| M4 | Single Loop | `tick(Q,G)` only runtime loop |
| M5 | Goal/Module/Atom/Capsule | compiler + shield |
| M6 | Worker profiles | dispatch purpose + receipts |
| M7 | Executor broker | CapabilityGrant + sandbox + receipts |
| M8 | Macro observer | worktree / branch / PR / CI anchors |
| M9 | Predicate kernel | micro/capsule/macro/market/pput predicates |
| M10 | Evidence + Approval | retention + tombstone + signing |
| M11 | Failure memory | classifier + abstract broadcast |
| M12 | Market substrate | CTF + CPMM + market replay |
| M13 | MarketRouter shadow | price signals, no authority |
| M14 | PPUT accounting | cost events, VPPUT, no leak |
| M15 | Projection | dashboard / UI data / rebuild |
| M16 | Integration queue | CAS, drift guard, no auto-main |
| M17 | E2E + handoff | demos, audits, final handoff |

## M0-A01 Atom Contract

```yaml
atom_id: M0-A01
title: install upgraded project book
owns:
  - docs/project_books/TURINGOS_AGENT_ECONOMY_RUNTIME_GREENFIELD_v1_0.md
does_not_own:
  - crates/*
  - src/*
  - contracts/*
  - schemas/*
  - tests/*
allowed_files:
  - docs/project_books/TURINGOS_AGENT_ECONOMY_RUNTIME_GREENFIELD_v1_0.md
forbidden_files:
  - crates/**
  - src/**
  - contracts/**
  - schemas/**
  - tests/**
risk:
  risk_class: P0
  human_before_dispatch: false
  human_before_accept: false
  human_before_merge: true
acceptance_commands:
  - command: grep -q "Agent Economy" docs/project_books/TURINGOS_AGENT_ECONOMY_RUNTIME_GREENFIELD_v1_0.md
    timeout_seconds: 5
    expected_exit_codes: [0]
    evidence_kind: audit
rollback: remove docs/project_books/TURINGOS_AGENT_ECONOMY_RUNTIME_GREENFIELD_v1_0.md
shipgates:
  - G-CONST-01
```

## Global Shipgates

- `G-CONST-01 tape_reconstructs_all_state`
- `G-CONST-02 no_macro_identity_confusion`
- `G-LOOP-01 single_loop_purity`
- `G-MKT-01 ctf_conservation`
- `G-MKT-02 cpmm_invariant`
- `G-MKT-03 market_replay_from_tape`
- `G-MKT-04 wallet_projection_replay_from_tape`
- `G-MKT-05 price_not_predicate`
- `G-MKT-07 marketrouter_shadow_no_authority`
- `G-PPUT-01 all_tokens_counted`
- `G-PPUT-02 failed_branches_counted`
- `G-PPUT-03 pput_replay_from_tape`
- `G-PPUT-05 no_pput_in_worker_prompt`
- `G-EV-02 approval_bytes_four_way`
- `G-MACRO-01 no_irreversible_action_without_auth`
- `G-PROJ-01 projection_rebuild`
- `G-E2E-01 new_project_agent_economy`
- `G-E2E-02 rescue_project_agent_economy`
- `G-E2E-03 final_handoff`

## Final Gate Bundle

```bash
cargo test --workspace
cargo test --workspace --features audit
bash demo/demo_agent_economy_e2e.sh
bash demo/demo_rescue_agent_economy.sh
turing replay --verify
turing market replay --verify
turing pput replay --verify
turing audit invariants
turing audit market
turing audit pput
```

## Definition of Done

- `/goal` bootstrap works.
- GoalState -> Module -> Atom -> WorkCapsule works.
- Single Loop tick runs.
- Worker writes only in isolated worktree.
- Tool calls produce receipts.
- Macro evidence imports as `macro:*` anchors.
- Predicate accepts or rejects candidate.
- Failure path appends FailureNode.
- MarketCreated / AMMSwapExecuted / MarketSettled replay.
- WalletProjection replay.
- PPUTAccounted replay.
- Price cannot move `accepted_head`.
- PPUT is hidden from Worker prompt.
- ApprovalCard canonical bytes match visible hash, signed bytes, gate bytes, and replay bytes.
- REQUIRED evidence is immutable.
- Projection rebuilds from tape.
- MCP/TUI is projection-only.
- New-project e2e demo passes.
- Rescue-project e2e demo passes.
- Final handoff is generated with `tape_tip`, `authorization_head`, `accepted_head`, market projection hash, wallet projection hash, PPUT projection hash, replay commands, and known risks.
