"""turingos.worker.fake — FakeWorker, the deterministic Stage-1 worker stub.

Frozen seam (contracts/INTERFACES.md worker/fake.py):

    class FakeWorker(WorkerAdapter):
        def __init__(self, scenario: str = "pass"): ...   # scenario in {pass, fail_test, fail_scope, ...}
        def run(self, capsule, worktree) -> dict          # turingos.receipt.v1 receipt

FakeWorker produces a REAL candidate so the deterministic Predicate exercises its real machinery
(it is NOT trusted — the gate re-runs everything). run():
  1. git init the worktree as a real Macro repo (deterministic identity, --no-gpg-sign);
  2. write files per scenario;
  3. git add + commit;
  4. return a turingos.receipt.v1 receipt whose candidate.tree_oid == `git rev-parse HEAD^{tree}`
     and candidate.files_touched lists exactly the paths written.

Scenarios (all deterministic — same capsule => same tree_oid):
  * "pass"       — writes the capsule.allowed_files with content that makes ALL the
                   capsule.acceptance_commands exit 0 (the file exists, parses as Python, and
                   carries the PASS_MARKER token). files_touched ⊆ allowed_files (P3 OK).
  * "fail_test"  — writes the allowed_files but WITHOUT the PASS_MARKER / with content that makes a
                   declared test exit non-zero. Stays IN scope (the failure is on TESTS, not scope).
  * "fail_scope" — writes the allowed_files AND an extra file OUTSIDE allowed_files; files_touched
                   contains that out-of-scope path (P3 scope_violation).

Stdlib only (json, os, subprocess, pathlib). The Macro worktree repo is a normal git repo,
separate from both the build repo and the SHA-256 Micro Tape.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .. import codec
from .adapter import WorkerAdapter

# A token a "pass" candidate always embeds so a `grep PASS_MARKER`-style acceptance check is green;
# a "fail_test" candidate omits it so that same check goes red.
_PASS_MARKER = "PASS_MARKER"

# A deterministic out-of-scope path the "fail_scope" candidate writes (relative, but NOT in
# allowed_files — a P3 scope violation the predicate must catch).
_OUT_OF_SCOPE_PATH = "OUT_OF_SCOPE/leak.txt"

# Deterministic git identity for the Macro worktree commit (reproducible tree OIDs).
_FAKE_GIT_ENV = {
    "GIT_AUTHOR_NAME": "turingos-fake-worker",
    "GIT_AUTHOR_EMAIL": "fake-worker@turingos.local",
    "GIT_COMMITTER_NAME": "turingos-fake-worker",
    "GIT_COMMITTER_EMAIL": "fake-worker@turingos.local",
    "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000",
}

_KNOWN_SCENARIOS = frozenset({"pass", "fail_test", "fail_scope"})


class FakeWorker(WorkerAdapter):
    """Deterministic in-process worker stub for Stage-1 (worker_id == 'fake')."""

    worker_id = "fake"

    def __init__(self, scenario: str = "pass"):
        if scenario not in _KNOWN_SCENARIOS:
            raise ValueError(
                f"unknown FakeWorker scenario {scenario!r}; "
                f"expected one of {sorted(_KNOWN_SCENARIOS)}"
            )
        self.scenario = scenario

    # --- git plumbing (deterministic) ---------------------------------------
    @staticmethod
    def _git(repo: str, *args: str) -> str:
        env = {**os.environ, **_FAKE_GIT_ENV}
        result = subprocess.run(
            ["git", "-C", repo, *args], capture_output=True, text=True, env=env
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} -> {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout

    # --- candidate content --------------------------------------------------
    def _content_for(self, rel_path: str, *, with_marker: bool) -> str:
        """Deterministic, syntactically-valid-Python content for a candidate file.

        Always valid Python (so `python3 -c 'ast.parse(...)'`-style checks pass) and `test -f`
        succeeds. `with_marker` controls whether the PASS_MARKER token is embedded — this is the
        lever that flips a `grep PASS_MARKER`-style acceptance check between green and red.
        """
        marker_line = f"# {_PASS_MARKER}\n" if with_marker else "# (no marker)\n"
        return (
            "# turingos FakeWorker deterministic candidate\n"
            f"# path: {rel_path}\n"
            f"{marker_line}"
            f"VALUE = {len(rel_path)}\n"
        )

    def _write_file(self, worktree: str, rel_path: str, content: str) -> None:
        dest = Path(worktree) / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    # --- the worker run -----------------------------------------------------
    def run(self, capsule: dict, worktree: str) -> dict:
        """Build a real candidate at `worktree` per scenario; return a turingos.receipt.v1 receipt."""
        wt = str(Path(worktree))
        Path(wt).mkdir(parents=True, exist_ok=True)

        # 1. A REAL git repo at the worktree (the Macro candidate repo).
        self._git(wt, "init")
        self._git(wt, "config", "user.name", _FAKE_GIT_ENV["GIT_AUTHOR_NAME"])
        self._git(wt, "config", "user.email", _FAKE_GIT_ENV["GIT_AUTHOR_EMAIL"])

        allowed = [p for p in capsule.get("allowed_files", []) if isinstance(p, str) and p]
        # Deterministic order regardless of capsule list order.
        allowed = sorted(set(allowed))

        files_touched = []
        with_marker = self.scenario != "fail_test"  # fail_test omits the marker so a test goes red

        # 2. Write the in-scope candidate files.
        for rel in allowed:
            self._write_file(wt, rel, self._content_for(rel, with_marker=with_marker))
            files_touched.append(rel)

        # If the capsule declares no allowed_files, still produce a deterministic in-scope file
        # so a "pass" candidate is a real (non-empty) tree.
        if not allowed and self.scenario != "fail_scope":
            fallback = "CANDIDATE.txt"
            self._write_file(wt, fallback, self._content_for(fallback, with_marker=with_marker))
            files_touched.append(fallback)

        # 3. fail_scope additionally writes a path OUTSIDE allowed_files (P3 violation).
        if self.scenario == "fail_scope":
            self._write_file(
                wt, _OUT_OF_SCOPE_PATH,
                "# out-of-scope leak written by FakeWorker(fail_scope)\n",
            )
            files_touched.append(_OUT_OF_SCOPE_PATH)

        files_touched = sorted(set(files_touched))

        # 4. Commit the candidate (deterministic identity, no gpg).
        self._git(wt, "add", "-A")
        self._git(
            wt, "commit", "--no-gpg-sign", "--allow-empty",
            "-m", f"fake-worker candidate ({self.scenario})",
        )
        tree_oid = self._git(wt, "rev-parse", "HEAD^{tree}").strip()
        macro_commit = self._git(wt, "rev-parse", "HEAD").strip()

        # status: the receipt's self-reported outcome (recorded, NOT trusted — predicate re-runs).
        # FakeWorker always *completed* a candidate, so it self-reports ok; the deterministic
        # predicate is what fails fail_test (P6) / fail_scope (P3).
        status = "ok"

        receipt = {
            "schema_id": "turingos.receipt.v1",
            "receipt_id": self._receipt_id(capsule, tree_oid),
            "capsule_id": capsule.get("capsule_id", ""),
            "worker_id": self.worker_id,
            "worktree_path": wt,
            "candidate": {
                "tree_oid": tree_oid,
                "files_touched": files_touched,
                "macro_commit": macro_commit,
            },
            "declared_test_results": [],
            "status": status,
            "no_orphan": True,
        }
        return receipt

    # --- receipt id ---------------------------------------------------------
    def _receipt_id(self, capsule: dict, tree_oid: str) -> str:
        """Deterministic receipt_id ("rcpt:"+hex) bound to the capsule + candidate tree + scenario."""
        body = {
            "capsule_id": capsule.get("capsule_id", ""),
            "worker_id": self.worker_id,
            "scenario": self.scenario,
            "tree_oid": tree_oid,
        }
        return "rcpt:" + codec.content_digest(body)[len("sha256:"):]
