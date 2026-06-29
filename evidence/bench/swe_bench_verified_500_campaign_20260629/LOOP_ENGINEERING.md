# Loop Engineering: Verified 500 Campaign Controller

## Current State

TuringOS is released to the official-campaign execution gate, not to a result
claim. The upstream SWE-bench Docker harness identity and Phase F 20-task
qualification are READY at commit d055ae4bd013ff09298ae8af576ebdbcf32a4e8c.
The campaign has not started running the 500 tasks.

The immediate frontier is shard S00. S00 remains BLOCKED until it has exactly
one worker-derived unified-diff prediction for every task in the 50-task shard.
The runner must not execute, or mark execution ready, from missing predictions,
dataset gold patches, repo-local evaluator outputs, empty patches, or task
summaries.

S00-W00 now has worker-safe task packets materialized under
`shards/S00/ipqc/S00-W00/worker_safe_tasks/`. These packets intentionally omit
dataset gold patches, test patches, hidden evaluator labels, and hints. They
are preparation evidence only; they are not predictions and do not start the
official harness.

S00-W00 is complete with ten audited worker-derived source-only candidate
patches. S00-W01 worker-safe task packets are materialized and ready for
independent workers. S00 is still only 10/50 predictions. It does not release
S00.

This packet makes the next loop executable without drift:

1. freeze 500-task manifest;
2. split into 10 sealed 50-task shards;
3. require 10-task IPQC windows;
4. build predictions only from worker-derived patches;
5. audit gold-patch guard;
6. record upstream official harness command packet;
7. audit each 50-task shard before continuing;
8. reduce 10 shard audits only after all shard gates pass.

## Outer Loop

```text
while official_campaign_not_complete:
  read exact-SHA official harness readiness gate
  freeze/read campaign manifest
  for shard in S00..S09:
    materialize worker-safe task packets for the next 10-task IPQC window
    audit each worker candidate patch before prediction assembly
    build worker-derived predictions for all 50 shard tasks
    block if predictions are incomplete or non-worker-derived
    run each instance as its own atom
    emit IPQC every 10 tasks
    stop after 50 tasks
    run shard audit
    release next shard only if shard PASS
  reduce campaign only if 10/10 shards PASS
```

## Stop Conditions

- gold patch shortcut suspected;
- repo-local evaluator marked official;
- upstream Docker harness evidence missing;
- required evidence missing;
- digest mismatch;
- MicroTape replay mismatch;
- credential material detected;
- shard manifest task missing or duplicated.
- shard predictions missing, duplicated, not unified diffs, or not
  worker-derived.

## Current Deliverable Boundary

This is a controller scaffold and manifest freeze packet plus the S00 execution
gate. It is suitable for external audit of launch gates. It is not execution
evidence and not a result packet until shard task predictions, official harness
logs, evaluation results, MicroTape bundles, IPQC reports, and shard audit
artifacts exist.
