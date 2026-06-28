# Phase G Full SWE-bench Verified 500 Acceptance Commands

```bash
python3 tools/bench/audit_full_swe_bench_readiness.py \
  --phase-f-root evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628 \
  --repair-loop-root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \
  --stage16r-real-root evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628 \
  --full-manifest-root evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628 \
  --out evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json

python3 tools/bench/audit_micro_tape_decision_dag.py --strict-vpput --strict-terminal-market --require-authorization-head <per-shard bundle args>
```

Readiness starts the sealed campaign only; full-score remains forbidden until all 500 tasks have official PASS, CandidateAccepted, final PPUT progress=1, and exact-SHA external audit release.
