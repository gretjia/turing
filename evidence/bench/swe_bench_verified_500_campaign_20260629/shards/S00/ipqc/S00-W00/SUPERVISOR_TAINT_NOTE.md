# S00-W00 Supervisor Taint Note

During controller development, the supervising Codex process inspected the local
SWE-bench Verified Arrow schema and printed the first raw dataset row to verify
available columns. That raw row included dataset-only fields for
`astropy__astropy-12907`.

No candidate patch has been generated from that inspection, and S00 remains
blocked because no shard predictions exist.

Integrity rule for this task:

```text
astropy__astropy-12907 candidate patch must be produced by an independent
worker context that receives only the worker-safe capsule/task packet under:

shards/S00/ipqc/S00-W00/worker_safe_tasks/astropy__astropy-12907/
```

The current supervisor context must not be used as the patch worker for that
instance. This note does not taint the materialized worker-safe packet itself;
it records operator-context contamination so the campaign can preserve its
gold-patch shortcut boundary.
