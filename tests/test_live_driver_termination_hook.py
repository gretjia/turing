"""WP-H3 (ADR-ECON-007 Decision 4; design doc §2 L1.3) -- integration tests for
`tools/econ_lab/live_driver.py`'s WP-H3 hook wiring: when WP-H2's own rollback
remedy is exhausted for a fork point (`RollbackCapExceededError`), the driver now
also produces a `RouteFalsified` PRESERVE event on the tape plus a structured
falsification report under `verdict["monitor_summary"]["route_falsification_reports"]`
(ADR-ECON-007 Decision 4's "放弃的合法产物").

Reuses `test_live_driver_monitor_hook.py`'s own offline fixtures (`tripping_driver`,
`_stub_out_broken_arm_a_worker_chain`, `_always_error_dispatch_worker_for_lineage`)
rather than re-deriving them -- same anchor branch discipline, same
`--monitor-rollback-cap 0` trigger that file's own cap-zero test already uses to
force `RollbackCapExceededError` deterministically on the first task, offline (no
network, no real worker/scoring calls).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_live_driver_monitor_hook as h2_hook  # noqa: E402


def _trippable_config_path(tmp_path: Path) -> Path:
    config_path = tmp_path / "monitor_config_trippable.json"
    config_path.write_text(
        json.dumps(
            {
                "same_fragment_failure_threshold": 1000,
                "action_window_size": 1000,
                "action_window_repeat_threshold": 1000,
                "phase_timeout_steps": 1000,
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_cap_exceeded_produces_route_falsified_event_and_report(tmp_path, monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    h2_hook._stub_out_broken_arm_a_worker_chain(monkeypatch)
    module = h2_hook._load_worktree_driver()
    monkeypatch.setattr(module, "load_task_packets", lambda shard_root=module.SHARD_ROOT: h2_hook._synthetic_packets(3))
    monkeypatch.setattr(
        module,
        "load_provider_config",
        lambda: {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "stub://offline", "model": "stub-model"},
    )
    calls: list = []
    monkeypatch.setattr(module, "dispatch_worker_for_lineage", h2_hook._always_error_dispatch_worker_for_lineage(calls))

    root = tmp_path / "falsified"
    root.mkdir()
    args = argparse.Namespace(
        smoke=False,
        max_tasks=3,
        out=root / "verdict.json",
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=root / "task_runs",
        report_dir=root / "scoring",
        run_label="wp-h3-termination-hook-test",
        monitor=True,
        monitor_config=_trippable_config_path(tmp_path),
        monitor_rollback_cap=0,
    )
    verdict = module.run_driver(args)  # must not raise

    monitor_summary = verdict["monitor_summary"]
    reports = monitor_summary["route_falsification_reports"]
    assert len(reports) >= 1

    report = reports[0]
    assert report["schema"] == module.monitor_termination.ROUTE_FALSIFICATION_REPORT_SCHEMA
    assert report["proposal_only"] is True
    assert report["route_id"]
    assert isinstance(report["attempts"], list) and len(report["attempts"]) >= 1
    assert isinstance(report["verifier_evidence"], list)
    assert isinstance(report["detector_events"], list) and len(report["detector_events"]) >= 1
    assert report["detector_events"][0]["rule_id"] == module.monitor_loop_detector.RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE
    assert report["remaining_candidates"] == []
    assert isinstance(report["recommendation"], str) and report["recommendation"]

    # Decision 3 blacklist, exercised end-to-end through the real hook.
    module.monitor_termination.assert_report_has_no_bzone_leak(report)

    route_falsified_events = [e for e in monitor_summary["tape"] if e["event_type"] == "RouteFalsified"]
    assert len(route_falsified_events) >= 1
    assert route_falsified_events[0]["head_effect"] == "PRESERVE"
    assert route_falsified_events[0]["report_digest"] == report["digest"]

    assert verdict["task_count"] == 3


def test_monitor_absent_still_has_no_route_falsification_key(tmp_path, monkeypatch):
    """Parity guard: this WP's addition never appears at all when `--monitor` is
    unused -- same additive-only discipline WP-H2's own `monitor_summary` gate uses."""
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    h2_hook._stub_out_broken_arm_a_worker_chain(monkeypatch)
    module = h2_hook._load_worktree_driver()
    h2_hook.wire_stubs(module, monkeypatch, task_count=2)

    root = tmp_path / "no-monitor"
    root.mkdir()
    verdict = h2_hook._run(module, root)
    assert "monitor_summary" not in verdict


def test_monitor_enabled_never_trips_route_falsification_reports_stays_empty(tmp_path, monkeypatch):
    """Success-path parity: when nothing ever trips (WP-H2's own never-trip fixture
    config), `route_falsification_reports` is present (additive) but empty -- the
    WP-H3 hook never fires spuriously and never perturbs a successful run."""
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    h2_hook._stub_out_broken_arm_a_worker_chain(monkeypatch)
    module = h2_hook._load_worktree_driver()
    h2_hook.wire_stubs(module, monkeypatch, task_count=2)

    root = tmp_path / "never-trips"
    root.mkdir()
    verdict = h2_hook._run(
        module,
        root,
        extra_args={"monitor": True, "monitor_config": h2_hook._high_thresholds_config_path(tmp_path)},
    )
    monitor_summary = verdict["monitor_summary"]
    assert monitor_summary["route_falsification_reports"] == []
    assert not any(e["event_type"] == "RouteFalsified" for e in monitor_summary["tape"])
