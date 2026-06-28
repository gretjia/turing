# Stage10 Failure Taxonomy Qualification

Scope: protocol fixture for SWE-bench failure taxonomy expansion.

This is not a solve-rate claim and not a statistical benchmark. It proves that classified failed attempts can be replayed from MicroTape and can emit preserve-only/private broadcast-rule candidates without activating sovereign broadcast rules.

## Evidence

- Input task list: `stage10_tasks.jsonl`
- Coverage: `turingos/substrate_coverage.json`
- Bundle manifest: `bundle_manifest.json`
- Taxonomy manifest: `taxonomy_manifest.json`
- Bundle digest list: `bundle_sha256s.txt`
- Strict MicroTape audit: `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- Decision DAG markdown: `micro_tape_audit_strict/micro_tape_decision_dag.md`
- Decision DAG DOT: `micro_tape_audit_strict/micro_tape_decision_dag.dot`
- Failure taxonomy audit: `failure_taxonomy_audit.json`
- Strict summary: `strict_audit_summary.md`
- Secret scan summary: `secret_scan_summary.txt`

## Classes Covered

```text
INSTALL_FAIL
TEST_TIMEOUT
WRONG_FILE
NO_REPRO
OVERBROAD_PATCH
SEMANTIC_FAIL
FLAKY_ORACLE
DEPENDENCY_GAP
CONTEXT_MISSING
PATCH_APPLIES_BUT_WRONG
```

## Reproduction

From repo root:

```bash
ROOT=evidence/bench/mini_swe_bench_stage10_failure_taxonomy_20260628

python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --failure-taxonomy-fixture \
  --authorization-mode required \
  --tasks-jsonl "$ROOT/stage10_tasks.jsonl" \
  --limit 10 \
  --out-dir "$ROOT"

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage "$ROOT/turingos/substrate_coverage.json" \
  --out-dir "$ROOT/micro_tape_audit_strict"

python3 tools/bench/audit_failure_taxonomy.py \
  --coverage "$ROOT/turingos/substrate_coverage.json" \
  --out "$ROOT/failure_taxonomy_audit.json"
```

## Status

Strict MicroTape audit reports `overall: PASS`.

Failure taxonomy audit reports:

```text
status: PASS
all_failures_have_failure_node: true
all_failures_have_broadcast_rule_candidate: true
broadcast_candidates_preserve_only: true
raw_logs_not_broadcast: true
```

No `BroadcastRuleActivated` event is used in this fixture; candidates remain preserve-only/private evidence until a future predicate-gated activation.

The taxonomy auditor also scans actual `broadcast_rule_candidate` strings for raw log, hidden predicate, PPUT/heldout, and credential-like markers instead of trusting only the candidate's boolean flags.
