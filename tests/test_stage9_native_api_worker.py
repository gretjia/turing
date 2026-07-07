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


def stage9_tasks():
    return [
        {
            "instance_id": "django__django-12039_stage9_accept",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": "Use proper whitespace in CREATE INDEX statements.",
            "stage9_expected_result": "PASS",
        },
        {
            "instance_id": "django__django-12039_stage9_fail",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": "Use proper whitespace in CREATE INDEX statements.",
            "stage9_expected_result": "FAIL",
        },
    ]


def generate_stage9_fixture(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    out_dir = tmp_path / "stage9"
    manifest = runner.generate_stage9_native_api_worker_fixture(out_dir, stage9_tasks())
    return out_dir, manifest


def test_stage9_native_api_worker_fixture_has_tool_receipts_and_strict_replay(tmp_path):
    auditor = load_module("tape_auditor", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    native = load_module("native_api", REPO / "tools" / "bench" / "audit_native_api_worker.py")
    out_dir, manifest = generate_stage9_fixture(tmp_path)

    bundles = [Path(item["micro_tape_bundle"]) for item in manifest["turingos_arm_runs"]]
    strict = auditor.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    native_report = native.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert strict["status_summary"]["vpput_accounting"] == "PASS"
    assert native_report["status"] == "PASS"
    assert set(native_report["required_tools"]) == {
        "read_file",
        "list_dir",
        "grep",
        "apply_patch",
        "write_file",
        "run_command",
    }
    assert native_report["accepted_run_tool_receipts_complete"] is True
    assert native_report["failed_run_has_failed_tool_receipt"] is True
    assert native_report["worker_receipts_assembled_from_tool_receipts"] is True
    assert native_report["tool_costs_counted"] is True


def test_stage9_native_api_audit_fails_when_expected_tool_receipt_missing(tmp_path):
    native = load_module("native_api", REPO / "tools" / "bench" / "audit_native_api_worker.py")
    out_dir, _ = generate_stage9_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["turingos_arm_runs"][0]["native_api_worker"]["expected_tools"].remove("grep")
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = native.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert "expected_tools must include all required native API tools" in report["problems"]


def test_stage9_native_api_requires_worker_receipt_assembled_flag():
    native = load_module("native_api", REPO / "tools" / "bench" / "audit_native_api_worker.py")
    tool_receipt_ids = {"mu:tool1", "mu:tool2"}

    assert native.worker_receipts_are_assembled([], tool_receipt_ids) is False
    assert (
        native.worker_receipts_are_assembled(
            [
                {
                    "tool_receipt_event_ids": ["mu:tool1"],
                    "assembled_from_tool_receipts": False,
                }
            ],
            tool_receipt_ids,
        )
        is False
    )
    assert (
        native.worker_receipts_are_assembled(
            [
                {
                    "tool_receipt_event_ids": ["mu:missing"],
                    "assembled_from_tool_receipts": True,
                }
            ],
            tool_receipt_ids,
        )
        is False
    )
    assert (
        native.worker_receipts_are_assembled(
            [
                {
                    "tool_receipt_event_ids": ["mu:tool1", "mu:tool2"],
                    "assembled_from_tool_receipts": True,
                }
            ],
            tool_receipt_ids,
        )
        is True
    )


def test_stage9_native_api_cli_writes_report(tmp_path):
    out_dir, _ = generate_stage9_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    output = out_dir / "native_api_worker_audit.json"

    subprocess.run(
        ["python3", "tools/bench/audit_native_api_worker.py", "--coverage", str(coverage), "--out", str(output)],
        cwd=REPO,
        check=True,
    )

    assert json.loads(output.read_text())["status"] == "PASS"
