# SWE-bench Verified 500 Readiness

Scope: readiness gate for the SWE-bench Verified 500 manifest.

This packet does not claim a completed full-score run. After external audit, it
also does not release an official SWE-bench campaign. The current evidence
supports an internal sealed rehearsal only.

- Phase F evaluator proof is PASS as TuringOS internal target-test replay.
- Phase F is BLOCKED as upstream SWE-bench official Docker harness proof.
- Stage16R-real repair evidence is PASS with 7/7 fresh worker-derived repairs.
- SWE-bench Verified full 500 manifest is frozen with `selection_policy=ALL`.
- Full-score, leaderboard-equivalence, official campaign, P1/P2, and
  provider-billing-complete VPPUT claims remain forbidden before upstream
  SWE-bench Docker harness evidence exists.

Current result:

```text
status: BLOCKED
phase_g_official_campaign_launch: false
phase_g_internal_rehearsal_launch: true
release_phase_g_as_official_campaign: false
release_phase_g_as_internal_rehearsal: true
next_loop: official_swebench_docker_harness_qualification
internal_rehearsal_next_loop: start_phase_g_internal_rehearsal_over_verified_500_manifest
blockers: [upstream_swebench_docker_harness_required]
```

Primary evidence:

- `evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628/`
- `evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628/`
- `evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/`
- `evidence/bench/swe_bench_full_readiness_20260628/official_swebench_docker_harness_qualification.md`

Verification command:

```bash
python3 tools/bench/audit_full_swe_bench_readiness.py \
  --phase-f-root evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628 \
  --repair-loop-root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \
  --stage16r-real-root evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628 \
  --full-manifest-root evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628 \
  --out evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json
```
