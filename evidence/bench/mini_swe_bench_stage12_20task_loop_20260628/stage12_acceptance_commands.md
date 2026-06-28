# Stage12-A01/A02 Acceptance Commands

Run these commands from the repository root.

```bash
python3 -m py_compile tools/bench/validate_stage12_contract.py
python3 -m py_compile tools/bench/prepare_stage12_run_plan.py tools/bench/validate_stage12_contract.py

pytest tests/test_stage12_contract.py tests/test_stage12_run_plan.py -q

python3 tools/bench/validate_stage12_contract.py \
  --root evidence/bench/mini_swe_bench_stage12_20task_loop_20260628

python3 tools/bench/prepare_stage12_run_plan.py \
  --root evidence/bench/mini_swe_bench_stage12_20task_loop_20260628

python3 - <<'PY'
import json
from pathlib import Path
root = Path("evidence/bench/mini_swe_bench_stage12_20task_loop_20260628")
task = json.loads((root / "task_manifest.json").read_text())
loop = json.loads((root / "loop_manifest.json").read_text())
assert task["task_count"] == 20
assert len(task["instance_ids"]) == 20
assert len(set(task["instance_ids"])) == 20
assert task["frozen_before_run"] is True
assert loop["authorization_mode"] == "required"
assert loop["stage_release_policy"]["dry_run_can_release"] is False
assert loop["stage_release_policy"]["static_only_external_review_can_release"] is False
print("STAGE12_A01_CONTRACT_FROZEN")
PY

python3 - <<'PY'
import json
from pathlib import Path
root = Path("evidence/bench/mini_swe_bench_stage12_20task_loop_20260628")
report = json.loads((root / "stage12_a02_report.json").read_text())
plan = json.loads((root / "stage12_run_plan.json").read_text())
tasks = [json.loads(line) for line in (root / "tasks_20.jsonl").read_text().splitlines()]
assert report["status"] == "PASS"
assert plan["status"] == "READY_FOR_STAGE12_A03"
assert plan["a02_does_not_run_workers"] is True
assert plan["expected_bundle_count_after_a03"] == 20
assert plan["stage12_a03_requires_runner_atom"] is True
assert "--loop-until-pass" not in plan["stage12_a03_command_template"]
assert "--loop-until-pass-fixture" not in plan["stage12_a03_command_template"]
assert len(tasks) == 20
assert [row["instance_id"] for row in tasks] == plan["instance_ids"]
for forbidden in ("micro_tape.bundle", "micro.git", "substrate_coverage.json"):
    assert not list(root.rglob(forbidden)), forbidden
print("STAGE12_A02_RUN_PLAN_FROZEN")
PY

git diff --check
```
