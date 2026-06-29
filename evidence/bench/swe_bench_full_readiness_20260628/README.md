# SWE-bench Verified 500 Readiness

Scope: readiness gate for the SWE-bench Verified 500 manifest.

This packet does not claim a completed full-score run. After external audit, it
now releases the official upstream SWE-bench Docker-harness sharded campaign
launch gate. It does not claim the campaign has run, does not claim a full
score, and does not claim leaderboard equivalence.

- Phase F upstream SWE-bench Docker harness proof is PASS.
- The repaired Phase F 20-task replay resolved 20/20 with `python -m
  swebench.harness.run_evaluation`.
- Stage16R-real repair evidence is PASS with 7/7 fresh worker-derived repairs.
- SWE-bench Verified full 500 manifest is frozen with `selection_policy=ALL`.
- Full-score, leaderboard-equivalence, P1/P2, and provider-billing-complete
  VPPUT claims remain forbidden until the sharded campaign actually completes
  and final gates pass.

Current result:

```text
status: READY
phase_g_official_campaign_launch: true
phase_g_internal_rehearsal_launch: true
release_phase_g_as_official_campaign: true
release_phase_g_as_internal_rehearsal: true
next_loop: start_official_swebench_verified_500_sharded_sealed_campaign
internal_rehearsal_next_loop: start_phase_g_internal_rehearsal_over_verified_500_manifest
blockers: []
```

Primary evidence:

- `evidence/bench/swe_bench_official_harness_qualification_20260629/`
- `evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628/`
- `evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/`
- `evidence/bench/swe_bench_full_readiness_20260628/official_swebench_docker_harness_qualification.md`

Verification command:

```bash
python3 tools/bench/audit_full_swe_bench_readiness.py \
  --phase-f-root evidence/bench/swe_bench_official_harness_qualification_20260629 \
  --repair-loop-root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \
  --stage16r-real-root evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628 \
  --full-manifest-root evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628 \
  --out evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json
```
