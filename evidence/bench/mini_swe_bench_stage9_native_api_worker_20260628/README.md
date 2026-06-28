# Stage9 Native API Worker Tool Receipt Qualification

Scope: protocol fixture for Native API Worker tool-level receipts on SWE-bench-shaped tasks.

This is not a solve-rate claim and not a statistical benchmark. It proves that tool-level whitebox evidence can be written to MicroTape and replay-audited.

## Evidence

- Coverage: `turingos/substrate_coverage.json`
- Bundle manifest: `bundle_manifest.json`
- Worker manifest: `worker_manifest.json`
- Bundle digest list: `bundle_sha256s.txt`
- Strict MicroTape audit: `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- Decision DAG markdown: `micro_tape_audit_strict/micro_tape_decision_dag.md`
- Decision DAG DOT: `micro_tape_audit_strict/micro_tape_decision_dag.dot`
- Native API Worker audit: `native_api_worker_audit.json`
- Strict summary: `strict_audit_summary.md`
- Secret scan summary: `secret_scan_summary.txt`
- Independent recursive audit: `independent_recursive_audit.md`

## Bundles

```text
sha256:3afc40ea18d9ef050641cbffb8bed24f055d4eb2702140d03d5e5aff687f4ef1  evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/turingos/instances/django__django-12039/micro_tape.bundle
sha256:8c66d2b84e6008590616505dffa4f7698e7b60f484da40c716d8cb2cc0a314a0  evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/turingos/instances/django__django-12050/micro_tape.bundle
```

## Reproduction

From repo root:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --native-api-worker-fixture \
  --authorization-mode required \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --limit 2 \
  --out-dir evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/micro_tape_audit_strict

python3 tools/bench/audit_native_api_worker.py \
  --coverage evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/turingos/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/native_api_worker_audit.json
```

## Status

Strict MicroTape audit reports `overall: PASS`.

Native API Worker audit reports:

```text
status: PASS
accepted_run_tool_receipts_complete: true
failed_run_has_failed_tool_receipt: true
worker_receipts_assembled_from_tool_receipts: true
tool_costs_counted: true
```

The accepted fixture includes successful `ToolReceiptAppended` events for:

```text
read_file
list_dir
grep
apply_patch
write_file
run_command
```

The failed fixture includes an executed failed `apply_patch` receipt, terminal `FailureNode`, terminal market settlement, and final PPUT progress 0.
