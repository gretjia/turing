"""WP-L3-3 acceptance tests: `tools/econ_lab/closed_loop/closed_loop_driver.py`.

Fully offline, no network/API call anywhere in this file (this WP's own brief: "mock
全链离线重放对拍") -- every dialectic-panel role and every iterate-harness worker call
below is a fully scripted, deterministic stand-in. The one exception -- an
`audit_loop_until_pass.py` PASS check against a bundle this closed loop actually
produces -- runs the real, unmodified `tools/bench/audit_loop_until_pass.py`, the same
way `tests/test_econ_lab_iterate_harness.py` already does for WP-L3-1's own bundles.

`econ_fold_cli` IS invoked (real subprocess, `--offline-mock`-shaped, WP-H4's own
`fold_and_select_route`) -- deterministic and network-free, same posture
`tests/test_depthk_driver.py` already uses; skipped (never failed) when the binary is
not built.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ECON_LAB = REPO_ROOT / "tools" / "econ_lab"
BENCH = REPO_ROOT / "tools" / "bench"

sys.path.insert(0, str(ECON_LAB))
sys.path.insert(0, str(ECON_LAB / "closed_loop"))
sys.path.insert(0, str(ECON_LAB / "iterate"))
sys.path.insert(0, str(BENCH))

import closed_loop.closed_loop_driver as cld  # noqa: E402
import iterate.iterate_harness as ih  # noqa: E402

CLI_CANDIDATES = [
    REPO_ROOT / "target" / "debug" / "econ_fold_cli",
    REPO_ROOT / "target" / "release" / "econ_fold_cli",
]


def _cli_bin() -> Path:
    for c in CLI_CANDIDATES:
        if c.exists():
            return c
    pytest.skip("econ_fold_cli not built")


def load_module(name: str, path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_offline_mock_full_chain_is_deterministic(tmp_path: Path) -> None:
    cli = _cli_bin()
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    verdict1 = cld.run_closed_loop_offline_mock(out_dir=out1, cli_bin=cli)
    verdict2 = cld.run_closed_loop_offline_mock(out_dir=out2, cli_bin=cli)
    assert json.dumps(verdict1, sort_keys=True) == json.dumps(verdict2, sort_keys=True)


def test_offline_mock_full_chain_shape(tmp_path: Path) -> None:
    """Every one of this WP's own five hard requirements, exercised on the fully
    offline, deterministic mock chain (the real-network variant of the same
    assertions lives in this WP's own real-drill report, not in this test file)."""
    cli = _cli_bin()
    out = tmp_path / "run"
    verdict = cld.run_closed_loop_offline_mock(out_dir=out, cli_bin=cli)

    # (1) route1 escalates -> a falsification report with non-empty remaining_candidates.
    assert verdict["route1_outcome"] == "ESCALATED"
    report = verdict["falsification_report"]
    assert report["remaining_candidates"]
    assert report["proposal_only"] is True

    # (2) the loop detector organically trips (rule 1, same-fragment-repeated-failure)
    # on this run's own event stream -- not a fixture replay.
    assert verdict["route1_detector_trips"]
    assert verdict["route1_detector_trips"][0]["rule_id"] == "SAME_FRAGMENT_REPEATED_FAILURE"

    # (3) the re-entry dialectic pass produced a revised portfolio, landed on disk.
    assert verdict["pass2_portfolio_digest"] is not None
    assert (out / "pass2_reentry" / "portfolio.json").exists()
    revised_portfolio = json.loads((out / "pass2_reentry" / "portfolio.json").read_text())
    assert revised_portfolio["reentry"]["upstream_route_id"] == verdict["route1_label"]
    assert revised_portfolio["reentry"]["upstream_remaining_candidates"] == report["remaining_candidates"]

    # (4) terminal state carries real (scripted-but-verifier-shaped) evidence.
    assert verdict["route2_outcome"] == "CONVERGED"

    # (5) organic iterate-attempt count is recorded (Decision 6 sunset-clause counter).
    assert verdict["organic_iterate_attempts_total"] == 4  # route1: 2 + route2: 2

    # Real-call budget was spent (dialectic pass1 x4 + route1 x2 + dialectic pass2 x4 + route2 x2 = 12).
    assert verdict["call_budget"]["used"] == 12
    assert verdict["call_budget"]["used"] <= 15


def test_route1_is_the_deliberately_retained_weak_route(tmp_path: Path) -> None:
    cli = _cli_bin()
    verdict = cld.run_closed_loop_offline_mock(out_dir=tmp_path / "run", cli_bin=cli)
    assert verdict["route1_label"] == "weak-capsule-only"
    assert verdict["route2_label"] != verdict["route1_label"]


def test_audit_loop_until_pass_passes_on_route2_bundle(tmp_path: Path) -> None:
    cli = _cli_bin()
    out = tmp_path / "run"
    cld.run_closed_loop_offline_mock(out_dir=out, cli_bin=cli)
    route2_run = json.loads((out / "route2_run.json").read_text())
    coverage = ih.build_coverage([route2_run])
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")

    auditor = load_module("_closed_loop_test_audit_loop_until_pass", BENCH / "audit_loop_until_pass.py")
    result = auditor.audit_coverage(coverage_path)
    assert result["status"] == "PASS", result
    assert result["problems"] == []


def test_route_worker_context_parses_controlled_vocabulary() -> None:
    capsule_only = {
        "route_descriptor": {
            "label": "x",
            "summary": "no hints here",
            "key_choices": ["worker_context: capsule_only", "something else"],
        }
    }
    source_loop = {
        "route_descriptor": {
            "label": "y",
            "summary": "no hints here",
            "key_choices": ["worker_context: source_context_loop"],
        }
    }
    ambiguous = {"route_descriptor": {"label": "z", "summary": "no token here", "key_choices": ["nothing relevant"]}}
    assert cld.route_worker_context(capsule_only) == cld.WORKER_CONTEXT_CAPSULE_ONLY
    assert cld.route_worker_context(source_loop) == cld.WORKER_CONTEXT_SOURCE_LOOP
    assert cld.route_worker_context(ambiguous) == cld.WORKER_CONTEXT_CAPSULE_ONLY  # documented fallback


def test_call_budget_raises_before_exceeding_max() -> None:
    budget = cld.CallBudget(max_calls=2)
    budget.spend("a")
    budget.spend("b")
    with pytest.raises(cld.CallBudgetExceeded):
        budget.spend("c")
    assert budget.used == 2


def test_budgeted_llm_client_counts_every_completion() -> None:
    from dialectic.llm_clients import MockLLMClient

    inner = MockLLMClient(responses={"role_a": "resp_a", "role_b": "resp_b"})
    budget = cld.CallBudget(max_calls=1)
    client = cld.BudgetedLLMClient(inner=inner, budget=budget, label_prefix="test")
    assert client.complete(role="role_a", system="s", user="u") == "resp_a"
    with pytest.raises(cld.CallBudgetExceeded):
        client.complete(role="role_b", system="s", user="u")
    # the budget-exceeded call never reached the inner mock client.
    assert len(inner.calls) == 1


def test_derive_route_keys_for_portfolio_gives_each_candidate_a_distinct_scaffold(tmp_path: Path) -> None:
    """Regression test for the real duplicate-market_id bug this WP's own drill hit
    and fixed: two candidates that share the same worker_context bucket (and would
    therefore share a `scaffold_id` if the candidate's own label were not folded into
    `toolchain`) must still get distinct scaffold ids."""
    cli = _cli_bin()
    candidates = [
        {
            "route_descriptor": {
                "label": "route-a",
                "summary": "s",
                "key_choices": ["worker_context: source_context_loop"],
            }
        },
        {
            "route_descriptor": {
                "label": "route-b",
                "summary": "s",
                "key_choices": ["worker_context: source_context_loop"],
            }
        },
    ]
    _domain_bucket, route_keys = cld.derive_route_keys_for_portfolio(
        cli, task_family="example/example", candidates=candidates
    )
    assert route_keys["route-a"]["route_scaffold"] != route_keys["route-b"]["route_scaffold"]
