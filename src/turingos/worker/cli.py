"""turingos.worker.cli — CliWorkerAdapter: real subscription Worker CLIs behind the seam (ADR-0008).

One generic adapter drives any headless one-shot agent CLI (claude / codex / agy / grok); per-worker argv
builders encode the best-practice invocation (ADR-0008). The candidate is produced inside an ISOLATED Macro
worktree; the adapter introspects that worktree (git) to build an adapter-agnostic turingos.receipt.v1
(tree_oid anchor + files_touched). The Predicate re-checks everything — the worker self-report is never the gate.

Stdlib only. Reuses the process-group reaper from .adapter (PG-REAP — no orphan on timeout).
"""
from __future__ import annotations

import os
import subprocess

from .. import codec
from .. import dispatch_router
from .adapter import WorkerAdapter, _pgid_alive, _reap_group


def build_prompt(capsule: dict) -> str:
    """Compose the Worker prompt from the Shielded Work Capsule (scope + shield rules + declared tests).

    The capsule's gate/scoring logic is NOT in the capsule (Art. III.4); only the abstract injected rules
    (shield) are surfaced to the Worker. The acceptance_commands are stated as the bar the change must clear
    (the Predicate re-runs them — P6).
    """
    allowed = capsule.get("allowed_files", [])
    rules = capsule.get("injected_rules", [])
    accept = capsule.get("acceptance_commands", [])
    lines = [
        f"You are a TuringOS Worker executing atom '{capsule.get('atom_id', '')}'.",
        f"Goal: {capsule.get('intent', 'complete the atom as specified')}.",
        "",
        "STRICT SCOPE — create/edit ONLY these files (relative to the current directory); touch nothing else:",
        *[f"  - {f}" for f in allowed],
        "",
        "Your change MUST make ALL of these commands exit 0 (they will be independently re-run):",
        *[f"  $ {c}" for c in accept],
    ]
    if rules:
        lines += ["", "Apply these abstract lessons from prior failures:",
                  *[f"  - {r.get('rule', '')}" for r in rules]]
    lines += ["", "Work ONLY inside the current directory. Do not run git. When finished, stop."]
    return "\n".join(lines)


def _argv_claude(prompt, wt, extra=()):
    return ["claude", "-p", prompt, "--dangerously-skip-permissions", *extra]


def _argv_codex(prompt, wt, extra=()):
    return ["codex", "exec", prompt, "-C", wt, "--skip-git-repo-check", "-s", "workspace-write", *extra]


def _argv_agy(prompt, wt, extra=()):
    return ["agy", "-p", prompt, "--dangerously-skip-permissions", "--add-dir", wt, *extra]


def _argv_grok(prompt, wt, extra=()):
    return ["grok", "-p", prompt, "--cwd", wt, "--always-approve", "--output-format", "plain", *extra]


ARGV_BUILDERS = {
    "claude": _argv_claude,
    "codex": _argv_codex,
    "agy": _argv_agy,
    "grok": _argv_grok,
}


def _git(wt, *args, check=True):
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "turingos-worker", "GIT_AUTHOR_EMAIL": "worker@turingos.local",
           "GIT_COMMITTER_NAME": "turingos-worker", "GIT_COMMITTER_EMAIL": "worker@turingos.local"}
    r = subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {r.returncode}: {r.stderr}")
    return r


class CliWorkerAdapter(WorkerAdapter):
    """Drives a headless one-shot agent CLI inside an isolated Macro worktree (ADR-0008).

    worker_id selects the built-in argv builder (claude/codex/agy/grok); a custom argv_builder(prompt, wt)
    can be supplied (used by tests with a stub CLI). The worktree is made a git repo so the candidate's
    tree_oid (P7 anchor) and files_touched (P3 scope) can be derived; the candidate is committed so
    HEAD^{tree} == the reported tree_oid.
    """

    def __init__(self, worker_id: str, argv_builder=None, *, tier=None):
        self.worker_id = worker_id
        self._argv = argv_builder or ARGV_BUILDERS[worker_id]
        self._tier_override = tier   # None -> the smart router decides per capsule (fast by default)

    def _ensure_git(self, wt: str) -> None:
        if not os.path.isdir(os.path.join(wt, ".git")):
            _git(wt, "init", "-q")
            _git(wt, "config", "user.name", "turingos-worker")
            _git(wt, "config", "user.email", "worker@turingos.local")
            _git(wt, "config", "commit.gpgsign", "false")
            # Local-only excludes (NOT a tracked file) so build noise a worker may generate while
            # self-verifying (e.g. running python) never pollutes files_touched / trips the scope check.
            try:
                with open(os.path.join(wt, ".git", "info", "exclude"), "a") as fh:
                    fh.write("\n__pycache__/\n*.pyc\n.pytest_cache/\n.DS_Store\nnode_modules/\n")
            except OSError:
                pass

    def _spawn_reap(self, argv, wt: str, timeout_s: int):
        """Run argv in its OWN process group; reap the whole group on timeout (PG-REAP)."""
        proc = subprocess.Popen(argv, cwd=wt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True, text=True,
                                env={**os.environ})
        pgid = os.getpgid(proc.pid)
        try:
            out, _ = proc.communicate(timeout=timeout_s)
            rc = proc.returncode
            if _pgid_alive(pgid) is not False:
                try:
                    os.killpg(pgid, 9)
                except (ProcessLookupError, PermissionError):
                    pass
            return ("ok" if rc == 0 else "failed"), True, (out or "")[-400:]
        except subprocess.TimeoutExpired:
            status = _reap_group(proc, pgid)  # "timeout" | "killed"
            for s in (proc.stdout,):
                try:
                    if s is not None:
                        s.close()
                except OSError:
                    pass
            return status, True, "(timeout)"

    def _candidate(self, wt: str):
        """Stage everything, list touched paths, commit, return (tree_oid, files_touched, macro_commit)."""
        _git(wt, "add", "-A")
        names = _git(wt, "diff", "--cached", "--name-only", check=False).stdout.split()
        if not names:
            # nothing changed -> empty candidate (the Predicate will reject it on scope/anchor)
            head = _git(wt, "rev-parse", "HEAD", check=False).stdout.strip()
            tree = _git(wt, "rev-parse", "HEAD^{tree}", check=False).stdout.strip() if head else ""
            return tree, [], head
        _git(wt, "commit", "-q", "-m", "turingos candidate", "--no-gpg-sign")
        commit = _git(wt, "rev-parse", "HEAD").stdout.strip()
        tree = _git(wt, "rev-parse", "HEAD^{tree}").stdout.strip()
        return tree, names, commit

    def run(self, capsule: dict, worktree: str) -> dict:
        os.makedirs(worktree, exist_ok=True)
        self._ensure_git(worktree)
        prompt = build_prompt(capsule)
        timeout_s = int(capsule.get("budget", {}).get("wall_seconds", 300))
        # Smart router: pick model + thinking effort PER TASK (fast by default) instead of the CLI's
        # expensive operator default (e.g. claude opus-4.8 xhigh, codex gpt-5.5 high). ADR-0008.
        tier = self._tier_override or dispatch_router.select_tier(capsule)
        extra = dispatch_router.worker_flags(self.worker_id, tier)
        self.last_tier = tier
        try:
            argv = self._argv(prompt, worktree, extra)
        except TypeError:        # custom argv_builder without the extra-flags param (e.g. test stubs)
            argv = self._argv(prompt, worktree)
        status, no_orphan, _tail = self._spawn_reap(argv, worktree, timeout_s)
        tree_oid, files_touched, macro_commit = self._candidate(worktree)
        return {
            "schema_id": "turingos.receipt.v1",
            "receipt_id": "rcpt:" + codec.content_digest(
                {"capsule_id": capsule.get("capsule_id", ""), "worker_id": self.worker_id,
                 "tree_oid": tree_oid, "status": status})[len("sha256:"):],
            "capsule_id": capsule.get("capsule_id", ""),
            "worker_id": self.worker_id,
            "worktree_path": worktree,
            "candidate": {"tree_oid": tree_oid, "files_touched": files_touched, "macro_commit": macro_commit},
            "declared_test_results": [],
            "status": status,
            "no_orphan": no_orphan,
        }
