# External Auditor Prompt: Full SWE-bench Readiness Evidence

Audit this evidence root and the exact pushed SHA.

Expected current verdict:

```text
status: BLOCKED
full_swe_bench_ready: false
release_phase_g: false
next_loop: stage16r_real_evaluator_bundle_loop
```

Questions:

1. Does the JSON block full SWE-bench launch because Phase F is still PARTIAL?
2. Does it block because fresh Stage16R-real evaluator bundles are missing?
3. Does it require full dataset manifest freeze before readiness?
4. Does it avoid full-score, full-dataset, and leaderboard-equivalence claims?
5. Is this packet safe to publish as a readiness blocker, not a release packet?
