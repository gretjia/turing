"""WP9c -- hard constraint B: fresh-run (non `--resume`) byte-parity gate.

Stage A is running against `hci/software3-20260705`'s HEAD driver (89d78e1 + the two commits
after it) while this WP9c resume work lands in a separate worktree/branch. The orchestrator's
own precondition for allowing that in-flight run to later merge this branch is: with
`--resume` unused, the new driver's verdict output must be byte-identical to the HEAD driver's,
given the same fixed inputs -- i.e. this file's own resume-checkpoint additions
(`_write_settlement_checkpoint` et al.) must be pure side effects that never touch a byte of
`verdict.json`. If this test fails, WP9c is BLOCKED from merging, full stop -- no formula is
invented here to make it pass; a genuine divergence is a real regression.

Spec source: this file's own task brief (WP9c orchestrator instructions, 2026-07-07, hard
constraint B) -- not an ADR/PREREG formula; this test only proves two Python module objects
(one loaded from `git show HEAD:tools/econ_lab/live_driver.py`, one this worktree's working
copy) produce byte-identical JSON given byte-identical mock/offline stubs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER_PATH = REPO / "tools" / "econ_lab" / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"
ECON_LAB_DIR = REPO / "tools" / "econ_lab"

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


def _head_commit_ref() -> str:
    """The commit whose driver Stage A's already-running processes actually loaded --
    *not* literally `HEAD`. This test's own branch (`wp9c/resume`) accumulates its own
    commits (this file's own WP9c work), so plain `HEAD` drifts forward with every commit
    made here and would eventually make this test compare the new driver against itself.
    The stable anchor is this branch's fork point from `hci/software3-20260705` (the branch
    Stage A is running against) -- `git merge-base HEAD hci/software3-20260705` -- which
    stays pinned to the exact pre-WP9c commit regardless of how many commits either branch
    gains afterwards, as long as this branch never merges hci/software3-20260705's later
    commits back into itself."""
    return subprocess.run(
        ["git", "merge-base", "HEAD", "hci/software3-20260705"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
    ).stdout.strip()


def _load_head_driver():
    """Loads `tools/econ_lab/live_driver.py` exactly as committed at the pinned pre-WP9c
    anchor commit (see `_head_commit_ref`), not this worktree's (modified) working copy --
    the "old driver" side of the parity check. Written to a throwaway file *inside*
    `tools/econ_lab/` (not `tmp_path`) so the loaded module's own
    `REPO_ROOT = Path(__file__).resolve().parents[2]` still resolves to this repo's actual
    root (the module derives every repo-relative path from its own file location at import
    time); the temp file is removed immediately after `exec_module` whether or not the
    import succeeds.

    B1 anchor guard (ADR-ECON-003 Decision 4 remedy, INDEPENDENT_AUDIT_ECON_LAB_20260707.md
    B1; owner decision: conform the kernel to the pin): the B1 fix adds the pinned
    `trigger_event_hash` seed input to the routing seed, the `econ_fold_cli`
    fold-and-suggest request (schema v1 -> v2), and this driver's own request builder.
    Routing selections therefore *legitimately* differ from any pre-B1 anchor driver -- and
    a pre-B1 anchor driver cannot even talk to the post-B1 CLI binary (its v1 request is
    rejected by schema version). Byte-parity against a pre-B1 anchor is thus expected to
    fail and is NOT evidence of a regression, so this fixture skips (never deletes/weakens
    the assertions) when the anchor predates B1.

    TODO(B1 re-anchor): once the commit that lands B1 is on `hci/software3-20260705`, the
    `git merge-base HEAD hci/software3-20260705` anchor advances past B1 on its own for any
    branch forked afterwards, the marker below is found in the anchored source, and the
    byte-parity assertions resume automatically -- no code change needed here. If a branch
    forked *before* B1 ever needs this parity gate against a post-B1 driver, its owner must
    first merge (or rebase onto) the B1 landing commit so the fork point moves past it; the
    corresponding Stage A comparison window also needs the PREREG-amendment trail the audit
    doc's B1 entry requires (owner-level, not this test's call)."""
    head_ref = _head_commit_ref()
    head_source = subprocess.run(
        ["git", "show", f"{head_ref}:tools/econ_lab/live_driver.py"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
    ).stdout
    if "trigger_event_hash" not in head_source:
        pytest.skip(
            "head-parity anchor commit "
            f"{head_ref[:12]} predates the B1 seed fix (ADR-ECON-003 D4 trigger_event_hash); "
            "byte-parity against it is expected to break and proves nothing about the new "
            "driver -- re-run once the B1 landing commit is the merge-base anchor "
            "(see _load_head_driver's TODO(B1 re-anchor))"
        )
    snapshot_path = ECON_LAB_DIR / f"_wp9c_head_snapshot_{uuid.uuid4().hex}.py"
    return _load_module_from_source(
        source_text=head_source, module_path=snapshot_path, module_name="wp9c_head_driver_under_test"
    )


def _load_worktree_driver():
    spec = importlib.util.spec_from_file_location("wp9c_worktree_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run_fresh(module, run_root: Path, *, max_tasks: int = 2) -> dict:
    # `run_root` must be a *separate* directory per driver invocation with an *identical*
    # relative substructure underneath (`task_runs/`, `scoring/`, `verdict.json`) -- not a
    # shared tmp_path with a per-driver tag suffix -- because `scoring_result.report_path`/
    # `log_path` embed the absolute `--report-dir` path verbatim (real driver behavior, not a
    # test artifact); a tag-suffixed directory name (e.g. `scoring_head` vs `scoring_new`)
    # would show up as a spurious byte diff that has nothing to do with the two drivers'
    # actual logic.
    out_path = run_root / "verdict.json"
    args = argparse.Namespace(
        smoke=False,
        max_tasks=max_tasks,
        out=out_path,
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=run_root / "task_runs",
        report_dir=run_root / "scoring",
        # Deliberately *not* setting `.tau`/`.resume` here: the HEAD driver snapshot predates
        # WP9c's `--resume` flag entirely, so both drivers must be exercised through the
        # common subset of `argparse.Namespace` attributes that already existed at HEAD.
        # `run_driver` on the worktree side reads both via `getattr(args, ..., default)`.
    )
    return module.run_driver(args)


def _normalize_run_root_paths(verdict: dict, *, run_root: Path) -> dict:
    """Strips the one legitimate source of absolute-path divergence between two otherwise
    byte-identical runs: `--report-dir`'s own absolute location, embedded verbatim in
    `scoring_result.report_path`/`log_path`. Both drivers are given a `run_root` with
    identical internal relative structure (see `_run_fresh`), so replacing each run's own
    `run_root` prefix with a fixed placeholder makes the two outputs directly comparable
    without masking any real divergence elsewhere."""
    text = json.dumps(verdict, sort_keys=True)
    text = text.replace(str(run_root.resolve()), "<RUN_ROOT>")
    return json.loads(text)


@pytest.fixture()
def head_driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_head_driver()
    wire_stubs(module, monkeypatch, task_count=2)
    return module


@pytest.fixture()
def worktree_driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_worktree_driver()
    wire_stubs(module, monkeypatch, task_count=2)
    return module


def test_fresh_run_byte_identical_to_head_driver(tmp_path, head_driver, worktree_driver):
    """Hard constraint B, smoke=False (`full`/Stage-A-shaped) mode."""
    head_root = tmp_path / "head_run"
    new_root = tmp_path / "new_run"
    head_root.mkdir()
    new_root.mkdir()
    verdict_head = _run_fresh(head_driver, head_root)
    verdict_new = _run_fresh(worktree_driver, new_root)

    stripped_head = _normalize_run_root_paths(strip_volatile(verdict_head), run_root=head_root)
    stripped_new = _normalize_run_root_paths(strip_volatile(verdict_new), run_root=new_root)
    assert stripped_head == stripped_new, "fresh-run verdict dict diverged from the HEAD driver"

    # "逐字节" is the orchestrator's literal requirement -- also compare the exact serialized
    # bytes each driver's own `main()` writes to `--out` (indent=2, sort_keys=True, trailing
    # newline), not just Python dict equality.
    head_bytes = (json.dumps(stripped_head, indent=2, sort_keys=True) + "\n").encode("utf-8")
    new_bytes = (json.dumps(stripped_new, indent=2, sort_keys=True) + "\n").encode("utf-8")
    assert head_bytes == new_bytes


def test_fresh_smoke_mode_byte_identical_to_head_driver(tmp_path, head_driver, worktree_driver):
    """Hard constraint B, `--smoke` mode (the other invocation shape `run_driver` supports)."""

    def _run_smoke(module, run_root: Path) -> dict:
        args = argparse.Namespace(
            smoke=True,
            max_tasks=None,
            out=run_root / "verdict.json",
            econ_fold_cli=CLI_BIN,
            scoring_python="python3",
            scoring_timeout_s=60,
            task_dir_root=run_root / "task_runs",
            report_dir=run_root / "scoring",
        )
        return module.run_driver(args)

    head_root = tmp_path / "head_run_smoke"
    new_root = tmp_path / "new_run_smoke"
    head_root.mkdir()
    new_root.mkdir()
    verdict_head = _normalize_run_root_paths(strip_volatile(_run_smoke(head_driver, head_root)), run_root=head_root)
    verdict_new = _normalize_run_root_paths(strip_volatile(_run_smoke(worktree_driver, new_root)), run_root=new_root)
    assert verdict_head == verdict_new
