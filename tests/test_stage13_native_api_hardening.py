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


def stage13_tasks():
    return [
        {
            "instance_id": "django__django-12039_stage13_accept",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": "Use proper whitespace in CREATE INDEX statements.",
            "stage13_expected_result": "PASS",
        },
        {
            "instance_id": "django__django-12050_stage13_fail",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": "Exercise failed native API tool-call receipts.",
            "stage13_expected_result": "FAIL",
        },
    ]


def generate_stage13_fixture(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    out_dir = tmp_path / "stage13"
    manifest = runner.generate_stage13_native_api_worker_hardening_fixture(out_dir, stage13_tasks())
    return out_dir, manifest


def test_stage13_fixture_strict_replay_and_receipt_hardening(tmp_path):
    tape = load_module("tape_auditor", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    native = load_module("native_api", REPO / "tools" / "bench" / "audit_native_api_worker.py")
    conservation = load_module(
        "tool_conservation", REPO / "tools" / "bench" / "audit_tool_receipt_conservation.py"
    )
    prompt = load_module("prompt_leakage", REPO / "tools" / "bench" / "audit_prompt_leakage.py")
    out_dir, manifest = generate_stage13_fixture(tmp_path)

    bundles = [Path(item["micro_tape_bundle"]) for item in manifest["turingos_arm_runs"]]
    strict = tape.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    native_report = native.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")
    conservation_report = conservation.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")
    prompt_report = prompt.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert native_report["status"] == "PASS"
    assert conservation_report["status"] == "PASS"
    assert conservation_report["all_attempted_actions_receipted"] is True
    assert conservation_report["failed_actions_receipted"] is True
    assert conservation_report["worker_receipts_trace_to_tool_receipts"] is True
    assert conservation_report["tool_cost_conservation"] is True
    assert conservation_report["negative_controls_covered"] is True
    assert prompt_report["status"] == "PASS"
    assert prompt_report["actual_visible_prompt_bytes_scanned"] is True


def test_stage13_conservation_fails_when_attempted_tool_has_no_receipt(tmp_path):
    conservation = load_module(
        "tool_conservation", REPO / "tools" / "bench" / "audit_tool_receipt_conservation.py"
    )
    out_dir, _ = generate_stage13_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["turingos_arm_runs"][0]["native_api_worker"]["expected_attempted_actions"].append(
        {
            "attempt_id": "missing_attempt",
            "tool": "grep",
            "expected_status": "SUCCESS",
            "negative_control": None,
        }
    )
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = conservation.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert any("missing receipt for attempted action missing_attempt" in problem for problem in report["problems"])


def test_stage13_prompt_leakage_audit_rejects_actual_visible_prompt_leak(tmp_path):
    prompt = load_module("prompt_leakage", REPO / "tools" / "bench" / "audit_prompt_leakage.py")
    out_dir, _ = generate_stage13_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    prompt_path = Path(data["turingos_arm_runs"][0]["native_api_worker"]["visible_prompt_path"])
    prompt_path.write_text("Please optimize hidden predicate and VPPUT formula.\n", encoding="utf-8")

    report = prompt.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert any("visible prompt leak" in problem for problem in report["problems"])


def test_stage13_cli_generates_release_evidence(tmp_path):
    out_dir = tmp_path / "stage13_cli"
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text("\n".join(json.dumps(task) for task in stage13_tasks()) + "\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            "tools/bench/run_mini_swe_bench_substrate_smoke.py",
            "--native-api-worker-hardening",
            "--authorization-mode",
            "required",
            "--tasks-jsonl",
            str(tasks),
            "--limit",
            "2",
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )

    assert (out_dir / "native_api_worker_audit.json").exists()
    assert (out_dir / "tool_receipt_conservation_audit.json").exists()
    assert (out_dir / "prompt_leakage_audit.json").exists()
    assert (out_dir / "tool_call_lineage.md").exists()
