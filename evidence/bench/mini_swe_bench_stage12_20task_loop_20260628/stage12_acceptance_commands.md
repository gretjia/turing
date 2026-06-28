# Stage12-A01 Acceptance Commands

Run these commands from the repository root.

```bash
python3 -m py_compile tools/bench/validate_stage12_contract.py

pytest tests/test_stage12_contract.py -q

python3 tools/bench/validate_stage12_contract.py \
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

git diff --check
```
