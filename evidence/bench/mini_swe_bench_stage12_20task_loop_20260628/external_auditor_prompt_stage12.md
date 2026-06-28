# External Auditor Prompt — Stage12 Exact-SHA Review

Audit the GitHub-visible Stage12 evidence at the exact pushed SHA containing this file. Do not audit local claims or summaries as truth; fetch the bundles from GitHub and rerun the commands below when possible.

Evidence root:
`evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/`

Required files:
- `task_manifest.json`
- `loop_manifest.json`
- `tasks_20.jsonl`
- `substrate_coverage.json`
- `bundle_sha256s.txt`
- `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- `stage12_release_audit.json`
- per-instance `instances/<instance>/micro_tape.bundle`

Claims allowed if and only if reproduced:
- Stage12 20-task scale/protocol evidence PASS.
- No statistical superiority claim.
- No full SWE-bench score claim.
- External CLI/Grok worker provenance remains PARTIAL.

Expected local report values:
- `stage12_release_audit.status == PASS`
- `run_count == 20`
- `solved_count == 13`
- `unsolved_count == 7`
- strict MicroTape `overall == PASS`
- `authorization_head == PASS`
- `vpput_accounting == PASS`
- `market_accounting_correctness == PASS`
- `constitutional_protocol_audit == PASS`

Verification commands from repo root:

```bash
python3 -m py_compile \
  tools/bench/audit_micro_tape_decision_dag.py \
  tools/bench/audit_stage12_release.py

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/substrate_coverage.json \
  --out-dir /tmp/turingos_stage12_external_strict_audit

python3 tools/bench/audit_stage12_release.py \
  --root evidence/bench/mini_swe_bench_stage12_20task_loop_20260628 \
  --coverage evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/substrate_coverage.json \
  --strict-audit /tmp/turingos_stage12_external_strict_audit/micro_tape_decision_dag_audit.json \
  --out /tmp/turingos_stage12_external_release_audit.json
```

Hard fail conditions:
- Any strict status is not PASS.
- Any bundle SHA in `bundle_sha256s.txt` does not match the GitHub blob/raw bytes.
- Fewer or more than 20 runs.
- `scientific_status` differs from `STAGE12_20TASK_SCALE_PROTOCOL_EVIDENCE_NOT_STATISTICAL_CLAIM`.
- Any run lacks `stage12_first_attempt`, `loop_until_pass`, authorization_head, or refreshed bundle digest.
- Any solved run lacks official PASS before CandidateAccepted or final PPUT progress=1 after accepted_head.
- Any unsolved run has CandidateAccepted or progress > 0.
- Any fixture marker/relabeling appears in bundle payloads.
- Any credential material appears in evidence.

Verdict format:
`PASS` only for Stage12 scale/protocol evidence. Use `PARTIAL` or `FAIL` for any missing executable reproduction or artifact mismatch.
