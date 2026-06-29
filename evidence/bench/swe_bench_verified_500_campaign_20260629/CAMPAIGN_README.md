# SWE-bench Verified 500 Campaign Controller

This directory freezes the internal official-harness campaign control plane.
It does not run the 500 tasks and does not claim official leaderboard
equivalence. Upstream SWE-bench Docker harness identity must pass before any
official campaign launch.

Execution policy:
- one-shot 500 run: FORBIDDEN
- execution atom: one instance
- process QC: 10-task IPQC window
- audit atom: 50-task sealed shard
- full campaign: 10 shards x 50 tasks
