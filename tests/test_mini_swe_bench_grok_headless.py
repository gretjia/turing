import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tools" / "bench" / "mini_swe_bench_grok_headless.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("mini_swe_bench_grok_headless", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_grok_headless_argv_turns_planning_and_reasoning_down():
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
    assert ["--output-format", "json"] in [argv[i : i + 2] for i in range(len(argv) - 1)]
    assert ["--reasoning-effort", "low"] in [argv[i : i + 2] for i in range(len(argv) - 1)]
    assert ["--effort", "low"] in [argv[i : i + 2] for i in range(len(argv) - 1)]
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
    assert packet["thinking_contract"] == "grok_reasoning_effort_low_no_plan_no_memory_no_subagents"
    assert packet["truth_guard"]["accepted_head_policy"] == "predicate_only"
    assert packet["truth_guard"]["forbidden_acceptance_signals"] == [
        "exit_code_0",
        "ci_green",
        "grok_self_report",
        "official_benchmark_result",
    ]
    assert [run["mode"] for run in packet["runs"]] == ["direct_grok_baseline", "turingos_grok_worker"]
    for run in packet["runs"]:
        argv = run["grok_command"]["argv"]
        assert ["--reasoning-effort", "low"] in [argv[i : i + 2] for i in range(len(argv) - 1)]
        assert "--no-plan" in argv
        assert run["task"]["instance_id"] == "django__django-00001"
