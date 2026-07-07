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


def write_config(path: Path, **overrides):
    data = {
        "official_harness_kind": "upstream_swebench_docker",
        "command": "python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Verified --split test --predictions_path predictions.jsonl --run_id unit --max_workers 2",
        "docker_environment_used": True,
        "evaluation_results_present": True,
        "stdout_stderr_digests_present": True,
        "docker_build_or_cache_logs_present": True,
        "repo_local_evaluator_marked_official": False,
        "fail_to_pass_checked": True,
        "pass_to_pass_checked": True,
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_official_harness_identity_accepts_upstream_docker_run_evaluation(tmp_path):
    auditor = load_module("official_harness_identity", REPO / "tools/bench/audit_official_harness_identity.py")
    config = tmp_path / "official_harness_descriptor.json"
    write_config(config)

    report = auditor.audit_config(config)

    assert report["status"] == "PASS"
    assert report["official_harness_kind"] == "upstream_swebench_docker"


def test_official_harness_identity_rejects_repo_local_evaluator_called_official(tmp_path):
    auditor = load_module("official_harness_identity", REPO / "tools/bench/audit_official_harness_identity.py")
    config = tmp_path / "official_harness_descriptor.json"
    write_config(
        config,
        official_harness_kind="repo_local",
        command="python tools/bench/evaluate_django_swe_bench_patches.py --tasks-jsonl x",
        repo_local_evaluator_marked_official=True,
    )

    report = auditor.audit_config(config)

    assert report["status"] == "FAIL"
    assert "official_harness_kind must be upstream_swebench_docker" in report["problems"]
    assert "repo-local evaluator cannot be marked official" in report["problems"]


def test_official_harness_identity_rejects_missing_pass_to_pass(tmp_path):
    auditor = load_module("official_harness_identity", REPO / "tools/bench/audit_official_harness_identity.py")
    config = tmp_path / "official_harness_descriptor.json"
    write_config(config, pass_to_pass_checked=False)

    report = auditor.audit_config(config)

    assert report["status"] == "FAIL"
    assert "pass_to_pass_checked must be true" in report["problems"]


def test_official_harness_identity_cli(tmp_path):
    config = tmp_path / "official_harness_descriptor.json"
    out = tmp_path / "official_harness_audit.json"
    write_config(config)

    subprocess.run(
        [
            "python3",
            "tools/bench/audit_official_harness_identity.py",
            "--config",
            str(config),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
    )

    assert json.loads(out.read_text())["status"] == "PASS"
