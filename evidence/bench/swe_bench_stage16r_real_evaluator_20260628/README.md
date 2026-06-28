# Stage16R Real Evaluator Loop

Scope: fresh real-worker/evaluator attempt for the seven Stage16R repair targets.

This packet supersedes none of the old Stage16R bundles and does not release
Phase F or Phase G. It records a real Grok worker run, official Django target-test
evaluation, MicroTape evidence import, and strict MicroTape replay audit for the
seven repair targets.

Current result:

```text
status: PARTIAL
repair_target_count: 7
fresh_real_evaluator_bundle_count: 7
official_pass_count: 2
remaining_repair_count: 5
strict_microtape_status: PASS
phase_f_evaluator_proof_ready: false
release_phase_f: false
release_phase_g: false
```

Passing targets:

- `django__django-11815`
- `django__django-12325`

Remaining targets:

- `django__django-11790`
- `django__django-11964`
- `django__django-12209`
- `django__django-12273`
- `django__django-12308`

Important scope boundary:

- This is not a full SWE-bench dataset.
- This is not a full-score claim.
- This is not Phase F PASS.
- This is not Phase G release.
- Old Stage16R MicroTape remains immutable.
- Dataset gold patches were not used as worker candidate sources.

Reproduction commands:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --tasks-jsonl /tmp/turingos_tasks_7.jsonl \
  --out-dir evidence/bench/swe_bench_stage16r_real_evaluator_20260628/turingos \
  --limit 7 \
  --worker-mode grok \
  --model grok-build \
  --max-turns 24 \
  --worker-timeout-s 1500 \
  --authorization-mode required \
  --authority-provider test-local \
  --stage12-real-loop \
  --broadcast-rules-file /tmp/turingos_stage16r_seed_rules.json

python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl /tmp/turingos_tasks_7.jsonl \
  --limit 7 \
  --turingos-dir evidence/bench/swe_bench_stage16r_real_evaluator_20260628/turingos \
  --direct-dir evidence/bench/swe_bench_stage16r_real_evaluator_20260628/direct \
  --out evidence/bench/swe_bench_stage16r_real_evaluator_20260628/patch_eval \
  --substrate-coverage evidence/bench/swe_bench_stage16r_real_evaluator_20260628/turingos/substrate_coverage.json \
  --import-turingos-evidence \
  --stage12-loop-until-pass

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/swe_bench_stage16r_real_evaluator_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/swe_bench_stage16r_real_evaluator_20260628/micro_tape_audit_strict
```

The `/tmp/turingos_tasks_7.jsonl` input contains upstream SWE-bench task records
and is intentionally not published in this evidence root because those records
include dataset gold patch fields. Worker-visible prompts did not include those
gold patch fields.
