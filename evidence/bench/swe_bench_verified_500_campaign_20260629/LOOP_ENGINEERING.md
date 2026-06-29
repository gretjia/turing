# Loop Engineering: Verified 500 Campaign Controller

## Current State

TuringOS is not released to start the official SWE-bench Verified 500 campaign.
The official launch remains blocked until upstream SWE-bench Docker harness
identity is proven with `python -m swebench.harness.run_evaluation`, Docker
evidence, evaluation results, FAIL_TO_PASS, and PASS_TO_PASS.

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
  qualify upstream official harness
  freeze/read campaign manifest
  for shard in S00..S09:
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

## Current Deliverable Boundary

This is a controller scaffold and manifest freeze packet. It is suitable for an
internal rehearsal or for external audit of launch gates. It is not execution
evidence and not a result packet.
