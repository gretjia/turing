# Full SWE-bench Readiness

Scope: launch-readiness gate for starting a sealed SWE-bench Verified 500
campaign.

This packet does not claim a completed full-score run. It only proves the launch
prerequisites for the next sealed campaign are satisfied:

- Phase F evaluator proof is PASS with executable official evaluator replay.
- Stage16R-real repair evidence is PASS with 7/7 fresh worker-derived repairs.
- SWE-bench Verified full 500 manifest is frozen with `selection_policy=ALL`.
- Full-score, leaderboard-equivalence, P1/P2, and provider-billing-complete
  VPPUT claims remain forbidden before the sealed campaign completes.

Current result:

```text
status: READY
full_swe_bench_ready: true
release_phase_g: true
next_loop: start_full_swe_bench_sharded_sealed_campaign
```

Primary evidence:

- `evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628/`
- `evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628/`
- `evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/`

Verification command:

```bash
python3 tools/bench/audit_full_swe_bench_readiness.py \
  --phase-f-root evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628 \
  --repair-loop-root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \
  --stage16r-real-root evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628 \
  --full-manifest-root evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628 \
  --out evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json
```
