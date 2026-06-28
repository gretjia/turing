import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_runner():
    path = REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py"
    spec = importlib.util.spec_from_file_location("runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_tape_auditor():
    path = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
    spec = importlib.util.spec_from_file_location("tape", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_test_local_authority_event_advances_authorization_head(tmp_path):
    runner = load_runner()
    tape = load_tape_auditor()
    repo = tmp_path / "micro"
    runner.init_micro_git(repo)
    registry = tape.load_event_registry()
    state = runner.stage6_base_state()
    runner.append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=tape.canonical_payload_digest,
        event_type="SystemConstitutionAccepted",
        payload={"constitution_digest": runner.digest_text("constitution")},
        writer_id="writer:bootstrap",
    )

    auth = runner.append_test_local_authorization(
        repo=repo,
        event_type="AtomAuthorized",
        payload={
            "atom_id": "atom_stage12_test",
            "approval_id": "ap_stage12_test",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
    )

    assert auth["event_type"] == "AtomAuthorized"
    assert auth["authorization_head_moved"] is True
    assert auth["accepted_head_moved"] is False
    assert auth["head_set"]["authorization_head"] == auth["event_id"]
    assert auth["head_set"]["accepted_head"] != auth["event_id"]


def test_cli_accepts_explicit_test_local_authority_for_required_mode(tmp_path):
    runner = load_runner()
    task = {
        "instance_id": "stage12_test_local_authority_cli",
        "repo": "django/django",
        "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
        "problem_statement": "Stage12 test-local authority CLI probe",
    }
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    subprocess.run(
        [
            "python3",
            "tools/bench/run_mini_swe_bench_substrate_smoke.py",
            "--authorization-mode",
            "required",
            "--authority-provider",
            "test-local",
            "--tasks-jsonl",
            str(tasks),
            "--out-dir",
            str(out_dir),
            "--limit",
            "1",
            "--worker-mode",
            "fake",
            "--max-turns",
            "1",
        ],
        cwd=REPO,
        check=True,
    )

    coverage = json.loads((out_dir / "substrate_coverage.json").read_text())
    run = coverage["turingos_arm_runs"][0]
    assert run["authorization_mode"] == "required"
    assert run["authority_provider"] == "test-local"
    assert run["fallback_to_auto_authorization"] is False
    assert run["authorization_head"].startswith("mu:")
    assert run["micro_tape_bundle"].endswith("micro_tape.bundle")
    assert Path(run["micro_tape_bundle"]).exists()
    assert run["micro_tape_bundle_sha256"].startswith("sha256:")
    assert run["event_calls"]["AtomAuthorized"] == 1
    assert run["event_calls"]["WorkerDispatchAuthorized"] == 1


def test_stage12_real_loop_cli_records_first_failed_attempt_and_evaluator_refreshes_bundle(tmp_path):
    task = {
        "instance_id": "django__django-stage12-loop-cli",
        "repo": "django/django",
        "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
        "problem_statement": "Stage12 loop CLI probe",
        "test_patch": "diff --git a/tests/test_example.py b/tests/test_example.py\n",
        "FAIL_TO_PASS": ["tests.example.TestCase.test_regression"],
    }
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    eval_dir = out_dir / "patch_eval"

    subprocess.run(
        [
            "python3",
            "tools/bench/run_mini_swe_bench_substrate_smoke.py",
            "--authorization-mode",
            "required",
            "--authority-provider",
            "test-local",
            "--stage12-real-loop",
            "--tasks-jsonl",
            str(tasks),
            "--out-dir",
            str(out_dir),
            "--limit",
            "1",
            "--worker-mode",
            "fake",
            "--max-turns",
            "1",
        ],
        cwd=REPO,
        check=True,
    )
    coverage = json.loads((out_dir / "substrate_coverage.json").read_text())
    run = coverage["turingos_arm_runs"][0]
    first = run["stage12_first_attempt"]
    assert first["official_evidence_event_id"].startswith("mu:")
    assert first["failure_event_id"].startswith("mu:")
    assert first["retry_authorization_event_id"].startswith("mu:")
    assert first["worker_receipt_id"] != run["worker_receipt_id"]

    subprocess.run(
        [
            "python3",
            "tools/bench/evaluate_django_swe_bench_patches.py",
            "--tasks-jsonl",
            str(tasks),
            "--limit",
            "1",
            "--turingos-dir",
            str(out_dir),
            "--direct-dir",
            str(out_dir / "direct_baseline"),
            "--out",
            str(eval_dir),
            "--substrate-coverage",
            str(out_dir / "substrate_coverage.json"),
            "--import-turingos-evidence",
            "--stage12-loop-until-pass",
        ],
        cwd=REPO,
        check=True,
    )

    refreshed = json.loads((out_dir / "substrate_coverage.json").read_text())
    run = refreshed["turingos_arm_runs"][0]
    loop = run["loop_until_pass"]
    assert refreshed["scientific_status"] == "STAGE12_20TASK_SCALE_PROTOCOL_EVIDENCE_NOT_STATISTICAL_CLAIM"
    assert loop["first_failure_event_id"] == first["failure_event_id"]
    assert loop["first_failure_official_evidence_event_id"] == first["official_evidence_event_id"]
    assert loop["retry_policy_event_id"] == first["retry_authorization_event_id"]
    assert loop["attempts_total"] == 2
    assert loop["failed_attempts_before_accept"] == 1
    assert loop["budget_exhausted"] is True
    assert run["micro_tape_bundle_refreshed_after_eval"] is True

    audit_dir = out_dir / "strict"
    subprocess.run(
        [
            "python3",
            "tools/bench/audit_micro_tape_decision_dag.py",
            "--strict-vpput",
            "--strict-terminal-market",
            "--require-authorization-head",
            "--coverage",
            str(out_dir / "substrate_coverage.json"),
            "--out-dir",
            str(audit_dir),
        ],
        cwd=REPO,
        check=True,
    )
    strict = json.loads((audit_dir / "micro_tape_decision_dag_audit.json").read_text())
    assert strict["status_summary"]["overall"] == "PASS"
