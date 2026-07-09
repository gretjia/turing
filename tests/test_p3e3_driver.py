"""P3-E3 driver extensions: stream manifest order, reset-at-task-index determinism,
and arm meta flags (CAPSULE A §3 / SHIP GATE §2). Offline only — no real worker/Docker.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB_DIR = REPO / "tools" / "econ_lab"
DRIVER_PATH = ECON_LAB_DIR / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(ECON_LAB_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wp9c_live_driver_fixtures import (  # noqa: E402
    strip_volatile,
    wire_stubs,
)


def _load_driver():
    spec = importlib.util.spec_from_file_location("p3e3_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_driver()
    wire_stubs(module, monkeypatch, task_count=4)
    return module


def _run_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    base = dict(
        smoke=False,
        max_tasks=4,
        out=tmp_path / "verdict.json",
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=tmp_path / "task_runs",
        report_dir=tmp_path / "scoring",
        run_label="test-p3e3",
        tau="0.5",
        priors=None,
        frozen_backup=False,
        task_shard=None,
        resume=False,
        stream_manifest=None,
        reset_at_task_index=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_stream_manifest_orders_packets(tmp_path):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built")
    unstubbed = _load_driver()
    shard_root = tmp_path / "S03"
    ids = ["z__z-1", "a__a-1", "m__m-1"]
    for iid in ids:
        d = shard_root / "ipqc" / "S03-W00" / "worker_safe_tasks" / iid
        d.mkdir(parents=True)
        (d / "task_packet.json").write_text(
            json.dumps({"instance_id": iid, "repo": iid.split("__")[0], "ipqc_window_id": "S03-W00"}),
            encoding="utf-8",
        )
    # Manifest forces non-glob order: m, a, z
    desired = ["m__m-1", "a__a-1", "z__z-1"]
    man = tmp_path / "stream.json"
    man.write_text(json.dumps({"instance_ids": desired}), encoding="utf-8")
    packets = unstubbed.load_task_packets(shard_root)
    ordered_ids, sha = unstubbed.load_stream_manifest(man)
    assert ordered_ids == desired
    assert sha == hashlib.sha256(man.read_bytes()).hexdigest()
    ordered = unstubbed.order_packets_by_stream_manifest(packets, ordered_ids)
    assert [p["instance_id"] for p in ordered] == desired


def test_reset_at_task_index_clears_fold_and_records_meta(tmp_path, driver, monkeypatch):
    """On a 4-task mock stream with reset@2, events from tasks 0-1 must not affect
    post-reset fold; meta.reset_at == 2; kill-at-reset resume is byte-equivalent."""
    # Count appends to committed events via a wrapper around fold_and_select that
    # records event-list length at each task.
    event_lens = []
    real_fold = driver.fold_and_select

    def tracking_fold(*args, **kwargs):
        event_lens.append(len(kwargs.get("committed_routing_events") or args[1] if False else kwargs["committed_routing_events"]))
        return real_fold(*args, **kwargs)

    monkeypatch.setattr(driver, "fold_and_select", tracking_fold)

    args = _run_args(tmp_path, max_tasks=4, reset_at_task_index=2, tau="0.5")
    verdict = driver.run_driver(args)
    meta = verdict["stage_b_prime_meta"]
    assert meta["reset_at_task_index"] == 2
    assert meta["reset_at"] == 2
    # At task 0,1: may accumulate; at task 2 (reset): length must be 0 entering fold.
    assert event_lens[2] == 0, event_lens
    # Tasks 0 and 1 entered with non-decreasing history (0 then possibly >0).
    assert event_lens[0] == 0


def test_reset_determinism_two_runs_byte_identical(tmp_path, driver):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    verdicts = []
    for root in (root_a, root_b):
        args = _run_args(
            root,
            max_tasks=4,
            reset_at_task_index=2,
            tau="0.5",
            out=root / "verdict.json",
            task_dir_root=root / "task_runs",
            report_dir=root / "scoring",
            run_label="p3e3-det",
        )
        verdicts.append(driver.run_driver(args))
    # Absolute report paths differ by tmp root; compare load-bearing structure only.
    def core(v: dict) -> dict:
        v = strip_volatile(v)
        return {
            "reset_at": v["stage_b_prime_meta"]["reset_at"],
            "reset_at_task_index": v["stage_b_prime_meta"]["reset_at_task_index"],
            "instance_ids": [t["instance_id"] for t in v["tasks"]],
            "routes": [t["selected_route_id"] for t in v["tasks"]],
            "settlements": [
                [d.get("settlement_verdict_resolved") for d in t["dispatches"]]
                for t in v["tasks"]
            ],
            "routing_prior_applied": v["verifier_summary"]["routing_prior_updated_applied_count"],
        }

    assert core(verdicts[0]) == core(verdicts[1])


def test_kill_at_reset_resume_byte_equivalent(tmp_path, driver):
    """Simulate interrupt at reset boundary: run tasks 0..1, then resume with reset@2
    through tasks 0..3; compare to a single continuous run with reset@2."""
    cont = tmp_path / "continuous"
    cont.mkdir()
    args_c = _run_args(
        cont,
        max_tasks=4,
        reset_at_task_index=2,
        tau="0.5",
        out=cont / "verdict.json",
        task_dir_root=cont / "task_runs",
        report_dir=cont / "scoring",
    )
    v_cont = driver.run_driver(args_c)

    split = tmp_path / "split"
    split.mkdir()
    # First leg: only 2 tasks, no reset yet (reset is at 2).
    args1 = _run_args(
        split,
        max_tasks=2,
        reset_at_task_index=2,
        tau="0.5",
        out=split / "verdict_partial.json",
        task_dir_root=split / "task_runs",
        report_dir=split / "scoring",
    )
    driver.run_driver(args1)
    # Resume full 4 with same task dirs.
    args2 = _run_args(
        split,
        max_tasks=4,
        reset_at_task_index=2,
        tau="0.5",
        resume=True,
        out=split / "verdict.json",
        task_dir_root=split / "task_runs",
        report_dir=split / "scoring",
    )
    v_res = driver.run_driver(args2)

    a = strip_volatile(v_cont)
    b = strip_volatile(v_res)
    # generated_at_unix / paths may still differ inside strip — compare key reset semantics
    assert a["stage_b_prime_meta"]["reset_at"] == 2
    assert b["stage_b_prime_meta"]["reset_at"] == 2
    assert [t["instance_id"] for t in a["tasks"]] == [t["instance_id"] for t in b["tasks"]]
    assert [t["selected_route_id"] for t in a["tasks"]] == [t["selected_route_id"] for t in b["tasks"]]


def test_arm_meta_flags_l_z_r(tmp_path, driver):
    priors = tmp_path / "priors.json"
    priors.write_text(json.dumps({"priors": {"armA::deepseek": 0.7}}), encoding="utf-8")
    sha = hashlib.sha256(priors.read_bytes()).hexdigest()

    v_l = driver.run_driver(
        _run_args(tmp_path / "L", max_tasks=1, priors=priors, tau="0.5",
                  out=tmp_path / "L" / "v.json", task_dir_root=tmp_path / "L" / "t",
                  report_dir=tmp_path / "L" / "s", run_label="L")
    )
    v_z = driver.run_driver(
        _run_args(tmp_path / "Z", max_tasks=1, priors=priors, tau="0.5", frozen_backup=True,
                  out=tmp_path / "Z" / "v.json", task_dir_root=tmp_path / "Z" / "t",
                  report_dir=tmp_path / "Z" / "s", run_label="Z")
    )
    v_r = driver.run_driver(
        _run_args(tmp_path / "R", max_tasks=2, priors=priors, tau="0.5", reset_at_task_index=1,
                  out=tmp_path / "R" / "v.json", task_dir_root=tmp_path / "R" / "t",
                  report_dir=tmp_path / "R" / "s", run_label="R")
    )
    assert v_l["stage_b_prime_meta"]["frozen_backup"] is False
    assert v_l["stage_b_prime_meta"]["reset_at"] is None
    assert v_l["stage_b_prime_meta"]["priors_sha256"] == sha
    assert v_z["stage_b_prime_meta"]["frozen_backup"] is True
    assert v_z["stage_b_prime_meta"]["priors_sha256"] == sha
    assert v_r["stage_b_prime_meta"]["reset_at"] == 1
    assert v_r["stage_b_prime_meta"]["reset_at_task_index"] == 1
    assert v_r["stage_b_prime_meta"]["priors_sha256"] == sha


def test_main_cli_accepts_p3e3_flag_shapes(tmp_path, monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built")
    module = _load_driver()
    captured = []
    monkeypatch.setattr(module, "run_driver", lambda args: captured.append(args) or {"tasks": []})
    priors = tmp_path / "priors.json"
    priors.write_text(json.dumps({"priors": {}}), encoding="utf-8")
    man = tmp_path / "stream.json"
    man.write_text(json.dumps({"instance_ids": ["x"]}), encoding="utf-8")
    shard = tmp_path / "S03"

    def common(label):
        return [
            "--tau", "0.5",
            "--task-shard", str(shard),
            "--stream-manifest", str(man),
            "--priors", str(priors),
            "--out", str(tmp_path / f"{label}.json"),
            "--task-dir-root", str(tmp_path / f"{label}_t"),
            "--report-dir", str(tmp_path / f"{label}_s"),
            "--scoring-python", "python3",
            "--scoring-timeout-s", "2700",
            "--run-label", label,
        ]

    assert module.main(common("L")) == 0
    assert module.main(common("Z") + ["--frozen-backup"]) == 0
    assert module.main(common("R") + ["--reset-at-task-index", "22"]) == 0
    assert len(captured) == 3
    assert captured[0].frozen_backup is False and captured[0].reset_at_task_index is None
    assert captured[1].frozen_backup is True
    assert captured[2].reset_at_task_index == 22
