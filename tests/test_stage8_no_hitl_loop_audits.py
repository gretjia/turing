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


def generate_stage8_fixture(tmp_path):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    task = {
        "instance_id": "django__django-12039_stage8_loop",
        "repo": "django/django",
        "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
        "problem_statement": "Use proper whitespace in CREATE INDEX statements.",
    }
    out_dir = tmp_path / "stage8"
    manifest = runner.generate_stage8_no_hitl_loop_fixture(out_dir, [task])
    return out_dir, manifest


def stage8_reports(tmp_path):
    tape_auditor = load_module("tape_auditor", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    no_hitl = load_module("no_hitl", REPO / "tools" / "bench" / "audit_no_hitl_loop.py")
    failure_memory = load_module("failure_memory", REPO / "tools" / "bench" / "audit_failure_memory.py")
    out_dir, manifest = generate_stage8_fixture(tmp_path)
    bundles = [Path(item["micro_tape_bundle"]) for item in manifest["turingos_arm_runs"]]
    strict = tape_auditor.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    no_hitl_report = no_hitl.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")
    failure_memory_report = failure_memory.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")
    return out_dir, manifest, strict, no_hitl_report, failure_memory_report


def test_stage8_no_hitl_loop_fixture_proves_failure_memory_retry_and_accept(tmp_path):
    _, _, strict, no_hitl_report, failure_memory_report = stage8_reports(tmp_path)

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert strict["status_summary"]["vpput_accounting"] == "PASS"
    assert strict["status_summary"]["market_accounting_correctness"] == "PASS"
    assert no_hitl_report["status"] == "PASS"
    assert no_hitl_report["human_intervention_count"] == 0
    assert no_hitl_report["manual_patch_count"] == 0
    assert no_hitl_report["manual_approval_count"] == 0
    assert no_hitl_report["fallback_to_auto_authorization"] is False
    assert no_hitl_report["verified_from_micro_tape_bundle_only"] is True
    assert failure_memory_report["status"] == "PASS"
    assert failure_memory_report["broadcast_rule_reduced_from_tape"] is True
    assert failure_memory_report["raw_log_text_absent_from_visible_capsule"] is True
    assert failure_memory_report["hidden_predicates_absent_from_visible_capsule"] is True
    assert failure_memory_report["injected_into_capsule_id"]


def test_no_hitl_loop_requires_failure_then_broadcast_then_retry_then_accept(tmp_path):
    _, _, _, no_hitl_report, _ = stage8_reports(tmp_path)
    run = no_hitl_report["runs"][0]

    assert no_hitl_report["status"] == "PASS"
    assert run["first_failure_event_id"]
    assert run["broadcast_rule_event_id"]
    assert run["retry_policy_event_id"]
    assert run["second_attempt_capsule_event_id"]
    assert run["terminal_candidate_accepted_event_id"]


def test_broadcast_rule_must_be_consumed_by_later_capsule(tmp_path):
    _, _, _, _, failure_memory_report = stage8_reports(tmp_path)

    assert failure_memory_report["status"] == "PASS"
    assert failure_memory_report["broadcast_rule_event_id"]
    assert failure_memory_report["injected_into_capsule_id"]


def test_raw_failure_log_not_in_visible_capsule(tmp_path):
    _, _, _, _, failure_memory_report = stage8_reports(tmp_path)

    assert failure_memory_report["raw_log_refs_present_only_as_private_evidence"] is True
    assert failure_memory_report["raw_log_text_absent_from_visible_capsule"] is True
    assert failure_memory_report["hidden_predicates_absent_from_visible_capsule"] is True


def test_require_authorization_head_passes_in_stage8_fixture(tmp_path):
    _, _, strict, _, _ = stage8_reports(tmp_path)

    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert strict["status_summary"]["constitutional_protocol_audit"] == "PASS"


def test_no_fallback_to_auto_authorization_when_required(tmp_path):
    _, manifest, _, no_hitl_report, _ = stage8_reports(tmp_path)

    assert manifest["turingos_arm_runs"][0]["authorization_mode"] == "required"
    assert no_hitl_report["fallback_to_auto_authorization"] is False


def test_failed_attempt_progress_zero_then_final_progress_one(tmp_path):
    _, _, strict, _, _ = stage8_reports(tmp_path)

    assert strict["status_summary"]["failed_progress_zero"] == "PASS"
    assert strict["status_summary"]["accepted_final_progress_one"] == "PASS"
    assert strict["status_summary"]["vpput_accounting"] == "PASS"


def test_market_reward_only_after_terminal_accept_or_terminal_failure(tmp_path):
    _, _, strict, _, _ = stage8_reports(tmp_path)

    assert strict["status_summary"]["economic_timing"] == "PASS"
    assert strict["status_summary"]["market_accounting_correctness"] == "PASS"


def test_manual_intervention_count_zero(tmp_path):
    _, _, _, no_hitl_report, _ = stage8_reports(tmp_path)

    assert no_hitl_report["human_intervention_count"] == 0
    assert no_hitl_report["manual_patch_count"] == 0
    assert no_hitl_report["manual_approval_count"] == 0
    assert no_hitl_report["manual_rerun_selection_count"] == 0


def test_failure_memory_forbidden_marker_detection_is_case_insensitive():
    failure_memory = load_module("failure_memory", REPO / "tools" / "bench" / "audit_failure_memory.py")
    visible_text = "\n".join(failure_memory.string_values({"visible": ["Traceback: stack frame"]})).lower()

    assert "traceback" in visible_text


def test_no_hitl_loop_audit_fails_without_retry_consuming_broadcast_rule(tmp_path):
    no_hitl = load_module("no_hitl", REPO / "tools" / "bench" / "audit_no_hitl_loop.py")
    out_dir, _ = generate_stage8_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["turingos_arm_runs"][0]["no_hitl_loop"]["second_attempt_capsule_event_id"] = None
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = no_hitl.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert "second_attempt_capsule_event_id" in report["missing"]


def test_stage8_cli_tools_write_reports(tmp_path):
    out_dir, _ = generate_stage8_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    no_hitl_out = out_dir / "no_hitl_loop_audit.json"
    failure_out = out_dir / "failure_memory_audit.json"

    subprocess.run(
        ["python3", "tools/bench/audit_no_hitl_loop.py", "--coverage", str(coverage), "--out", str(no_hitl_out)],
        cwd=REPO,
        check=True,
    )
    subprocess.run(
        ["python3", "tools/bench/audit_failure_memory.py", "--coverage", str(coverage), "--out", str(failure_out)],
        cwd=REPO,
        check=True,
    )

    assert json.loads(no_hitl_out.read_text())["status"] == "PASS"
    assert json.loads(failure_out.read_text())["status"] == "PASS"
