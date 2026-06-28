# Stage10 Independent Recursive Audit

Auditor: Darwin (`019f0c3a-1b5a-7ad2-be08-c379049e8152`)

Verdict: PASS

Scope: Stage10 Failure Taxonomy fixture/protocol evidence only.

## Findings

- PASS: all 10 expected failure classes are covered in `stage10_tasks.jsonl`, `taxonomy_manifest.json`, and replayed bundle payloads.
- PASS: all 10 bundles are failed paths: no `CandidateAccepted`, no `BroadcastRuleActivated`, each has a `FailureNode`, final `PPUTAccounted.progress = 0`, strict MicroTape audit `PASS`, and `authorization_head` `PASS`.
- PASS: each failed attempt has `FailureCertificate` with preserve-only `broadcast_rule_candidate`, `candidate_only: true`, `activation_event_id: null`, and a source reference to its `FailureNode`.
- PASS: direct candidate-field inspection found no raw log text, hidden predicates, secrets, or credential-shaped values.
- PASS: market/reward stay terminal failure basis: `MarketSettled.result = NO`, reward `0`, slash `1`, terminal event points to `FailureNode`; accepted head is not advanced by failure/market/reward tail events.
- PASS: Stage10 claim language is scoped and does not claim repair ability or solve-rate.

## Follow-up Applied

Darwin noted one non-blocking hardening gap: the first taxonomy auditor version trusted `raw_log_text_absent` and `hidden_predicates_absent` flags more than actual content.

This was fixed after the audit:

- `tools/bench/audit_failure_taxonomy.py` now recursively scans `broadcast_rule_candidate` strings for raw log, hidden predicate, PPUT/heldout, and credential-like markers.
- `tests/test_stage10_failure_taxonomy.py` includes a negative test for forbidden broadcast candidate content.
- The Stage10 taxonomy audit was regenerated and remains `PASS`.

## Evidence Inspected

- `tools/bench/run_mini_swe_bench_substrate_smoke.py`
- `tools/bench/audit_failure_taxonomy.py`
- `tests/test_stage10_failure_taxonomy.py`
- `evidence/bench/mini_swe_bench_stage10_failure_taxonomy_20260628/`
- all 10 `turingos/instances/stage10_*/micro_tape.bundle` artifacts
- `failure_taxonomy_audit.json`
- `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- `strict_audit_summary.md`
- `secret_scan_summary.txt`
- `stage10_tasks.jsonl`
- `taxonomy_manifest.json`
- `turingos/substrate_coverage.json`

## Merge Readiness

Merge-ready for Stage10 fixture scope only.

Stage10 proves taxonomy coverage and preserve-only broadcast-rule candidates for failed paths. It does not prove automated repair, loop-until-PASS behavior, or solve-rate.
