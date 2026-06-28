# External Auditor Prompt: Full SWE-bench Readiness Evidence

Audit this evidence root and the exact pushed SHA.

Expected current verdict:

```text
status: BLOCKED
full_swe_bench_ready: false
release_phase_g: false
next_loop: retry_remaining_stage16r_real_targets
```

Questions:

1. Does the JSON block full SWE-bench launch because Phase F is still PARTIAL?
2. Does it recognize the Stage16R-real evaluator loop as PARTIAL, with 2/7
   official PASS and 5 remaining repair targets?
3. Does it require full dataset manifest freeze before readiness?
4. Does it avoid full-score, full-dataset, and leaderboard-equivalence claims?
5. Is this packet safe to publish as a readiness blocker, not a release packet?
