# External Auditor Prompt: Full SWE-bench Readiness Evidence

Audit this evidence root and the exact pushed SHA.

Expected current verdict:

```text
status: READY
full_swe_bench_ready: true
release_phase_g: true
next_loop: start_full_swe_bench_sharded_sealed_campaign
```

Questions:

1. Does the JSON show Phase F evaluator proof PASS with executable official
   replay and `release_next_phase_g: true`?
2. Does it recognize the Stage16R-real completed packet as PASS, with 7 fresh
   worker-derived repairs, strict MicroTape PASS, and zero remaining repair
   targets?
3. Does the Phase G manifest freeze exactly 500 SWE-bench Verified instance IDs
   with `selection_policy=ALL`, no exclusions, and dataset/harness SHA-256
   digests?
4. Does the auditor reject Mini 50 as insufficient for full-readiness and avoid
   treating readiness as full-score completion?
5. Does the packet forbid full-score, leaderboard-equivalence, P1/P2, and
   provider-billing-complete VPPUT claims before a sealed run completes?
6. Is the next loop correctly `start_full_swe_bench_sharded_sealed_campaign`,
   not a claim that SWE-bench has already been solved?
