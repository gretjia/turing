# Stage12-A02 Independent Recursive Audit

Verdict: PASS.

Blocking findings: none.

Scope:
- `tools/bench/prepare_stage12_run_plan.py`
- `tests/test_stage12_run_plan.py`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/README.md`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/stage12_acceptance_commands.md`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/task_manifest.json`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/loop_manifest.json`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/tasks_20.jsonl`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/stage12_run_plan.json`
- `evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/stage12_a02_report.json`

Findings:
- A02 stays at contract/run-plan freeze. The planner validates the A01 contract, source SHA-256, and first-20 `instance_id` order before writing `tasks_20.jsonl` or `stage12_run_plan.json`.
- No worker run artifacts were found: no `micro_tape.bundle`, no `micro.git`, and no `substrate_coverage.json`.
- Tests cover happy path, digest mismatch, first-20 mismatch, invalid contract, and CLI report writing.
- Artifacts keep `authorization_mode` as `required`, keep fallback-to-auto authorization disabled, and set the runner-plan status to `READY_FOR_STAGE12_A03`.
- No overclaim was found. A02 does not claim Stage12 execution, solve-rate, statistical superiority, full score, or full external-worker provenance.
- No credential-shaped value or private-key material was found in the scoped artifacts.

Verification commands run by the independent auditor:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider \
  tests/test_stage12_contract.py tests/test_stage12_run_plan.py -q

PYTHONDONTWRITEBYTECODE=1 python3 tools/bench/validate_stage12_contract.py \
  --root evidence/bench/mini_swe_bench_stage12_20task_loop_20260628

find evidence/bench/mini_swe_bench_stage12_20task_loop_20260628 \
  \( -name 'micro_tape.bundle' -o -name 'micro.git' -o -name 'substrate_coverage.json' \) -print
```

Additional checks:
- Source SHA matched `task_manifest.json`.
- Source first 20 rows matched `task_manifest.json`.
- `tasks_20.jsonl` matched the source first 20 rows.
- `stage12_run_plan.json.tasks_jsonl_sha256` matched `tasks_20.jsonl`.
- Temporary regeneration of A02 outputs matched the committed artifacts.
- Secret-pattern scan returned no hits.
