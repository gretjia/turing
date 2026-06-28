import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


write_contract = load_module("stage12_contract_helpers", REPO / "tests" / "test_stage12_contract.py").write_contract


def write_source(path: Path, instance_ids: list[str]) -> str:
    rows = []
    for index, instance_id in enumerate(instance_ids):
        rows.append(
            {
                "instance_id": instance_id,
                "repo": "django/django",
                "base_commit": f"commit-{index}",
                "problem_statement": f"problem {instance_id}",
                "test_patch": f"diff --git a/tests/{index}.py b/tests/{index}.py\n",
            }
        )
    text = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    path.write_text(text)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_stage12_contract(root: Path, source: Path, instance_ids: list[str]):
    digest = write_source(source, instance_ids)
    write_contract(root)
    task_path = root / "task_manifest.json"
    task = json.loads(task_path.read_text())
    task["source_dataset_reference"] = str(source)
    task["source_dataset_digest"] = digest
    task["instance_ids"] = instance_ids[:20]
    task["task_order"] = instance_ids[:20]
    task["excluded_instances"] = instance_ids[20:]
    task["task_count"] = 20
    task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n")


def test_stage12_run_plan_writes_tasks_and_runner_plan(tmp_path):
    planner = load_module("planner", REPO / "tools" / "bench" / "prepare_stage12_run_plan.py")
    ids = [f"django__django-{12000 + i}" for i in range(25)]
    source = tmp_path / "verified-mini-50.jsonl"
    root = tmp_path / "stage12"
    make_stage12_contract(root, source, ids)

    report = planner.prepare_run_plan(root)

    assert report["status"] == "PASS"
    assert report["task_count"] == 20
    tasks_path = root / "tasks_20.jsonl"
    plan_path = root / "stage12_run_plan.json"
    assert tasks_path.exists()
    assert plan_path.exists()
    rows = [json.loads(line) for line in tasks_path.read_text().splitlines()]
    assert [row["instance_id"] for row in rows] == ids[:20]
    plan = json.loads(plan_path.read_text())
    assert plan["status"] == "READY_FOR_STAGE12_A03"
    assert plan["a02_does_not_run_workers"] is True
    assert plan["expected_bundle_count_after_a03"] == 20
    assert plan["stage12_a03_requires_runner_atom"] is True
    command = plan["stage12_a03_command_template"]
    assert "--loop-until-pass" not in command
    assert "--loop-until-pass-fixture" not in command
    assert "--tasks-jsonl" in command
    assert "--authorization-mode" in command
    assert "required" in command
    assert "--authority-provider" in command
    assert "test-local" in command
    assert not list(root.rglob("micro_tape.bundle"))


def test_stage12_run_plan_rejects_source_digest_mismatch(tmp_path):
    planner = load_module("planner", REPO / "tools" / "bench" / "prepare_stage12_run_plan.py")
    ids = [f"django__django-{12000 + i}" for i in range(20)]
    source = tmp_path / "source.jsonl"
    root = tmp_path / "stage12"
    make_stage12_contract(root, source, ids)
    task_path = root / "task_manifest.json"
    task = json.loads(task_path.read_text())
    task["source_dataset_digest"] = "sha256:" + "0" * 64
    task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n")

    report = planner.prepare_run_plan(root)

    assert report["status"] == "FAIL"
    assert any("source dataset digest mismatch" in problem for problem in report["problems"])


def test_stage12_run_plan_rejects_first20_order_mismatch(tmp_path):
    planner = load_module("planner", REPO / "tools" / "bench" / "prepare_stage12_run_plan.py")
    ids = [f"django__django-{12000 + i}" for i in range(20)]
    source = tmp_path / "source.jsonl"
    root = tmp_path / "stage12"
    make_stage12_contract(root, source, list(reversed(ids)))
    task_path = root / "task_manifest.json"
    task = json.loads(task_path.read_text())
    task["instance_ids"] = ids
    task["task_order"] = ids
    task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n")

    report = planner.prepare_run_plan(root)

    assert report["status"] == "FAIL"
    assert any("source first 20 instance_ids do not match task_manifest" in problem for problem in report["problems"])


def test_stage12_run_plan_rejects_invalid_contract(tmp_path):
    planner = load_module("planner", REPO / "tools" / "bench" / "prepare_stage12_run_plan.py")
    ids = [f"django__django-{12000 + i}" for i in range(20)]
    source = tmp_path / "source.jsonl"
    root = tmp_path / "stage12"
    make_stage12_contract(root, source, ids)
    loop_path = root / "loop_manifest.json"
    loop = json.loads(loop_path.read_text())
    loop["authorization_mode"] = "auto"
    loop_path.write_text(json.dumps(loop, indent=2, sort_keys=True) + "\n")

    report = planner.prepare_run_plan(root)

    assert report["status"] == "FAIL"
    assert any("contract validation failed" in problem for problem in report["problems"])


def test_stage12_run_plan_cli_writes_report(tmp_path):
    ids = [f"django__django-{12000 + i}" for i in range(20)]
    source = tmp_path / "source.jsonl"
    root = tmp_path / "stage12"
    make_stage12_contract(root, source, ids)

    subprocess.run(
        ["python3", "tools/bench/prepare_stage12_run_plan.py", "--root", str(root)],
        cwd=REPO,
        check=True,
    )

    report = json.loads((root / "stage12_a02_report.json").read_text())
    assert report["status"] == "PASS"
    assert (root / "tasks_20.jsonl").exists()
