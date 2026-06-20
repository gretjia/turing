"""turingos.macro — GitHub PR/CI MacroAdapter (plan M9, F-9) via the `gh` CLI.

Macro is NEVER directly sovereign: PR/CI state is imported as a `MacroObservationImported` Tape event (the
PR head tree OID is the anchor the Predicate P7 binds). The merge to the base branch is a HUMAN-CONFIRMED
sovereign act — `merge()` refuses unless a human-confirm Tape event id is supplied (the operator's standing
authorization is recorded as a HumanSteerInjected merge-authorization). Auto-integration (QB-5) is 1.x.

Operator native `gh` login only — no credential bundling/retention. Stdlib only.
"""
from __future__ import annotations

import json
import os
import subprocess

from . import evidence


class MacroError(RuntimeError):
    pass


def _gh(*args, check=True, cwd=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, cwd=cwd, env={**os.environ})
    if check and r.returncode != 0:
        raise MacroError(f"gh {' '.join(args)} -> {r.returncode}: {r.stderr.strip()}")
    return r


def _git(wt, *args, check=True):
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "turingos", "GIT_AUTHOR_EMAIL": "tape@turingos.local",
           "GIT_COMMITTER_NAME": "turingos", "GIT_COMMITTER_EMAIL": "tape@turingos.local"}
    r = subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise MacroError(f"git {' '.join(args)} -> {r.returncode}: {r.stderr.strip()}")
    return r


def gh_login() -> str:
    """Return the authenticated GitHub login (proves native auth; no token is read/stored)."""
    return _gh("api", "user", "--jq", ".login").stdout.strip()


def create_repo(name: str, *, private: bool = True) -> str:
    """Create a disposable repo under the authed user; return 'owner/name'."""
    login = gh_login()
    vis = "--private" if private else "--public"
    _gh("repo", "create", f"{login}/{name}", vis)
    return f"{login}/{name}"


def setup_git_auth() -> None:
    """Configure git to use gh's credential helper (idempotent)."""
    _gh("auth", "setup-git", check=False)


def push_branch(worktree: str, repo_full: str, branch: str, *, set_default_base: bool = False) -> None:
    """Push the worktree's HEAD to <branch> on the remote repo over gh-authenticated https."""
    setup_git_auth()
    url = f"https://github.com/{repo_full}.git"
    if _git(worktree, "remote", check=False).stdout.find("origin") < 0:
        _git(worktree, "remote", "add", "origin", url)
    else:
        _git(worktree, "remote", "set-url", "origin", url)
    _git(worktree, "push", "-u", "origin", f"HEAD:refs/heads/{branch}")


def open_pr(repo_full: str, head: str, base: str, title: str, body: str) -> int:
    """Open a PR head->base; return the PR number."""
    r = _gh("pr", "create", "--repo", repo_full, "--head", head, "--base", base,
            "--title", title, "--body", body)
    # gh prints the PR URL; the number is the trailing path segment.
    url = r.stdout.strip().splitlines()[-1]
    return int(url.rstrip("/").split("/")[-1])


def observe_ci(repo_full: str, pr: int, *, watch: bool = True) -> dict:
    """Observe the PR's CI check-run state. Returns {state, checks:[...]} (state 'none' if no checks)."""
    args = ["pr", "checks", str(pr), "--repo", repo_full]
    if watch:
        args.append("--watch")
    r = _gh(*args, check=False)
    out = r.stdout.strip()
    if not out:
        return {"state": "none", "checks": [], "raw": r.stderr.strip()[:200]}
    # gh pr checks exits 0 if all pass, 8 if pending, nonzero on failure; rows are TSV.
    checks = [line.split("\t") for line in out.splitlines() if line.strip()]
    state = "success" if r.returncode == 0 else ("pending" if r.returncode == 8 else "failure")
    return {"state": state, "checks": checks, "rc": r.returncode}


def pr_head_commit(repo_full: str, pr: int) -> str:
    r = _gh("pr", "view", str(pr), "--repo", repo_full, "--json", "headRefOid")
    return json.loads(r.stdout)["headRefOid"]


def import_pr_observation(tape, repo_full: str, pr: int, tree_oid: str, ci: dict) -> str:
    """Record the Macro anchor (PR head tree OID) + CI state as MacroObservationImported on the Tape."""
    obs = {
        "macro": "github",
        "repo": repo_full,
        "pr": pr,
        "tree_oid": tree_oid,            # the anchor P7 binds against (ANCHOR_BINDS_HASH)
        "ci_state": ci.get("state", "none"),
        "head_commit": pr_head_commit(repo_full, pr),
    }
    return evidence.import_macro_observation(tape, obs)


def merge(repo_full: str, pr: int, *, human_confirm_event_id: str, admin: bool = True) -> dict:
    """Merge the PR — ONLY with a recorded human-confirm Tape event id (merge=human-confirmed).

    Absent `human_confirm_event_id` the adapter REFUSES (returns without merging). This is the
    constitutional gate: the Macro merge is a human-confirmed sovereign act, never automatic.
    """
    if not human_confirm_event_id:
        raise MacroError("merge refused: no recorded human-confirm event (merge=human-confirmed)")
    args = ["pr", "merge", str(pr), "--repo", repo_full, "--merge"]
    if admin:
        args.append("--admin")
    r = _gh(*args, check=False)
    return {"merged": r.returncode == 0, "rc": r.returncode,
            "human_confirm_event_id": human_confirm_event_id, "detail": (r.stdout or r.stderr).strip()[:200]}


def delete_repo(repo_full: str) -> dict:
    """Dispose of the disposable repo. Prefer delete (needs the 'delete_repo' token scope); if that scope is
    missing (HTTP 403), self-heal by ARCHIVING the repo (needs only admin) so it is inert. Honest either way."""
    r = _gh("repo", "delete", repo_full, "--yes", check=False)
    if r.returncode == 0:
        return {"deleted": True, "disposed": "deleted", "rc": 0}
    # Fallback: delete_repo scope absent -> archive so the throwaway repo is disposed/inert.
    a = _gh("repo", "archive", repo_full, "--yes", check=False)
    return {"deleted": False, "disposed": "archived" if a.returncode == 0 else "left",
            "rc": r.returncode, "archive_rc": a.returncode,
            "detail": (r.stderr or r.stdout).strip()[:160],
            "note": "full delete needs: gh auth refresh -h github.com -s delete_repo"}
