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


def generate_stage11_fixture(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    out_dir = tmp_path / "stage11"
    manifest = runner.generate_stage11_loop_until_pass_fixture(out_dir, runner.default_stage11_tasks())
    return out_dir, manifest


def load_stage11_auditors():
    return (
        load_module("loop", REPO / "tools" / "bench" / "audit_loop_until_pass.py"),
        load_module("fm", REPO / "tools" / "bench" / "audit_failure_memory_activation.py"),
        load_module("classifier", REPO / "tools" / "bench" / "audit_real_classifier.py"),
    )


def test_stage11_strict_microtape_pass(tmp_path):
    tape_auditor = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    loop_audit, fm_audit, classifier_audit = load_stage11_auditors()
    out_dir, manifest = generate_stage11_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    bundles = [Path(item["micro_tape_bundle"]) for item in manifest["turingos_arm_runs"]]

    strict = tape_auditor.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert strict["status_summary"]["failed_progress_zero"] == "PASS"
    assert strict["status_summary"]["accepted_final_progress_one"] == "PASS"
    assert loop_audit.audit_coverage(coverage)["status"] == "PASS"
    assert fm_audit.audit_coverage(coverage)["status"] == "PASS"
    assert classifier_audit.audit_coverage(coverage)["status"] == "PASS"


def test_stage11_requires_failed_then_accepted(tmp_path):
    loop_audit, _, _ = load_stage11_auditors()
    out_dir, _ = generate_stage11_fixture(tmp_path)

    report = loop_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert report["status"] == "PASS"
    assert report["attempts_total"] >= 2
    assert report["failed_attempts_before_accept"] >= 1
    assert report["accepted_attempt_index"] > report["first_failed_attempt_index"]


def test_stage11_requires_broadcast_rule_activation_after_failure_certificate(tmp_path):
    loop_audit, fm_audit, _ = load_stage11_auditors()
    out_dir, _ = generate_stage11_fixture(tmp_path)

    loop = loop_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")
    fm = fm_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert loop["status"] == "PASS"
    assert loop["failure_certificate_event_id"].startswith("mu:")
    assert loop["broadcast_rule_activated_event_id"].startswith("mu:")
    assert fm["status"] == "PASS"
    assert fm["activated_rule_event_id"] == loop["broadcast_rule_activated_event_id"]


def test_stage11_second_capsule_consumes_activated_rule(tmp_path):
    _, fm_audit, _ = load_stage11_auditors()
    out_dir, _ = generate_stage11_fixture(tmp_path)

    report = fm_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert report["status"] == "PASS"
    assert report["later_capsule_consumed_rule"] is True
    assert report["injected_into_capsule_id"]


def test_stage11_rejects_scenario_label_classifier():
    _, _, classifier_audit = load_stage11_auditors()

    decision = {
        "failure_class": "WRONG_FILE",
        "observer_derived_failure_class": True,
        "classifier_inputs": {"scenario_label": "wrong_file"},
    }

    problems = classifier_audit.validate_classifier_decision(decision)
    assert any("forbidden classifier input" in problem for problem in problems)


def test_stage11_all_attempt_costs_in_vpput(tmp_path):
    loop_audit, _, _ = load_stage11_auditors()
    out_dir, _ = generate_stage11_fixture(tmp_path)

    report = loop_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert report["status"] == "PASS"
    assert report["all_attempt_costs_counted"] is True


def test_stage11_no_raw_logs_or_hidden_predicates_in_activated_rule():
    _, fm_audit, _ = load_stage11_auditors()

    payload = {
        "abstract_pattern": "retry after raw stderr traceback",
        "guidance": "hidden predicate threshold",
    }

    assert fm_audit.contains_forbidden_visible_content(payload) is True


def test_stage11_failed_attempt_progress_zero_then_final_progress_one(tmp_path):
    loop_audit, _, _ = load_stage11_auditors()
    out_dir, _ = generate_stage11_fixture(tmp_path)

    report = loop_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert report["status"] == "PASS"
    assert report["failed_attempt_progress_zero"] is True
    assert report["terminal_progress_one"] is True


def test_stage11_budget_exhausted_if_no_pass(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    loop_audit, _, _ = load_stage11_auditors()
    out_dir = tmp_path / "budget_exhausted"
    task = runner.default_stage11_tasks()[0]
    manifest = runner.generate_stage11_loop_until_pass_fixture(out_dir, [task], force_budget_exhausted=True)

    report = loop_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert manifest["turingos_arm_runs"][0]["loop_until_pass"]["budget_exhausted"] is True
    assert report["status"] == "FAIL"
    assert "budget exhausted before CandidateAccepted" in report["problems"]


def test_stage11_negative_no_broadcast_consumption_fails(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    _, fm_audit, _ = load_stage11_auditors()
    out_dir = tmp_path / "bad_no_consumption"
    task = runner.default_stage11_tasks()[0]
    runner.generate_stage11_loop_until_pass_fixture(out_dir, [task], omit_broadcast_consumption=True)

    report = fm_audit.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert report["status"] == "FAIL"
    assert "later WorkCapsuleBuilt did not consume the broadcast rule" in report["problems"]


def test_stage11_cli_writes_manifest(tmp_path):
    out_dir = tmp_path / "cli"

    subprocess.run(
        [
            "python3",
            "tools/bench/run_mini_swe_bench_substrate_smoke.py",
            "--loop-until-pass-fixture",
            "--authorization-mode",
            "required",
            "--out-dir",
            str(out_dir),
            "--limit",
            "3",
        ],
        cwd=REPO,
        check=True,
    )

    manifest = json.loads((out_dir / "loop_manifest.json").read_text())
    assert manifest["schema_id"] == "Stage11LoopUntilPassFixtureManifest.v1"
    assert manifest["sample_size"] == 3
