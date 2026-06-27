# ADR: Agent Economy as Organization

Status: Accepted for P0 Greenfield execution baseline

## Context

TuringOS is not a workflow engine with agents attached. The Greenfield runtime is a constitution-bound local operating substrate where agents generate candidate worlds, while predicate, signature, tape, and replay preserve sovereignty.

The old Greenfield foundation correctly chose Rust authority, native SHA-256 Git Micro Tape, three refs, 7-field append, capability grants, receipts, evidence, approval, and replay. The missing layer was the organization form for many workers and planners.

## Decision

Agent Economy is the organization layer for the swarm.

```text
Predicate settles truth.
Signature settles sovereignty.
Tape settles memory.
Market settles attention.
PPUT settles progress efficiency.
Workers generate candidates.
Constitution governs everything.
```

Parallel, A*, Beam, MCTS, and RL are not sovereign controllers. They are market strategy subsets:

- Parallel is flat-price exploration.
- A* is path quote policy.
- Beam is candidate reranking.
- MCTS is bounded local market tree search.
- RL is future budget or portfolio policy only.

All of these strategies execute inside the Single Loop:

```text
Read -> Propose -> Verify -> Write/Reject -> Compress -> Broadcast/Shield -> Halt?
```

No planner, market, PPUT, dashboard, TUI, MCP, or worker subsystem may become a second runtime loop.

## Consequences

- `turingd` remains the sovereign kernel and owns head movement.
- `turing-marketd` and `turing-pputd` are derived reducers/accountants, not truth owners.
- Workers receive visible capsules and bounded grants, not hidden predicates or hidden scoring internals.
- The market can change attention and suggested budget, but cannot authorize macro actions or advance `accepted_head`.

## Gates

- `G-CONST-01 tape_reconstructs_all_state`
- `G-LOOP-01 single_loop_purity`
- `G-MKT-07 marketrouter_shadow_no_authority`
- `G-PPUT-05 no_pput_in_worker_prompt`
