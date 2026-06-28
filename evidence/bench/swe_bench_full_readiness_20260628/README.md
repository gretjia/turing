# Full SWE-bench Readiness

Scope: launch-readiness gate for starting a full SWE-bench sealed campaign.

This packet is intentionally a blocker packet. It does not claim that full
SWE-bench is ready. It records the exact remaining gates that must pass before a
full campaign may start.

Current result:

```text
status: BLOCKED
full_swe_bench_ready: false
release_phase_g: false
next_loop: stage16r_real_evaluator_bundle_loop
```

Primary blockers:

- fresh Stage16R-real evaluator bundles are still required;
- Phase F evaluator proof is still PARTIAL;
- full dataset manifest freeze has not happened.

Verification command:

```bash
python3 tools/bench/audit_full_swe_bench_readiness.py \
  --phase-f-root evidence/bench/swe_bench_phase_f_evaluator_proof_20260628 \
  --repair-loop-root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \
  --full-manifest-root evidence/bench/swe_bench_full_manifest_20260628 \
  --out evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json
```
