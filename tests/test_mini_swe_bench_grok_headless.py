import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tools" / "bench" / "mini_swe_bench_grok_headless.py"
AUDITOR = REPO / "tools" / "bench" / "audit_mini_swe_bench_plan.py"
SMOKE = REPO / "tools" / "bench" / "smoke_mini_swe_bench_grok_headless.sh"


def load_harness():
    spec = importlib.util.spec_from_file_location("mini_swe_bench_grok_headless", HARNESS)
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
