# Stage14 Corpus-Level Failure Memory

Scope: Stage14 corpus failure-memory/protocol evidence.

This is not a solve-rate claim, not a statistical benchmark, and not a full SWE-bench score claim. It proves that repeated `CONTEXT_MISSING` failures can be reduced from fresh MicroTape bundles into an activated broadcast rule, and that a later capsule can consume that rule without exposing raw logs, hidden predicates, PPUT/VPPUT internals, heldout labels, official solution hints, or credentials.

## Evidence

- Coverage: `turingos/substrate_coverage.json`
- Bundle manifest: `bundle_manifest.json`
- Bundle digest list: `bundle_sha256s.txt`
- Strict MicroTape audit: `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- Decision DAG markdown: `micro_tape_audit_strict/micro_tape_decision_dag.md`
- Decision DAG DOT: `micro_tape_audit_strict/micro_tape_decision_dag.dot`
- Corpus failure-memory audit: `corpus_failure_memory_audit.json`
- Failure cluster audit: `failure_cluster_audit.json`
- Broadcast rule visibility audit: `broadcast_rule_visibility_audit.json`
- Broadcast rule efficacy audit: `broadcast_rule_efficacy_audit.json`
- Cross-task lineage: `cross_task_memory_lineage.md`
- Strict summary: `strict_audit_summary.md`
- Secret scan summary: `secret_scan_summary.txt`
- External auditor prompt: `external_auditor_prompt_stage14.md`

## Bundles

```text
sha256:55a93b5595dae00c1c01aef7fbc4f2713174bd22cdfbf855f1e587098f4766e3  evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/turingos/instances/django__django-11790/micro_tape.bundle
sha256:cfd69abe09f7979dc54d0d3ba69f2feeb6e85820ada08f3e7a4cf3fbfb9349d1  evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/turingos/instances/django__django-11815/micro_tape.bundle
sha256:00433a2295664df378f0a78a5d898d3dc92771f6f2b3a9cc060ad4120a74e85c  evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/turingos/instances/django__django-11848/micro_tape.bundle
sha256:fa5ab7741561495bcf131fe9d1cb1006187afb1b9a160eae8475bdfeb6472f78  evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/turingos/instances/django__django-11880/micro_tape.bundle
```

## Status

```text
strict overall: PASS
authorization_head: PASS
accepted_head_authority: PASS
vpput_accounting: PASS
market_accounting_correctness: PASS
constitutional_protocol_audit: PASS
corpus_failure_memory_audit: PASS
failure_cluster_audit: PASS
broadcast_rule_visibility_audit: PASS
broadcast_rule_efficacy_audit: PASS
```

## Reproduction

From repo root:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --corpus-failure-memory \
  --authorization-mode required \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/tasks_20.jsonl \
  --limit 4 \
  --out-dir evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/micro_tape_audit_strict

python3 tools/bench/audit_corpus_failure_memory.py \
  --coverage evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/turingos/substrate_coverage.json \
  --out-dir evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628
```

## Claim Boundary

Stage14 may claim corpus-level failure memory fixture qualification only. Its efficacy report is explicitly bounded: it records observed association in a fixture sample and does not claim causality.

