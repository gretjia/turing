# Stage12-A01/A02 Contract And Runner-Plan Freeze

Scope: contract and runner-plan freeze only for Stage12 Real 20-task Loop-until-PASS Scale.

This evidence root does not contain Stage12 bundles. It freezes the 20-task manifest, budget profile, no-HITL policy, claim boundary, acceptance commands, exact `tasks_20.jsonl`, and Stage12-A03 command templates before any Stage12 worker run.

Stage12-A03 now has an explicit release auditor and a test-scope authority bridge. The bridge is selected only by `--authority-provider test-local` together with `--authorization-mode required`; it directly appends benchmark-scope AUTHORIZATION events to MicroTape and does not loosen production `turingd` approval RPCs, which still require OsKeyring.

`audit_stage12_release.py` is the local Stage12 release gate. It recomputes strict MicroTape audit from the same coverage bundle paths, compares supplied strict-audit bundle hashes against the recomputed hashes, rejects relabeled fixture payload markers inside the bundle itself, and rejects any fewer-than-20, manual-intervention, or non-PASS strict evidence.

## Source

- Source dataset: `/tmp/turingos-swebench-data/verified-mini-50.jsonl`
- Source dataset digest: `sha256:cafe0f03f7f6db133e98ad259f3a1cd0c6a59dce6965ddcb6e220df8b376ba5d`
- Selection policy: first 20 rows from the frozen source before any Stage12 run
- Base commit SHA: `38bae9971863db9196643084a926a7590c157cce`

Stage12-A02 read a local source file whose SHA-256 matches the digest above and wrote `tasks_20.jsonl` with exactly the first 20 frozen rows. The source dataset file itself is not copied into this evidence root.

## Frozen Files

- `task_manifest.json`
- `loop_manifest.json`
- `tasks_20.jsonl`
- `stage12_run_plan.json`
- `stage12_a02_report.json`
- `stage12_acceptance_commands.md`
- `stage12_claim_boundary.md`
- `independent_recursive_audit.md`
- `independent_recursive_audit_stage12_a02.md`

## Claim Boundary

Stage12 is 20-task scale/protocol evidence only. It is not statistically powered, makes no product superiority claim, makes no full SWE-bench score claim, and does not upgrade external CLI worker provenance to FULL.

## Acceptance Commands

```bash
python3 -m py_compile tools/bench/validate_stage12_contract.py
python3 -m py_compile \
  tools/bench/prepare_stage12_run_plan.py \
  tools/bench/validate_stage12_contract.py \
  tools/bench/audit_stage12_release.py

pytest \
  tests/test_stage12_contract.py \
  tests/test_stage12_run_plan.py \
  tests/test_stage12_release_audit.py \
  tests/test_stage12_test_local_authority.py \
  -q

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
assert "--authority-provider" in plan["stage12_a03_command_template"]
assert "test-local" in plan["stage12_a03_command_template"]
assert plan["authority_provider"] == "test-local"
assert plan["fallback_to_auto_authorization"] is False
assert len(tasks) == 20
assert [row["instance_id"] for row in tasks] == plan["instance_ids"]
for forbidden in ("micro_tape.bundle", "micro.git", "substrate_coverage.json"):
    assert not list(root.rglob(forbidden)), forbidden
print("STAGE12_A02_RUN_PLAN_FROZEN")
PY

git diff --check
```

## Next Atom

Stage12-A03 may run the Stage12 worker path from `stage12_run_plan.json`. It must not change the task list without producing a new Stage12-A01 contract and audit trail. Stage12 release requires `audit_stage12_release.py` PASS after strict MicroTape audit PASS; fixture, partial, or fewer-than-20 output cannot release Stage13.
