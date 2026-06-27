import importlib.util
import hashlib
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tools" / "bench" / "mini_swe_bench_grok_headless.py"
AUDITOR = REPO / "tools" / "bench" / "audit_mini_swe_bench_plan.py"
SUBSTRATE_AUDITOR = REPO / "tools" / "bench" / "audit_mini_swe_bench_substrate_coverage.py"
SUBSTRATE_SMOKE = REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py"
META_REVIEW = REPO / "tools" / "bench" / "run_deepseek_meta_review.py"
DIRECT_BASELINE = REPO / "tools" / "bench" / "run_direct_grok_baseline_smoke.py"
PATCH_EVAL = REPO / "tools" / "bench" / "evaluate_django_swe_bench_patches.py"
SMOKE = REPO / "tools" / "bench" / "smoke_mini_swe_bench_grok_headless.sh"


def load_harness():
    spec = importlib.util.spec_from_file_location("mini_swe_bench_grok_headless", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_grok_headless_argv_turns_planning_memory_and_subagents_off():
    harness = load_harness()
    argv = harness.grok_worker_argv(
        cwd="/tmp/turingos-mini-swe/task",
        prompt="visible capsule",
        model="grok-code-fast-1",
        max_turns=8,
    )

    assert argv[:2] == ["grok", "-p"]
    assert ["--cwd", "/tmp/turingos-mini-swe/task"] in [
        argv[i : i + 2] for i in range(len(argv) - 1)
    ]
    assert ["--output-format", "plain"] in [argv[i : i + 2] for i in range(len(argv) - 1)]
    assert "--reasoning-effort" not in argv
    assert "--effort" not in argv
    assert "--always-approve" in argv
    assert "--no-plan" in argv
    assert "--no-memory" in argv
    assert "--no-subagents" in argv
    assert "--disable-web-search" in argv


def test_dry_run_writes_baseline_and_turingos_plan(tmp_path):
    harness = load_harness()
    tasks = tmp_path / "verified-mini.jsonl"
    tasks.write_text(
        json.dumps(
            {
                "instance_id": "django__django-00001",
                "repo": "https://github.com/django/django",
                "base_commit": "abc123",
                "problem_statement": "Fix the failing regression test.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "run.json"

    rc = harness.main(
        [
            "--tasks-jsonl",
            str(tasks),
            "--out",
            str(out),
            "--dry-run",
            "--limit",
            "1",
        ]
    )

    assert rc == 0
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "MiniSweBenchGrokHeadlessRun.v1"
    assert packet["benchmark"] == "swe_bench_verified_mini"
    assert packet["worker_id"].startswith("worker:sha256:")
    assert packet["experiment_design"] == {
        "schema_id": "MiniSweBenchExperimentDesign.v1",
        "assignment": "paired_within_task",
        "arms": ["direct_grok_baseline", "turingos_grok_worker"],
        "statistical_unit": "swe_bench_instance",
        "minimum_real_tasks": 50,
        "randomization_seed": 20260627,
        "pre_registered_before_execution": True,
        "primary_metric": {
            "name": "resolved_by_predicate",
            "type": "paired_binary",
            "truth_source": "micro_tape_predicate_replay",
        },
        "secondary_metrics": [
            "cost_per_resolved_task",
            "wall_time_ms",
            "retry_count",
            "failure_class_distribution",
            "replay_pass_rate",
            "invalid_accepted_head_attempts",
        ],
        "statistical_tests": [
            {
                "name": "mcnemar_exact",
                "applies_to": "paired_binary_resolution",
            },
            {
                "name": "paired_bootstrap_ci",
                "confidence": "0.95",
                "applies_to": "paired_differences",
            },
        ],
        "multiple_runs_policy": "report_all_runs_no_best_of_n_unless_preregistered",
        "exclusion_policy": "no_post_hoc_exclusions",
    }
    assert packet["meta_ai"] == {
        "schema_id": "MetaAIProvider.v1",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "credential_material": "env_only_not_serialized",
        "authority": "none",
        "accepted_head_authority": False,
    }
    assert packet["thinking_contract"] == "grok_no_plan_no_memory_no_subagents_plain_output"
    assert packet["truth_guard"]["accepted_head_policy"] == "predicate_only"
    assert packet["truth_guard"]["forbidden_acceptance_signals"] == [
        "exit_code_0",
        "ci_green",
        "grok_self_report",
        "official_benchmark_result",
    ]
    assert {run["mode"] for run in packet["runs"]} == {
        "direct_grok_baseline",
        "turingos_grok_worker",
    }
    for run in packet["runs"]:
        argv = run["grok_command"]["argv"]
        assert ["--output-format", "plain"] in [argv[i : i + 2] for i in range(len(argv) - 1)]
        assert "--no-plan" in argv
        assert "--reasoning-effort" not in argv
        assert "--effort" not in argv
        assert run["task"]["instance_id"] == "django__django-00001"


def test_meta_ai_env_key_is_not_serialized(tmp_path, monkeypatch):
    harness = load_harness()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sentinel-secret-must-not-appear")
    tasks = tmp_path / "verified-mini.jsonl"
    tasks.write_text(
        json.dumps(
            {
                "instance_id": "sympy__sympy-00001",
                "repo": "https://github.com/sympy/sympy",
                "base_commit": "def456",
                "problem_statement": "Fix the failing symbolic regression.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "run.json"

    rc = harness.main(
        [
            "--tasks-jsonl",
            str(tasks),
            "--out",
            str(out),
            "--dry-run",
            "--meta-provider",
            "deepseek",
            "--meta-model",
            "deepseek-v4-pro",
            "--meta-api-key-env",
            "DEEPSEEK_API_KEY",
        ]
    )

    assert rc == 0
    raw = out.read_text(encoding="utf-8")
    assert "sentinel-secret-must-not-appear" not in raw
    assert "DEEPSEEK_API_KEY" in raw


def test_clean_auditor_passes_scientific_smoke_plan(tmp_path):
    harness = load_harness()
    tasks = tmp_path / "verified-mini.jsonl"
    tasks.write_text(
        "\n".join(
            json.dumps(
                {
                    "instance_id": f"project__repo-{index:05d}",
                    "repo": "https://github.com/example/repo",
                    "base_commit": f"base{index}",
                    "problem_statement": "Fix the failing regression test.",
                },
                sort_keys=True,
            )
            for index in range(2)
        )
        + "\n",
        encoding="utf-8",
    )
    plan = tmp_path / "plan.json"
    audit = tmp_path / "audit.json"
    assert harness.main(["--tasks-jsonl", str(tasks), "--out", str(plan), "--dry-run"]) == 0

    proc = subprocess.run(
        [
            "python3",
            str(AUDITOR),
            "--plan",
            str(plan),
            "--out",
            str(audit),
            "--allow-smoke",
            "--min-tasks",
            "2",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    packet = json.loads(audit.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "MiniSweBenchPlanAudit.v1"
    assert packet["verdict"] == "PASS"
    assert packet["auditor_independence"]["imports_benchmark_harness"] is False
    assert packet["scientific_status"] == "SMOKE_ONLY_NOT_REAL_BENCHMARK"


def test_clean_auditor_rejects_underpowered_real_plan(tmp_path):
    harness = load_harness()
    tasks = tmp_path / "verified-mini.jsonl"
    tasks.write_text(
        json.dumps(
            {
                "instance_id": "django__django-00001",
                "repo": "https://github.com/django/django",
                "base_commit": "abc123",
                "problem_statement": "Fix the failing regression test.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = tmp_path / "plan.json"
    audit = tmp_path / "audit.json"
    assert harness.main(["--tasks-jsonl", str(tasks), "--out", str(plan), "--dry-run"]) == 0

    proc = subprocess.run(
        ["python3", str(AUDITOR), "--plan", str(plan), "--out", str(audit)],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    packet = json.loads(audit.read_text(encoding="utf-8"))
    assert packet["verdict"] == "FAIL"
    assert any(
        finding["id"] == "sample_size_below_minimum"
        for finding in packet["blocking_findings"]
    )


def test_benchmark_smoke_script_runs_harness_and_auditor(tmp_path):
    proc = subprocess.run(
        ["bash", str(SMOKE), str(tmp_path)],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    audit = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "PASS"
    assert (tmp_path / "plan.json").exists()


def test_substrate_coverage_auditor_rejects_missing_modules(tmp_path):
    coverage = tmp_path / "coverage.json"
    out = tmp_path / "audit.json"
    coverage.write_text(
        json.dumps(
            {
                "schema_id": "MiniSweBenchSubstrateCoverage.v1",
                "run_id": "coverage_missing",
                "sample_size": 50,
                "turingos_arm_runs": [
                    {
                        "instance_id": "django__django-00001",
                        "module_calls": {
                            "M0_law_goal_harness": 1,
                            "M6_worker_profiles": 1,
                        },
                        "process_calls": {
                            "grok_cli": 1,
                        },
                        "event_calls": {
                            "WorkCapsuleBuilt": 1,
                        },
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "python3",
            str(SUBSTRATE_AUDITOR),
            "--coverage",
            str(coverage),
            "--out",
            str(out),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert packet["verdict"] == "FAIL"
    missing = {finding["id"] for finding in packet["blocking_findings"]}
    assert "missing_module_M2_micro_git_tape" in missing
    assert "missing_process_turingd" in missing
    assert "missing_event_CandidateAccepted_or_FailureNode" in missing


def test_substrate_coverage_auditor_accepts_all_required_modules(tmp_path):
    coverage = tmp_path / "coverage.json"
    out = tmp_path / "audit.json"
    module_calls = {
        module_id: 1
        for module_id in [
            "M0_law_goal_harness",
            "M1_canonical_codec",
            "M2_micro_git_tape",
            "M3_event_registry",
            "M4_single_loop",
            "M5_goal_module_atom_capsule",
            "M6_worker_profiles",
            "M7_executor_broker",
            "M8_macro_observer",
            "M9_predicate_kernel",
            "M10_evidence_approval",
            "M11_failure_memory",
            "M12_market_substrate",
            "M13_marketrouter_shadow",
            "M14_pput_accounting",
            "M15_projection",
            "M16_integration_queue",
            "M17_e2e_handoff",
        ]
    }
    process_calls = {
        process: 1
        for process in [
            "turingd",
            "turing-execd",
            "turing-mcp",
            "turing-marketd",
            "turing-pputd",
            "turing-viewd",
            "grok_cli",
        ]
    }
    event_calls = {
        event: 1
        for event in [
            "GoalStateProposed",
            "WorkCapsuleBuilt",
            "MarketCreated",
            "BudgetAllocated",
            "WorkerReceiptImported",
            "MacroObservationImported",
            "CandidateAccepted",
            "FailureNode",
            "MarketSettled",
            "PPUTAccounted",
            "PredicateEvaluated",
        ]
    }
    coverage.write_text(
        json.dumps(
            {
                "schema_id": "MiniSweBenchSubstrateCoverage.v1",
                "run_id": "coverage_full",
                "sample_size": 50,
                "turingos_arm_runs": [
                    {
                        "instance_id": "django__django-00001",
                        "module_calls": module_calls,
                        "process_calls": process_calls,
                        "event_calls": event_calls,
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "python3",
            str(SUBSTRATE_AUDITOR),
            "--coverage",
            str(coverage),
            "--out",
            str(out),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert packet["verdict"] == "PASS"
    assert packet["scientific_status"] == "SUBSTRATE_COVERAGE_READY"


def test_substrate_coverage_auditor_accepts_real_meta_ai_review(tmp_path):
    coverage = tmp_path / "coverage.json"
    meta = tmp_path / "meta.json"
    out = tmp_path / "audit.json"
    modules = [
        "M0_law_goal_harness",
        "M1_canonical_codec",
        "M2_micro_git_tape",
        "M3_event_registry",
        "M4_single_loop",
        "M5_goal_module_atom_capsule",
        "M6_worker_profiles",
        "M7_executor_broker",
        "M8_macro_observer",
        "M9_predicate_kernel",
        "M10_evidence_approval",
        "M11_failure_memory",
        "M12_market_substrate",
        "M13_marketrouter_shadow",
        "M14_pput_accounting",
        "M15_projection",
        "M16_integration_queue",
        "M17_e2e_handoff",
    ]
    coverage.write_text(
        json.dumps(
            {
                "schema_id": "MiniSweBenchSubstrateCoverage.v1",
                "run_id": "coverage_full_meta",
                "sample_size": 1,
                "turingos_arm_runs": [
                    {
                        "instance_id": "django__django-11790",
                        "module_calls": {module: 1 for module in modules},
                        "process_calls": {
                            "turingd": 1,
                            "turing-execd": 1,
                            "turing-mcp": 1,
                            "turing-marketd": 1,
                            "turing-pputd": 1,
                            "turing-viewd": 1,
                            "grok_cli": 1,
                        },
                        "event_calls": {
                            "GoalStateProposed": 1,
                            "WorkCapsuleBuilt": 1,
                            "MarketCreated": 1,
                            "BudgetAllocated": 1,
                            "WorkerReceiptImported": 1,
                            "MacroObservationImported": 1,
                            "FailureNode": 1,
                            "MarketSettled": 1,
                            "PPUTAccounted": 1,
                            "PredicateEvaluated": 1,
                        },
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    meta.write_text(
        json.dumps(
            {
                "schema_id": "DeepSeekMetaAIReviewRun.v1",
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "status": "PASS",
                "authority": "none",
                "accepted_head_authority": False,
                "credential_material": "env_only_not_serialized",
                "review": {"verdict": "WARN"},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "python3",
            str(SUBSTRATE_AUDITOR),
            "--coverage",
            str(coverage),
            "--out",
            str(out),
            "--min-sample-size",
            "1",
            "--worker-process",
            "grok_cli",
            "--meta-ai-review",
            str(meta),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert packet["verdict"] == "PASS"
    assert packet["scientific_status"] == "SUBSTRATE_COVERAGE_READY_WITH_META_AI"
    assert packet["meta_ai"]["review_verdict"] == "WARN"


def test_substrate_smoke_runner_fake_worker_outputs_full_coverage(tmp_path):
    tasks = tmp_path / "verified-mini.jsonl"
    tasks.write_text(
        json.dumps(
            {
                "instance_id": "django__django-11790",
                "repo": "django/django",
                "base_commit": "main",
                "problem_statement": "Real SWE-bench shaped task fixture.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"

    proc = subprocess.run(
        [
            "python3",
            str(SUBSTRATE_SMOKE),
            "--tasks-jsonl",
            str(tasks),
            "--out-dir",
            str(out_dir),
            "--worker-mode",
            "fake",
            "--limit",
            "1",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    coverage = json.loads((out_dir / "substrate_coverage.json").read_text(encoding="utf-8"))
    assert coverage["schema_id"] == "MiniSweBenchSubstrateCoverage.v1"
    assert coverage["sample_size"] == 1
    assert coverage["turingos_arm_runs"][0]["instance_id"] == "django__django-11790"

    audit = json.loads((out_dir / "substrate_coverage_audit.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "PASS"
    assert audit["scientific_status"] == "SUBSTRATE_INSTRUMENTATION_ONLY_NOT_REAL_WORKER"
    summary = json.loads((out_dir / "substrate_smoke_result.json").read_text(encoding="utf-8"))
    assert summary["scientific_status"] == "SUBSTRATE_INSTRUMENTATION_ONLY_NOT_REAL_WORKER"


def test_meta_ai_review_missing_key_is_not_run_and_does_not_serialize_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "substrate_coverage_audit.json").write_text(
        json.dumps(
            {
                "schema_id": "MiniSweBenchSubstrateCoverageAudit.v1",
                "verdict": "PASS",
                "scientific_status": "SUBSTRATE_COVERAGE_READY",
                "blocking_findings": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "meta.json"

    proc = subprocess.run(
        [
            "python3",
            str(META_REVIEW),
            "--evidence-dir",
            str(evidence),
            "--out",
            str(out),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 2
    packet = json.loads(out.read_text(encoding="utf-8"))
    assert packet["status"] == "NOT_RUN"
    assert packet["credential_material"] == "env_only_not_serialized"
    assert "DEEPSEEK_API_KEY" in packet["missing_env"]
    assert "sk-" not in out.read_text(encoding="utf-8")


def test_direct_baseline_dry_run_writes_redacted_commands(tmp_path):
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text(
        json.dumps(
            {
                "instance_id": "django__django-11790",
                "repo": "django/django",
                "base_commit": "b1d6b35e146aea83b171c1b921178bbaae2795ed",
                "problem_statement": "Fix the failing regression.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "baseline"

    proc = subprocess.run(
        [
            "python3",
            str(DIRECT_BASELINE),
            "--tasks-jsonl",
            str(tasks),
            "--out-dir",
            str(out_dir),
            "--limit",
            "1",
            "--dry-run",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    summary = json.loads((out_dir / "direct_baseline_summary.json").read_text(encoding="utf-8"))
    assert summary["sample_size"] == 1
    command = json.loads(
        (out_dir / "direct_baseline_django__django-11790" / "command.json").read_text(encoding="utf-8")
    )
    assert "<direct_baseline_prompt>" in command["argv"]
    assert "Fix the failing regression" not in json.dumps(command)


def test_django_fail_to_pass_labels_convert_to_runtests_labels():
    evaluator = load_module(PATCH_EVAL, "evaluate_django_swe_bench_patches")
    labels = evaluator.django_test_labels(
        [
            "test_username_field_max_length_defaults_to_254 (auth_tests.test_forms.AuthenticationFormTest)",
            "already.runnable.Label",
        ]
    )

    assert labels == [
        "auth_tests.test_forms.AuthenticationFormTest.test_username_field_max_length_defaults_to_254",
        "already.runnable.Label",
    ]


def test_gate_a_capsule_prompt_injects_scope_and_broadcast_rules():
    runner = load_module(SUBSTRATE_SMOKE, "run_mini_swe_bench_substrate_smoke")
    task = {
        "instance_id": "django__django-11815",
        "repo": "django/django",
        "base_commit": "abc123",
        "problem_statement": "Fix the migration writer regression.",
    }

    prompt = runner.visible_grok_prompt(
        task,
        "wc_django__django-11815",
        broadcast_rules=[
            {
                "rule_id": "br_scope_test_edit",
                "failure_class": "SCOPE_VIOLATION_TEST_EDIT",
                "guidance": "Do not edit benchmark/official test files unless the task contract explicitly allows test changes.",
            }
        ],
    )

    assert "Do not edit benchmark/official test files" in prompt
    assert "SCOPE_VIOLATION_TEST_EDIT" in prompt
    assert "hidden predicate" not in prompt.lower()
    assert "pput" not in prompt.lower()


def test_gate_a_grant_forbids_swe_bench_test_file_mutations():
    runner = load_module(SUBSTRATE_SMOKE, "run_mini_swe_bench_substrate_smoke")

    grant = runner.grant_json(
        "wc_django__django-11815",
        "mkt_django__django-11815",
        "worker:sha256:" + "1" * 64,
    )

    forbidden = set(grant["scope"]["forbidden_paths"])
    assert "tests/**" in forbidden
    assert "*/tests/**" in forbidden
    assert "test_*.py" in forbidden
    assert "*_test.py" in forbidden


def test_gate_a_evaluator_payload_detects_test_edits_and_is_micro_tape_importable():
    evaluator = load_module(PATCH_EVAL, "evaluate_django_swe_bench_patches")
    task = {
        "instance_id": "django__django-11815",
        "test_patch": "diff --git a/tests/example.py b/tests/example.py\n",
        "FAIL_TO_PASS": ["tests.example.TestCase.test_regression"],
    }
    patch_text = (
        "diff --git a/tests/migrations/test_writer.py b/tests/migrations/test_writer.py\n"
        "--- a/tests/migrations/test_writer.py\n"
        "+++ b/tests/migrations/test_writer.py\n"
        "@@\n"
        "-old\n"
        "+new\n"
    )

    payload = evaluator.official_evaluator_evidence_payload(
        task=task,
        arm="turingos",
        candidate_patch_text=patch_text,
        apply_candidate_result={"status": "PASS", "exit_code": 0, "stdout": "", "stderr": ""},
        apply_test_patch_result={"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "conflict"},
        target_test_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
        capsule_id="wc_django__django-11815",
        macro_anchor_id="macro:diff:django__django-11815",
        worker_receipt_id="rcp_pack",
    )

    assert payload["schema_id"] == "official_evaluator_evidence_imported.v1"
    assert payload["event_type"] == "OfficialEvaluatorEvidenceImported"
    assert payload["evidence_id"].startswith("ev_official_")
    assert payload["instance_id"] == "django__django-11815"
    assert payload["capsule_id"] == "wc_django__django-11815"
    assert payload["macro_anchor_id"] == "macro:diff:django__django-11815"
    assert payload["worker_receipt_id"] == "rcp_pack"
    assert payload["candidate_patch_hash"] == "sha256:" + hashlib.sha256(patch_text.encode()).hexdigest()
    assert payload["test_patch_hash"].startswith("sha256:")
    assert payload["result"] == "FAIL"
    assert payload["failure_class"] == "SCOPE_VIOLATION_TEST_EDIT"
    assert payload["forbidden_test_edit_detected"] is True
    assert payload["forbidden_test_edit_paths"] == ["tests/migrations/test_writer.py"]
    assert payload["truth_source"] == "official_evaluator_macro_evidence"


def test_gate_a_evaluator_builds_candidate_payload_from_evidence_and_substrate_refs():
    evaluator = load_module(PATCH_EVAL, "evaluate_django_swe_bench_patches")
    substrate_run = {
        "instance_id": "django__django-11790",
        "capsule_id": "wc_django__django-11790",
        "macro_anchor_id": "macro:diff:django__django-11790",
        "worker_receipt_id": "rcp_abc",
    }
    evidence_payload = {
        "evidence_id": "ev_official_deadbeef",
        "result": "PASS",
    }

    candidate_payload = evaluator.candidate_payload_from_official_evidence(
        substrate_run,
        evidence_payload,
    )

    assert candidate_payload == {
        "candidate_id": "cand_django__django-11790",
        "capsule_id": "wc_django__django-11790",
        "macro_anchor_id": "macro:diff:django__django-11790",
        "worker_receipt_id": "rcp_abc",
        "official_evaluator_evidence_id": "ev_official_deadbeef",
    }


def test_gate_a_failure_evidence_reduces_to_abstract_broadcast_rule():
    evaluator = load_module(PATCH_EVAL, "evaluate_django_swe_bench_patches")
    evidence_payload = {
        "evidence_id": "ev_official_scope",
        "instance_id": "django__django-11815",
        "failure_class": "SCOPE_VIOLATION_TEST_EDIT",
        "stderr_hash": "sha256:" + "a" * 64,
        "stdout_hash": "sha256:" + "b" * 64,
    }

    rule = evaluator.broadcast_rule_from_evidence(evidence_payload)

    assert rule == {
        "rule_id": "br_ev_official_scope",
        "source_evidence_id": "ev_official_scope",
        "source_instance_id": "django__django-11815",
        "failure_class": "SCOPE_VIOLATION_TEST_EDIT",
        "guidance": "Do not edit benchmark/official test files unless the task contract explicitly allows test changes.",
    }
    assert "stderr" not in json.dumps(rule).lower()
    assert "stdout" not in json.dumps(rule).lower()


def test_gate_a_worker_stop_contract_distinguishes_nonzero_patch_pass():
    runner = load_module(SUBSTRATE_SMOKE, "run_mini_swe_bench_substrate_smoke")

    assert (
        runner.classify_worker_stop(
            exit_code=1,
            stderr="Max turns reached",
            diff_text="diff --git a/django/forms.py b/django/forms.py\n",
            official_eval_result="PASS",
        )
        == "PATCH_PASS_WITH_WORKER_NONZERO"
    )
    assert (
        runner.classify_worker_stop(
            exit_code=1,
            stderr="Max turns reached",
            diff_text="diff --git a/django/forms.py b/django/forms.py\n",
            official_eval_result="FAIL",
        )
        == "MAX_TURNS_WITH_PATCH"
    )
    assert (
        runner.classify_worker_stop(
            exit_code=0,
            stderr="",
            diff_text="",
            official_eval_result="FAIL",
        )
        == "MAX_TURNS_NO_PATCH"
    )


def test_gate_a_pput_prompt_validation_uses_actual_visible_prompt_bytes(tmp_path):
    runner = load_module(SUBSTRATE_SMOKE, "run_mini_swe_bench_substrate_smoke")
    log_dir = tmp_path / "worker_logs"
    log_dir.mkdir()
    prompt = "visible capsule without hidden scoring formula\n"
    (log_dir / "visible_prompt.txt").write_text(prompt, encoding="utf-8")

    request = runner.pput_prompt_validation_request(log_dir)

    assert request["prompt"] == prompt
    assert request["prompt_hash"] == "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
    assert request["source"] == "actual_visible_prompt_txt"


def test_gate_a_micro_import_socket_path_stays_below_unix_limit(tmp_path):
    evaluator = load_module(PATCH_EVAL, "evaluate_django_swe_bench_patches")
    long_runtime_root = tmp_path / ("deep_" + "x" * 140)

    socket_path = evaluator.micro_import_socket_path(
        long_runtime_root,
        "django__django-11885",
    )

    assert str(socket_path).startswith("/tmp/")
    assert len(str(socket_path)) < 100
