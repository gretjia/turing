import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
EXPECTED_CLASSES = {
    "INSTALL_FAIL",
    "TEST_TIMEOUT",
    "WRONG_FILE",
    "NO_REPRO",
    "OVERBROAD_PATCH",
    "SEMANTIC_FAIL",
    "FLAKY_ORACLE",
    "DEPENDENCY_GAP",
    "CONTEXT_MISSING",
    "PATCH_APPLIES_BUT_WRONG",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def stage10_tasks():
    return [
        {
            "instance_id": f"stage10_{failure_class.lower()}",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": f"Stage10 failure taxonomy fixture for {failure_class}",
            "stage10_failure_class": failure_class,
        }
        for failure_class in sorted(EXPECTED_CLASSES)
    ]


def generate_stage10_fixture(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    out_dir = tmp_path / "stage10"
    manifest = runner.generate_stage10_failure_taxonomy_fixture(out_dir, stage10_tasks())
    return out_dir, manifest


def test_stage10_failure_taxonomy_fixture_covers_all_classes_and_strict_replay(tmp_path):
    auditor = load_module("tape_auditor", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    taxonomy = load_module("taxonomy", REPO / "tools" / "bench" / "audit_failure_taxonomy.py")
    out_dir, manifest = generate_stage10_fixture(tmp_path)

    bundles = [Path(item["micro_tape_bundle"]) for item in manifest["turingos_arm_runs"]]
    strict = auditor.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    report = taxonomy.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["failed_progress_zero"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert report["status"] == "PASS"
    assert set(report["classes_seen"]) == EXPECTED_CLASSES
    assert report["all_failures_have_failure_node"] is True
    assert report["all_failures_have_broadcast_rule_candidate"] is True
    assert report["broadcast_candidates_preserve_only"] is True
    assert report["raw_logs_not_broadcast"] is True


def test_stage10_taxonomy_audit_fails_on_missing_class_coverage(tmp_path):
    taxonomy = load_module("taxonomy", REPO / "tools" / "bench" / "audit_failure_taxonomy.py")
    out_dir, _ = generate_stage10_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["turingos_arm_runs"] = data["turingos_arm_runs"][:-1]
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = taxonomy.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert "taxonomy coverage incomplete" in report["problems"]


def test_stage10_failure_taxonomy_cli_writes_report(tmp_path):
    out_dir, _ = generate_stage10_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    output = out_dir / "failure_taxonomy_audit.json"

    subprocess.run(
        ["python3", "tools/bench/audit_failure_taxonomy.py", "--coverage", str(coverage), "--out", str(output)],
        cwd=REPO,
        check=True,
    )

    assert json.loads(output.read_text())["status"] == "PASS"


def test_stage10_taxonomy_rejects_forbidden_broadcast_candidate_content():
    taxonomy = load_module("taxonomy", REPO / "tools" / "bench" / "audit_failure_taxonomy.py")

    candidate = {
        "candidate_only": True,
        "activation_event_id": None,
        "raw_log_text_absent": True,
        "hidden_predicates_absent": True,
        "guidance": "Avoid this raw stderr: traceback from hidden predicate threshold.",
    }

    assert taxonomy.broadcast_candidate_has_forbidden_content(candidate) is True
