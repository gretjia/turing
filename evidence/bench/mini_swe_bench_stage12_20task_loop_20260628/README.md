# Stage12-A01 Contract Freeze

Scope: contract freeze only for Stage12 Real 20-task Loop-until-PASS Scale.

This evidence root does not contain Stage12 bundles. It freezes the 20-task manifest, budget profile, no-HITL policy, claim boundary, and acceptance commands before any Stage12 worker run.

## Source

- Source dataset: `/tmp/turingos-swebench-data/verified-mini-50.jsonl`
- Source dataset digest: `sha256:cafe0f03f7f6db133e98ad259f3a1cd0c6a59dce6965ddcb6e220df8b376ba5d`
- Selection policy: first 20 rows from the frozen source before any Stage12 run
- Base commit SHA: `38bae9971863db9196643084a926a7590c157cce`

The source dataset file itself is not copied into this A01 contract root. Stage12-A02 must either use a source file whose SHA-256 matches the digest above or add a GitHub-visible source mirror before any Stage12 run.

## Frozen Files

- `task_manifest.json`
- `loop_manifest.json`
- `stage12_acceptance_commands.md`
- `stage12_claim_boundary.md`
- `independent_recursive_audit.md`

## Claim Boundary

Stage12 is 20-task scale/protocol evidence only. It is not statistically powered, makes no product superiority claim, makes no full SWE-bench score claim, and does not upgrade external CLI worker provenance to FULL.

## Acceptance Commands

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

## Next Atom

Stage12-A02 may implement or configure the runner for this frozen manifest. It must not change the task list without producing a new Stage12-A01 contract and audit trail.
