# External Auditor Prompt — Stage13

Repository: https://github.com/gretjia/turing
Branch: goal/mini-swe-bench-grok-worker
Commit SHA: <EXACT_PUSHED_SHA>
Stage: Stage13 Native API Worker Receipts Hardening
Evidence root: evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628

Audit scope: verify Stage13 only. Do not convert this PASS into solve-rate, statistical superiority, full SWE-bench score, or FULL provenance for external CLI workers.

Required checks:
1. Download and verify bundle SHA-256 digests from `bundle_sha256s.txt`.
2. Run strict MicroTape audit with `--strict-vpput --strict-terminal-market --require-authorization-head` over `turingos/substrate_coverage.json`.
3. Run `audit_native_api_worker.py`, `audit_tool_receipt_conservation.py`, and `audit_prompt_leakage.py`.
4. Confirm every attempted `read_file`, `list_dir`, `grep`, `apply_patch`, `write_file`, and `run_command` action has a `ToolReceiptAppended` event.
5. Confirm failed grep, denied write, apply conflict, nonzero command, timeout, and forbidden path mutation are covered by tape receipts or denials.
6. Confirm `WorkerReceiptImported` references tool receipt IDs and does not rest on model self-report.
7. Confirm CostEvent/final PPUT token fields reconcile from tool receipt token fields.
8. Confirm actual visible prompt files and WorkCapsule payloads do not contain hidden predicates, raw logs, PPUT/VPPUT internals, heldout labels, official solution hints, gold patches, auth caches, API keys, signing material, or credentials.
9. Confirm Market/PPUT/projection events never move `accepted_head`.
10. Return `release_next_stage: YES` only if every strict field and every stage-specific audit is PASS and you can fetch/verify bundles.
