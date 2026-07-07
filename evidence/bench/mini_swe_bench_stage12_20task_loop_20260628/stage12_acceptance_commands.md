# Stage12 Release Acceptance Commands

Run these commands from the repository root to reproduce the Stage12 local release gate. These commands audit the post-run evidence packet; the earlier A01/A02 pre-run contract checks remain in git history and in the frozen contract files.

```bash
python3 -m py_compile \
  tools/bench/prepare_stage12_run_plan.py \
  tools/bench/validate_stage12_contract.py \
  tools/bench/audit_stage12_release.py \
  tools/bench/audit_micro_tape_decision_dag.py \
  tools/bench/run_mini_swe_bench_substrate_smoke.py \
  tools/bench/evaluate_django_swe_bench_patches.py

pytest \
  tests/test_stage12_contract.py \
  tests/test_stage12_run_plan.py \
  tests/test_stage12_release_audit.py \
  tests/test_stage12_test_local_authority.py \
  tests/test_mini_swe_bench_grok_headless.py::test_evaluator_refreshes_micro_tape_bundle_after_terminal_import \
  tests/test_mini_swe_bench_grok_headless.py::test_stage12_loop_metadata_records_failed_attempt_before_terminal_accept \
  tests/test_mini_swe_bench_grok_headless.py::test_stage12_loop_metadata_records_budget_exhausted_without_accept \
  -q

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

python3 - <<'PY'
import json
from pathlib import Path
root = Path("evidence/bench/mini_swe_bench_stage12_20task_loop_20260628")
strict = json.loads((root / "micro_tape_audit_strict/micro_tape_decision_dag_audit.json").read_text())
release = json.loads((root / "stage12_release_audit.json").read_text())
assert release["status"] == "PASS"
assert release["run_count"] == 20
assert release["solved_count"] == 13
assert release["unsolved_count"] == 7
assert release["problems"] == []
summary = strict["status_summary"]
for key in [
    "overall",
    "replay_structural_integrity",
    "git_topology",
    "registry_head_effect",
    "accepted_head_authority",
    "authorization_head",
    "cost_conservation_all_branches",
    "vpput_accounting",
    "economic_timing",
    "market_accounting_correctness",
    "constitutional_protocol_audit",
]:
    assert summary[key] == "PASS", (key, summary[key])
print("STAGE12_RELEASE_PACKET_PASS")
PY

git diff --check
```

Expected release audit result: `PASS`, `run_count=20`, `solved_count=13`, `unsolved_count=7`, `problems=[]`.
