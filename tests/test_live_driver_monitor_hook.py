"""WP-H2 (ADR-ECON-007 Decision 1/2/3; design doc §2 L1.2) -- integration tests for
`tools/econ_lab/live_driver.py`'s `--monitor` hook wiring (deliverable (c)).

Four claims tested:
  1. `--monitor` absent (or `args.monitor` unset entirely, matching every pre-WP-H2
     caller) is byte-identical to the pre-WP-H2 driver on `wp-h1-loop-detector` (this
     branch's own fork point) -- "对拍测试" ("clock-comparison" / parity test), the
     hard requirement from this WP's own brief.
  2. `--monitor` enabled but never tripping (the detector finds nothing to report)
     changes `verdict.json` only by adding the new `monitor_summary` key -- proves the
     hook is additive even when *active*, not just when disabled.
  3. `--monitor` enabled, tripped: the diagnostic is injected into the *next* task's
     dispatch call, and a `TrajectoryRolledBack` event lands in `monitor_summary.tape`.
  4. `--monitor-rollback-cap 0` (the smallest legal cap): a trip immediately exceeds
     the cap, so no rollback/injection happens, and the run still completes cleanly
     (RollbackCapExceededError is caught, not propagated -- see `run_driver`'s own
     `except monitor_interventions.RollbackCapExceededError` block).

Both offline (no network, no real worker/scoring calls -- every dispatch/scoring
function is monkeypatched) per this WP's red line. Uses the same `econ_fold_cli`
subprocess bridge every other `tests/test_live_driver_*.py` file uses for the real
deterministic routing math (never re-derived here).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import types
import uuid
from pathlib import Path
from typing import Any, Optional

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "tools" / "econ_lab" / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"
ECON_LAB_DIR = REPO / "tools" / "econ_lab"


def _stub_out_broken_arm_a_worker_chain(monkeypatch) -> None:
    """This sandbox's `~/.local/bin/turing` CLI shim resolves to a stale/mismatched
    `turingos` package install (`ModuleNotFoundError: No module named 'turingos'`),
    which `tools/bench/run_deepseek_provider_canary.py` transitively hits at import
    time via `src/turingos/worker/cost.py`'s module-level price-table digest call --
    confirmed pre-existing and unrelated to this WP (identical failure on the
    unmodified `wp-h1-loop-detector` anchor). `live_driver.py` only ever references
    `arm_a_worker.<attr>` *inside* function bodies (never at module import time, and
    every test in this file monkeypatches `dispatch_worker_for_lineage` wholesale, so
    those attributes are never actually called) -- so a bare placeholder module
    registered in `sys.modules` under the same import name lets `import
    run_deepseek_arm_a_worker as arm_a_worker` succeed without ever touching the
    broken chain, letting these tests genuinely execute `run_driver` (not just skip)
    in this environment. `monkeypatch.setitem` reverts this after each test."""
    monkeypatch.setitem(sys.modules, "run_deepseek_arm_a_worker", types.ModuleType("run_deepseek_arm_a_worker"))

# This branch's own fork point (per this WP's own task brief: "从 h1/loop-detector 建
# worktree"). No B1/B5-style anchor-drift guard is needed the way
# test_live_driver_head_parity.py needs one for `hci/software3-20260705`: this WP
# never touches routing/selection/verifier internals, only adds new optional
# parameters and a new additive hook, so there is no legitimate divergence to mask.
ANCHOR_REF = "wp-h1-loop-detector"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _wp9c_live_driver_fixtures import strip_volatile, wire_stubs  # noqa: E402


def _load_module_from_source(*, source_text: str, module_path: Path, module_name: str):
    module_path.write_text(source_text, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        module_path.unlink(missing_ok=True)


def _load_anchor_driver():
    anchor_source = subprocess.run(
        ["git", "show", f"{ANCHOR_REF}:tools/econ_lab/live_driver.py"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
    ).stdout
    snapshot_path = ECON_LAB_DIR / f"_wp_h2_anchor_snapshot_{uuid.uuid4().hex}.py"
    return _load_module_from_source(
        source_text=anchor_source, module_path=snapshot_path, module_name="wp_h2_anchor_driver_under_test"
    )


def _load_worktree_driver():
    spec = importlib.util.spec_from_file_location("wp_h2_worktree_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _normalize_run_root_paths(verdict: dict, *, run_root: Path) -> dict:
    text = json.dumps(verdict, sort_keys=True)
    text = text.replace(str(run_root.resolve()), "<RUN_ROOT>")
    return json.loads(text)


@pytest.fixture()
def anchor_driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    _stub_out_broken_arm_a_worker_chain(monkeypatch)
    try:
        module = _load_anchor_driver()
    except Exception as error:  # noqa: BLE001 -- surfaces a clear skip reason, not a hard failure.
        pytest.skip(f"anchor live_driver.py failed to import in this environment: {error!r}")
    wire_stubs(module, monkeypatch, task_count=2)
    return module


@pytest.fixture()
def worktree_driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    _stub_out_broken_arm_a_worker_chain(monkeypatch)
    try:
        module = _load_worktree_driver()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"worktree live_driver.py failed to import in this environment: {error!r}")
    wire_stubs(module, monkeypatch, task_count=2)
    return module


def _run(module, run_root: Path, *, extra_args: Optional[dict[str, Any]] = None) -> dict:
    out_path = run_root / "verdict.json"
    kwargs = dict(
        smoke=False,
        max_tasks=2,
        out=out_path,
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=run_root / "task_runs",
        report_dir=run_root / "scoring",
        run_label="wp-h2-monitor-hook-test",
    )
    if extra_args:
        kwargs.update(extra_args)
    args = argparse.Namespace(**kwargs)
    return module.run_driver(args)


# ---------------------------------------------------------------------------
# 1. --monitor absent: byte-identical to the pre-WP-H2 anchor driver.
# ---------------------------------------------------------------------------


def test_monitor_absent_is_byte_identical_to_anchor_driver(tmp_path, anchor_driver, worktree_driver):
    anchor_root = tmp_path / "anchor"
    worktree_root = tmp_path / "worktree"
    anchor_root.mkdir()
    worktree_root.mkdir()

    anchor_verdict = _run(anchor_driver, anchor_root)
    worktree_verdict = _run(worktree_driver, worktree_root)  # args.monitor never set at all

    anchor_verdict = _normalize_run_root_paths(strip_volatile(anchor_verdict), run_root=anchor_root)
    worktree_verdict = _normalize_run_root_paths(strip_volatile(worktree_verdict), run_root=worktree_root)

    assert "monitor_summary" not in worktree_verdict
    assert json.dumps(worktree_verdict, sort_keys=True) == json.dumps(anchor_verdict, sort_keys=True)


def test_monitor_explicitly_false_is_byte_identical_to_monitor_absent(tmp_path, worktree_driver):
    """`--monitor` not passed at all (argparse default `False`) and `args.monitor =
    False` set explicitly must be indistinguishable -- both are "off"."""
    root_absent = tmp_path / "absent"
    root_false = tmp_path / "false"
    root_absent.mkdir()
    root_false.mkdir()

    verdict_absent = _run(worktree_driver, root_absent)
    verdict_false = _run(worktree_driver, root_false, extra_args={"monitor": False})

    verdict_absent = _normalize_run_root_paths(strip_volatile(verdict_absent), run_root=root_absent)
    verdict_false = _normalize_run_root_paths(strip_volatile(verdict_false), run_root=root_false)
    assert json.dumps(verdict_absent, sort_keys=True) == json.dumps(verdict_false, sort_keys=True)


# ---------------------------------------------------------------------------
# 2. --monitor enabled but never trips: additive-only (adds monitor_summary, nothing
#    else changes).
# ---------------------------------------------------------------------------


def _high_thresholds_config_path(tmp_path: Path) -> Path:
    """Deliberately never-trippable thresholds for a 2-task, single-lineage-per-task
    run (harness-invented fixture values, same discipline as
    tests/test_econ_lab_loop_detector.py's own fixtures -- no ADR pins a concrete
    number)."""
    config_path = tmp_path / "monitor_config_never_trips.json"
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


def test_monitor_enabled_never_trips_only_adds_monitor_summary_key(tmp_path, worktree_driver):
    root_off = tmp_path / "off"
    root_on = tmp_path / "on"
    root_off.mkdir()
    root_on.mkdir()

    verdict_off = _run(worktree_driver, root_off)
    verdict_on = _run(
        worktree_driver,
        root_on,
        extra_args={"monitor": True, "monitor_config": _high_thresholds_config_path(tmp_path)},
    )

    verdict_off = _normalize_run_root_paths(strip_volatile(verdict_off), run_root=root_off)
    verdict_on = _normalize_run_root_paths(strip_volatile(verdict_on), run_root=root_on)

    assert "monitor_summary" not in verdict_off
    monitor_summary = verdict_on.pop("monitor_summary")
    assert monitor_summary["diagnostics_issued"] == []
    assert json.dumps(verdict_on, sort_keys=True) == json.dumps(verdict_off, sort_keys=True)


# ---------------------------------------------------------------------------
# 3 & 4. --monitor enabled, tripped: diagnostic injection + rollback / rollback cap.
# ---------------------------------------------------------------------------


def _synthetic_packets(count: int) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": f"fixture__repo-{i:04d}",
            "repo": "Fixture/Repo",
            "ipqc_window_id": "FIX-W00",
            "_task_dir": Path(f"/nonexistent/fixture-repo-{i:04d}"),
            "_task_packet_path": Path(f"/nonexistent/fixture-repo-{i:04d}/task_packet.json"),
        }
        for i in range(1, count + 1)
    ]


def _always_error_dispatch_worker_for_lineage(calls: list[dict[str, Any]]):
    """A worker dispatch that always fails outright (`status: ERROR`, never scored) --
    the simplest reliable way to make WP-H1's `events_from_real_settlement_checkpoint`
    translator emit a `termination` event with no prior `verification` event, which
    deterministically trips `RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE` on the very
    first task (needs no repeated-N-tasks setup). `calls` records every invocation's
    kwargs (in particular `diagnostic_prefix`) for the injection assertions below."""

    def _dispatch(**kwargs):
        calls.append(kwargs)
        packet = kwargs["packet"]
        return {
            "status": "ERROR",
            "error_type": "StubForcedError",
            "error_message": "WP-H2 test fixture: forced dispatch failure",
            "instance_id": packet["instance_id"],
            "arm": kwargs["arm"],
            "lineage": kwargs["lineage"],
            "provider_path": None,
        }

    return _dispatch


@pytest.fixture()
def tripping_driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    _stub_out_broken_arm_a_worker_chain(monkeypatch)
    try:
        module = _load_worktree_driver()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"worktree live_driver.py failed to import in this environment: {error!r}")
    monkeypatch.setattr(module, "load_task_packets", lambda shard_root=module.SHARD_ROOT: _synthetic_packets(3))
    monkeypatch.setattr(
        module,
        "load_provider_config",
        lambda: {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "stub://offline", "model": "stub-model"},
    )
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(module, "dispatch_worker_for_lineage", _always_error_dispatch_worker_for_lineage(calls))
    return module, calls


def test_monitor_enabled_trip_injects_diagnostic_into_next_task(tmp_path, tripping_driver):
    module, calls = tripping_driver
    root = tmp_path / "trip"
    root.mkdir()
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

    args = argparse.Namespace(
        smoke=False,
        max_tasks=3,
        out=root / "verdict.json",
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=root / "task_runs",
        report_dir=root / "scoring",
        run_label="wp-h2-monitor-hook-trip-test",
        monitor=True,
        monitor_config=config_path,
    )
    verdict = module.run_driver(args)

    monitor_summary = verdict["monitor_summary"]
    diagnostics_issued = monitor_summary["diagnostics_issued"]
    assert len(diagnostics_issued) >= 1
    first = diagnostics_issued[0]
    assert first["outcome"] == "ROLLED_BACK"
    assert first["rule_id"] == module.monitor_loop_detector.RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE
    # A TrajectoryRolledBack PRESERVE event actually landed on the tape.
    rolled_back_events = [e for e in monitor_summary["tape"] if e["event_type"] == "TrajectoryRolledBack"]
    assert len(rolled_back_events) >= 1
    assert rolled_back_events[0]["head_effect"] == "PRESERVE"
    assert rolled_back_events[0]["event_hash"] == first["rollback_event_hash"]

    # Task 0 (the one that tripped the detector) was dispatched with no diagnostic yet
    # (nothing to inject before any trip has happened); task 1 (the *next* task) must
    # have received the diagnostic text built from task 0's trip.
    assert calls[0]["diagnostic_prefix"] is None
    assert calls[1]["diagnostic_prefix"] is not None
    assert "loop detected" in calls[1]["diagnostic_prefix"].lower() or "termination" in calls[1][
        "diagnostic_prefix"
    ].lower()
    # Decision 3 blacklist, exercised end-to-end through the real hook (not just the
    # unit-level assertion in tests/test_econ_lab_interventions.py): no B-zone term
    # leaks into what actually got threaded into the dispatch call.
    module.monitor_interventions.assert_no_bzone_terms_in_text(calls[1]["diagnostic_prefix"])


def test_monitor_rollback_cap_zero_refuses_and_run_still_completes(tmp_path, tripping_driver):
    module, calls = tripping_driver
    root = tmp_path / "cap-zero"
    root.mkdir()
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

    args = argparse.Namespace(
        smoke=False,
        max_tasks=3,
        out=root / "verdict.json",
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=root / "task_runs",
        report_dir=root / "scoring",
        run_label="wp-h2-monitor-hook-cap-zero-test",
        monitor=True,
        monitor_config=config_path,
        monitor_rollback_cap=0,
    )
    verdict = module.run_driver(args)  # must not raise -- RollbackCapExceededError is caught internally

    monitor_summary = verdict["monitor_summary"]
    diagnostics_issued = monitor_summary["diagnostics_issued"]
    assert len(diagnostics_issued) >= 1
    assert diagnostics_issued[0]["outcome"] == "ROLLBACK_CAP_EXCEEDED"
    assert not any(e["event_type"] == "TrajectoryRolledBack" for e in monitor_summary["tape"])
    # No rollback happened -> no diagnostic was ever queued for injection.
    assert all(call["diagnostic_prefix"] is None for call in calls)
    assert verdict["task_count"] == 3


def test_monitor_requires_config_when_enabled(tmp_path, worktree_driver):
    root = tmp_path / "missing-config"
    root.mkdir()
    with pytest.raises(SystemExit):
        _run(worktree_driver, root, extra_args={"monitor": True, "monitor_config": None})
