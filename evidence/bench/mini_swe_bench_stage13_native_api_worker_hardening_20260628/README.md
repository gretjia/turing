# Stage13 Native API Worker Receipts Hardening

Scope: Stage13 receipt-hardening/protocol evidence for the Native API Worker path.

This is not a solve-rate claim, not a statistical benchmark, and not a full SWE-bench score claim. It proves that deterministic Native API Worker actions can be represented as MicroTape `ToolActionAuthorized` / `ToolReceiptAppended` events, that `WorkerReceiptImported` is assembled from tool receipt IDs, that failed/denied/timeout tool actions remain on tape, and that final cost/PPUT can be reconciled from tool receipts.

## Evidence

- Coverage: `turingos/substrate_coverage.json`
- Bundle manifest: `bundle_manifest.json`
- Bundle digest list: `bundle_sha256s.txt`
- Strict MicroTape audit: `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- Decision DAG markdown: `micro_tape_audit_strict/micro_tape_decision_dag.md`
- Decision DAG DOT: `micro_tape_audit_strict/micro_tape_decision_dag.dot`
- Native API Worker audit: `native_api_worker_audit.json`
- Tool receipt conservation audit: `tool_receipt_conservation_audit.json`
- Prompt leakage audit: `prompt_leakage_audit.json`
- Tool call lineage: `tool_call_lineage.md`
- Strict summary: `strict_audit_summary.md`
- Secret scan summary: `secret_scan_summary.txt`
- External auditor prompt: `external_auditor_prompt_stage13.md`

## Bundles

```text
sha256:0044db5afb946f22eaa5b8c713152aaac16ecf80fc15b6bb6fc38e2ca5e02b47  evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/instances/django__django-12039/micro_tape.bundle
sha256:9f64731b45c18a5bb04f983d7484fbdfe91c7fb34abdb3283b853adb011d7ce5  evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/instances/django__django-12050/micro_tape.bundle
```

## Status

```text
strict overall: PASS
authorization_head: PASS
accepted_head_authority: PASS
vpput_accounting: PASS
market_accounting_correctness: PASS
constitutional_protocol_audit: PASS
native_api_worker_audit: PASS
tool_receipt_conservation_audit: PASS
prompt_leakage_audit: PASS
```

## Reproduction

From repo root:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --native-api-worker-hardening \
  --authorization-mode required \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --limit 2 \
  --out-dir evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/micro_tape_audit_strict

python3 tools/bench/audit_native_api_worker.py \
  --coverage evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/native_api_worker_audit.json

python3 tools/bench/audit_tool_receipt_conservation.py \
  --coverage evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/tool_receipt_conservation_audit.json

python3 tools/bench/audit_prompt_leakage.py \
  --coverage evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/prompt_leakage_audit.json
```

## Claim Boundary

Stage13 may claim Native API Worker receipt hardening for these fresh bundles only. It may not claim solve-rate, statistical superiority, full SWE-bench score, or FULL provenance for external CLI workers.
