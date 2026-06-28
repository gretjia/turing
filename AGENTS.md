# TuringOS Repository Instructions

This file extends the workspace-level `AGENTS.md`; it does not ratify or
override `TOP_ALIGNMENT_PROJECT_BOOK.md`.

## Full SWE-bench Loop Memory

For any SWE-bench, Phase F, Stage16R, Phase G, full-campaign, or MicroTape
release work, read these files before changing code or evidence:

- `.claude/agent-memory/full_swe_bench_loop_reflection.md`
- `docs/handoff/FULL_SWE_BENCH_READY_LOOP_ENGINEERING_PLAN.md`
- `evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json`

## Non-Negotiable Release Rules

- A blocker packet is not a release artifact.
- A fixture PASS is not a real-world capability PASS.
- A repair-loop structural PASS is not Phase G release.
- Phase G/full-campaign launch requires Phase F evaluator proof PASS with
  executable official evaluator replay.
- Current old Stage16R MicroTape bundles are immutable; supersede with fresh
  bundles, never rewrite.
- Dataset gold patches, official solution patches, hidden heldout labels,
  credentials, auth caches, signing material, and private keys are forbidden as
  candidate sources or visible evidence.
- Full SWE-bench score claims are forbidden until the full dataset manifest is
  frozen with `selection_policy=ALL`, every task has official PASS,
  `unsolved_count == 0`, final PPUT progress is 1 for every task, all cost/time
  derives from MicroTape, and the exact-SHA external audit releases the claim.

## Current Loop Stop

As of the full-readiness gate, TuringOS is ready to start a sealed
SWE-bench Verified 500 campaign. This is a launch-readiness claim only, not a
full-score result, leaderboard-equivalence claim, or P1/P2 product claim.

The correct next loop is:

```text
start SWE-bench Verified 500 sharded sealed campaign
-> every instance writes a MicroTape bundle
-> solved: official PASS -> CandidateAccepted -> final PPUT progress=1
-> unsolved: no CandidateAccepted -> final PPUT progress=0
-> strict audit every shard
-> repair only unsolved frontier
-> full-score claim gate only if unsolved_count == 0 across all 500
```
