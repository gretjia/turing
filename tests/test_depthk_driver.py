"""CAPSULE B offline tests for depth-k layered markets.

Covers:
  - mock-stream deterministic replay
  - stage-key sharing (two scaffolds updating the same stage node)
  - seed domain separation (different stages yield independent selection paths)
  - A-territory zero modification guard (static path check helper)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPTH_DRIVER = REPO_ROOT / "tools" / "econ_lab" / "depthk" / "depth_driver.py"
CLI_CANDIDATES = [
    REPO_ROOT / "target" / "debug" / "econ_fold_cli",
    REPO_ROOT / "target" / "release" / "econ_fold_cli",
]


def _cli_bin() -> Path:
    for c in CLI_CANDIDATES:
        if c.exists():
            return c
    pytest.skip("econ_fold_cli not built")


def test_offline_mock_deterministic_and_shared_nodes(tmp_path: Path) -> None:
    cli = _cli_bin()
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    for out in (out1, out2):
        proc = subprocess.run(
            [
                sys.executable,
                str(DEPTH_DRIVER),
                "--offline-mock",
                "--out",
                str(out),
                "--econ-fold-cli",
                str(cli),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout

    v1 = json.loads((out1 / "verdict.json").read_text(encoding="utf-8"))
    v2 = json.loads((out2 / "verdict.json").read_text(encoding="utf-8"))
    assert v1 == v2, "offline mock must be bit-identical across replays"
    assert v1["worker_calls_used"] == 0
    assert v1["assertions"]["shared_nodes_n_equals_2"] is True
    assert v1["assertions"]["seed_sep_all_stages_present"] is True
    # Credit assignment honesty label present.
    assert v1["credit_assignment"] == "v0_equal_share_not_causal"
    # Each task updates 3 stage nodes.
    for task in v1["tasks"]:
        assert task["events_appended"] == 3
        assert task["dispatch_arm"] == "armB"


def test_stage_seed_domain_separation_via_cli() -> None:
    """Different stage_name under SoftmaxUniform must not crash and must echo stage_name."""
    cli = _cli_bin()
    sys.path.insert(0, str(REPO_ROOT / "tools" / "econ_lab"))
    from depthk import depth_driver as dd  # type: ignore

    bucket, stage_ids = dd.derive_stage_keys(cli, "Sympy/Sympy")
    seen_options = set()
    for stage_name in dd.STAGE_WALK:
        sel = dd.fold_and_select_stage(
            cli,
            stage_name=stage_name,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=[],
            instance_id="seed-test",
            router_mode={"kind": "SoftmaxUniform"},
        )
        assert sel["stage_name"] == stage_name
        assert sel["budget_suggestion"]["route_id"] in dd.STAGE_OPTIONS[stage_name]
        seen_options.add((stage_name, sel["budget_suggestion"]["route_id"]))
    assert len(seen_options) == 3


import pytest as _pytest


@_pytest.mark.skip(
    reason="capsule-scoped guard: enforced parallel-capsule file zones vs base 0ebd7ad; "
    "verified true at orchestrator merge time (merge b91f700), legitimately false after "
    "Capsule A's changes were integrated"
)
def test_a_territory_files_unmodified() -> None:
    """A-territory paths must not appear in the depthk branch diff vs baseline."""
    forbidden_prefixes = (
        "tools/econ_lab/live_driver.py",
        "tools/econ_lab/run_",
        "tools/econ_lab/analysis/",
    )
    proc = subprocess.run(
        ["git", "diff", "0ebd7ad", "--name-only"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    # Also include untracked depthk files only — should not include A territory.
    proc_u = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    for line in proc_u.stdout.splitlines():
        path = line[3:].strip()
        if path:
            changed.append(path)
    offenders = [
        p
        for p in changed
        if any(p == pref or p.startswith(pref) for pref in forbidden_prefixes)
        or p.startswith("tools/econ_lab/analysis/")
        or (
            p.startswith("tools/econ_lab/run_")
            and p.endswith(".sh")
        )
    ]
    assert not offenders, f"A-territory files modified: {offenders}"
