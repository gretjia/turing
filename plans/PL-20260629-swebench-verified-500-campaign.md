# PL-20260629 SWE-bench Verified 500 Campaign Controller

Status: implemented as launch-gate scaffolding only.

## Scope

This plan records the loop engineering for an internal upstream SWE-bench
Docker-harness campaign over SWE-bench Verified 500. It does not start the
500-task run, does not claim full score, and does not claim leaderboard
equivalence.

## Required Loops

1. Official harness qualification: upstream `python -m swebench.harness.run_evaluation`, Docker evidence, evaluation results, FAIL_TO_PASS, and PASS_TO_PASS.
2. Manifest freeze: 500 tasks, selection_policy=ALL, 10 shards x 50, 10-task IPQC windows.
3. Shard execution: one task at a time, one worker-derived patch per prediction row, official Docker harness evidence per task.
4. Shard audit: every 50 tasks hard stop, SG-01..SG-10 must pass.
5. Campaign reducer: 10/10 shard PASS, 500 unique tasks, claim boundary clean.

## Non-Negotiable Boundaries

- one-shot 500 run is forbidden.
- repo-local evaluator cannot be marked official.
- dataset gold patch or official solution patch cannot be a candidate source.
- dashboard/projection/summary JSON is never truth.
- MicroTape replay and required evidence are mandatory for release.
- leaderboard equivalence is false unless an external leaderboard submission is accepted.

## Current Gate State

Official campaign launch remains blocked until upstream SWE-bench Docker
harness identity is proven. The current implementation is ready to freeze and
audit the control plane and to support an internal rehearsal.
