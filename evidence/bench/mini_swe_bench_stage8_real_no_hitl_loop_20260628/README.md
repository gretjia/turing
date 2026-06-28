# Stage8 Real No-HITL Loop MicroTape Qualification

Scope: protocol qualification fixture for a SWE-bench-shaped task. This is not a solve-rate claim and not a statistical benchmark.

This run proves, from a fresh MicroTape bundle, the causal shape requested by the Stage8 auditor:

1. attempt 1 receives authorization, builds a capsule, imports worker and macro evidence, imports official evaluator FAIL, and appends `FailureNode`;
2. the failure is compressed into `FailureCertificate` and `BroadcastRuleActivated`;
3. retry is authorized without human intervention;
4. attempt 2 builds a later capsule that consumes the broadcast rule;
5. official evaluator PASS precedes terminal `CandidateAccepted`;
6. terminal `MarketSettled`, `RewardDistributed`, and final `PPUTAccounted(progress=1)` happen after accept;
7. strict replay audit reconstructs `tape_tip`, `authorization_head`, and `accepted_head` from the bundle.

## Evidence

- Coverage: `turingos/substrate_coverage.json`
- Bundle manifest: `bundle_manifest.json`
- Bundle digest list: `bundle_sha256s.txt`
- MicroTape bundle: `turingos/instances/django__django-12039/micro_tape.bundle`
- Strict MicroTape audit: `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- Decision DAG markdown: `micro_tape_audit_strict/micro_tape_decision_dag.md`
- Decision DAG DOT: `micro_tape_audit_strict/micro_tape_decision_dag.dot`
- no-HITL audit: `no_hitl_loop_audit.json`
- Failure memory audit: `failure_memory_audit.json`
- Strict summary: `strict_audit_summary.md`
- Secret scan summary: `secret_scan_summary.txt`
- Independent recursive audit: `independent_recursive_audit.md`

## Bundle

```text
sha256:df0ccc6df48c3ac87dac7d66f51ce029432828245df0077b8d84b798bd723155  evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/turingos/instances/django__django-12039/micro_tape.bundle
```

## Reproduction

From repo root:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --no-hitl-loop-fixture \
  --authorization-mode required \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --limit 1 \
  --out-dir evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/micro_tape_audit_strict

python3 tools/bench/audit_no_hitl_loop.py \
  --coverage evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/turingos/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/no_hitl_loop_audit.json

python3 tools/bench/audit_failure_memory.py \
  --coverage evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/turingos/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/failure_memory_audit.json
```

## Status

The strict MicroTape audit reports `overall: PASS`.

This evidence does not claim SWE-bench solve-rate, full Single Loop autonomy, or real Grok repair capability. It closes the protocol fixture gap: no-HITL retry causality, failure-memory injection, authorization-head coverage, terminal market, and final VPPUT accounting are replayable from MicroTape.
