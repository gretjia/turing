# ADR: Held-Out Verified PPUT as North Star

Status: Accepted for P0 Greenfield execution baseline

## Context

Solve rate alone rewards unmetered search, slow brute force, failed hidden trials, and prompt leakage. The Greenfield Agent Economy runtime needs an efficiency metric that accounts for physical cost while preserving predicate truth and worker isolation.

The north star is held-out Verified PPUT, under constitutional constraints.

```text
Progress_i = 1 iff verified golden path exists.
VPPUT_i = 1[GroundTruth(G_i)=1] / (C_i * T_i)
PPUT-M = 1_000_000 * VPPUT_i
```

`C_i` includes all agents, branches, failed proposals, hidden trials, reranks, tool calls, tool stdout context, abandoned market bets, replay verification, and other counted token costs. `T_i` is wall time from first read to final accept.

## Decision

PPUT is a hidden evaluator, not a Worker-visible objective.

The runtime must implement cost events and replayable PPUT accounting, but ordinary Workers must not receive raw formulas, heldout IDs, metric files, hidden evaluator thresholds, or other Goodhart-sensitive internals.

Required PPUT event families:

- `CostEvent`
- `BranchCostEvent`
- `ToolStdoutCostEvent`
- `PPUTProposalRecord`
- `PPUTAccounted`
- `HeldoutGuardViolation`

No PPUT in Worker prompt is a first-class architectural decision. Workers may see budget remaining, allowed commands, abstract failure rules, and pass/fail errors. They may not see the raw PPUT target or heldout identifiers.

## Consequences

- Failed branches count toward total cost even when they produce no accepted artifact.
- Tool stdout must be hashed and costed when it enters context.
- Hidden evaluator work is still physical cost.
- Progress is zero without a verified golden path.
- PPUT projections must be rebuildable from Micro Tape.

## Gates

- `G-PPUT-01 all_tokens_counted`
- `G-PPUT-02 failed_branches_counted`
- `G-PPUT-03 pput_replay_from_tape`
- `G-PPUT-05 no_pput_in_worker_prompt`
- `G-PPUT-06 heldout_guard`
- `G-PPUT-07 ground_truth_required_for_progress`
