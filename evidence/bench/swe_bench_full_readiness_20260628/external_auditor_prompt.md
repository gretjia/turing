# External Auditor Prompt: SWE-bench Verified 500 Readiness Evidence

Audit this evidence root and the exact pushed SHA.

Expected current verdict:

```text
status: BLOCKED
phase_g_official_campaign_launch: false
phase_g_internal_rehearsal_launch: true
release_phase_g_as_official_campaign: false
release_phase_g_as_internal_rehearsal: true
next_loop: official_swebench_docker_harness_qualification
```

Questions:

1. Does the JSON show Phase F as internal target-test replay PASS but upstream
   SWE-bench Docker harness proof BLOCKED?
2. Does it recognize the Stage16R-real completed packet as PASS, with 7 fresh
   worker-derived repairs, strict MicroTape PASS, and zero remaining repair
   targets?
3. Does the Phase G manifest freeze exactly 500 SWE-bench Verified instance IDs
   with `selection_policy=ALL`, no exclusions, and dataset/harness SHA-256
   digests?
4. Does the auditor reject Mini 50 as insufficient for full-readiness and avoid
   treating readiness as full-score completion?
5. Does the packet forbid official campaign launch, full-score,
   leaderboard-equivalence, P1/P2, and provider-billing-complete VPPUT claims
   until upstream SWE-bench Docker harness evidence exists?
6. Is the next official loop correctly `official_swebench_docker_harness_qualification`,
   with only `start_phase_g_internal_rehearsal_over_verified_500_manifest`
   allowed as an internal rehearsal?
