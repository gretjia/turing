# External Auditor Prompt: SWE-bench Verified 500 Readiness Evidence

Audit this evidence root and the exact pushed SHA.

Expected current verdict:

```text
status: READY
phase_g_official_campaign_launch: true
phase_g_internal_rehearsal_launch: true
release_phase_g_as_official_campaign: true
release_phase_g_as_internal_rehearsal: true
next_loop: start_official_swebench_verified_500_sharded_sealed_campaign
```

Questions:

1. Does the JSON show Phase F upstream SWE-bench Docker harness proof PASS?
2. Does it recognize the Stage16R-real completed packet as PASS, with 7 fresh
   worker-derived repairs, strict MicroTape PASS, and zero remaining repair
   targets?
3. Does the Phase G manifest freeze exactly 500 SWE-bench Verified instance IDs
   with `selection_policy=ALL`, no exclusions, and dataset/harness SHA-256
   digests?
4. Does the auditor reject Mini 50 as insufficient for full-readiness and avoid
   treating readiness as full-score completion?
5. Does the packet allow official campaign launch while still forbidding
   full-score, leaderboard-equivalence, P1/P2, and provider-billing-complete
   VPPUT claims until final campaign gates pass?
6. Is the next official loop correctly
   `start_official_swebench_verified_500_sharded_sealed_campaign`?
7. Does `evidence/bench/swe_bench_official_harness_qualification_20260629/`
   show the repaired Phase F 20-task upstream Docker replay resolved 20/20?
