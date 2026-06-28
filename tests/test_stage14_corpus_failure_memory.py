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


def stage14_tasks():
    return [
        {
            "instance_id": f"stage14_context_missing_{index}",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": "Exercise corpus-level failure memory.",
        }
        for index in range(1, 5)
    ]


def generate_stage14_fixture(tmp_path, **kwargs):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    out_dir = tmp_path / "stage14"
    manifest = runner.generate_stage14_corpus_failure_memory_fixture(out_dir, stage14_tasks(), **kwargs)
    return out_dir, manifest


def test_stage14_corpus_memory_fixture_strict_and_stage_audit_pass(tmp_path):
    tape = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    corpus = load_module("corpus", REPO / "tools" / "bench" / "audit_corpus_failure_memory.py")
    out_dir, manifest = generate_stage14_fixture(tmp_path)

    bundles = [Path(run["micro_tape_bundle"]) for run in manifest["turingos_arm_runs"]]
    strict = tape.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    report = corpus.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert report["status"] == "PASS"
    assert report["failure_cluster"]["status"] == "PASS"
    assert report["failure_cluster"]["source_failure_count"] >= 3
    assert report["broadcast_visibility"]["status"] == "PASS"
    assert report["later_capsule_consumed_rule"] is True
    assert report["efficacy"]["causal_claim_allowed"] is False


def test_stage14_audit_fails_when_source_failure_missing(tmp_path):
    corpus = load_module("corpus", REPO / "tools" / "bench" / "audit_corpus_failure_memory.py")
    out_dir, _ = generate_stage14_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["corpus_failure_memory"]["source_failure_nodes"].append("mu:" + "0" * 64)
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = corpus.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert any("source failure node unresolved" in problem for problem in report["problems"])


def test_stage14_forbidden_visible_content_detector():
    corpus = load_module("corpus", REPO / "tools" / "bench" / "audit_corpus_failure_memory.py")

    assert corpus.contains_forbidden_visible_content({"rule": "retry after raw stderr traceback"}) is True
    assert corpus.contains_forbidden_visible_content({"rule": "retry with a smaller scoped context"}) is False


def test_stage14_cli_generates_release_evidence(tmp_path):
    out_dir = tmp_path / "stage14_cli"
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text("\n".join(json.dumps(task) for task in stage14_tasks()) + "\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            "tools/bench/run_mini_swe_bench_substrate_smoke.py",
            "--corpus-failure-memory",
            "--authorization-mode",
            "required",
            "--tasks-jsonl",
            str(tasks),
            "--limit",
            "4",
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )

    assert (out_dir / "failure_cluster_audit.json").exists()
    assert (out_dir / "broadcast_rule_efficacy_audit.json").exists()
    assert (out_dir / "broadcast_rule_visibility_audit.json").exists()
    assert (out_dir / "cross_task_memory_lineage.md").exists()
