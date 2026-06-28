import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def stage15_tasks():
    return [
        {
            "instance_id": "stage15_market_router_multi_route",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": "Exercise multi-route market router without truth authority.",
        }
    ]


def generate_stage15_fixture(tmp_path, **kwargs):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    out_dir = tmp_path / "stage15"
    manifest = runner.generate_stage15_multi_agent_market_router_fixture(out_dir, stage15_tasks(), **kwargs)
    return out_dir, manifest


def replay_stage15_events(market, coverage: Path, tmp_path: Path):
    auditor = market.load_micro_tape_auditor()
    with tempfile.TemporaryDirectory(dir=tmp_path) as temp:
        return market.fetch_events(json.loads(coverage.read_text()), auditor, Path(temp))


def test_stage15_market_router_fixture_strict_and_stage_audit_pass(tmp_path):
    tape = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    market = load_module("market", REPO / "tools" / "bench" / "audit_market_router.py")
    out_dir, manifest = generate_stage15_fixture(tmp_path)

    bundles = [Path(run["micro_tape_bundle"]) for run in manifest["turingos_arm_runs"]]
    strict = tape.audit_bundles(
        bundles,
        tmp_path / "strict_work",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    report = market.audit_coverage(out_dir / "turingos" / "substrate_coverage.json")

    assert strict["verdict"] == "PASS"
    assert strict["status_summary"]["authorization_head"] == "PASS"
    assert report["status"] == "PASS"
    assert report["market_router"]["status"] == "PASS"
    assert report["route_diversity"]["status"] == "PASS"
    assert report["agent_reputation"]["status"] == "PASS"
    assert report["price_not_truth"]["status"] == "PASS"
    assert report["branch_cost_conservation"]["status"] == "PASS"
    assert report["route_types_count"] >= 2
    assert report["market_moved_accepted_head"] is False


def test_stage15_audit_fails_when_single_route_collapses(tmp_path):
    market = load_module("market", REPO / "tools" / "bench" / "audit_market_router.py")
    out_dir, _ = generate_stage15_fixture(tmp_path)
    coverage = out_dir / "turingos" / "substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["market_router"]["route_diversity_policy"]["min_route_types_per_batch"] = 3
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = market.audit_coverage(coverage)

    assert report["status"] == "FAIL"
    assert any("route diversity floor not met" in problem for problem in report["problems"])


def test_stage15_audit_ignores_manifest_reputation_metadata(tmp_path):
    market = load_module("market", REPO / "tools" / "bench" / "audit_market_router.py")
    out_dir, _ = generate_stage15_fixture(tmp_path)
    coverage = out_dir / "turingos/substrate_coverage.json"
    data = json.loads(coverage.read_text())
    data["market_router"]["reputation_updates"][0]["basis_kind"] = "progress_pput"
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = market.audit_coverage(coverage)

    assert report["status"] == "PASS"
    assert report["truth_source"] == "micro_tape_bundles_replayed_events"


def test_stage15_audit_fails_when_tape_reward_uses_progress_basis(tmp_path):
    market = load_module("market", REPO / "tools" / "bench" / "audit_market_router.py")
    out_dir, _ = generate_stage15_fixture(tmp_path)
    coverage = out_dir / "turingos/substrate_coverage.json"
    data = json.loads(coverage.read_text())
    events = replay_stage15_events(market, coverage, tmp_path)
    for event in events:
        if event.get("event_type") == "RewardDistributed":
            event["payload"]["reason"] = "PROGRESS_PPUT_REWARD"
            break

    report = market.audit_market_router_evidence(data, events)

    assert report["status"] == "FAIL"
    assert any("reputation must consume terminal VPPUT only" in problem for problem in report["problems"])


def test_stage15_audit_fails_when_terminal_market_order_is_mutated(tmp_path):
    market = load_module("market", REPO / "tools" / "bench" / "audit_market_router.py")
    out_dir, _ = generate_stage15_fixture(tmp_path)
    coverage = out_dir / "turingos/substrate_coverage.json"
    data = json.loads(coverage.read_text())
    events = replay_stage15_events(market, coverage, tmp_path)
    terminal_accept = next(event for event in events if event.get("event_type") == "CandidateAccepted")
    settlement = next(event for event in events if event.get("event_type") == "MarketSettled")
    settlement["sequence"] = terminal_accept["sequence"]

    report = market.audit_market_router_evidence(data, events)

    assert report["status"] == "FAIL"
    assert any("MarketSettled must occur after terminal accept/failure event" in problem for problem in report["problems"])


def test_stage15_cli_generates_release_evidence(tmp_path):
    out_dir = tmp_path / "stage15_cli"
    tasks = tmp_path / "tasks.jsonl"
    tasks.write_text("\n".join(json.dumps(task) for task in stage15_tasks()) + "\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            "tools/bench/run_mini_swe_bench_substrate_smoke.py",
            "--multi-agent-market-router",
            "--authorization-mode",
            "required",
            "--tasks-jsonl",
            str(tasks),
            "--limit",
            "1",
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )

    assert (out_dir / "market_router_audit.json").exists()
    assert (out_dir / "route_diversity_audit.json").exists()
    assert (out_dir / "agent_reputation_audit.json").exists()
    assert (out_dir / "price_not_truth_audit.json").exists()
    assert (out_dir / "branch_cost_conservation_audit.json").exists()
