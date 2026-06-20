#!/usr/bin/env python3
"""S-5 — GitHub PR/CI MacroAdapter happy-path on a DISPOSABLE repo (credentialed, live).

Closes the Phase-0 BLOCKED forge arm: open a PR, observe a CI check run, import the PR head tree OID as a
MacroObservationImported Tape event, MERGE ONLY after a recorded human-confirm event (operator standing
authorization), then delete the throwaway repo. Operator native `gh` login only — no credential bundling.
    PYTHONPATH=src python3 evidence/stage2/s5_github.py
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from turingos.tape import Tape
from turingos import boot, macro, explore

CI_YML = """name: ci
on: pull_request
jobs:
  ok:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""

def git(wt, *a, check=True):
    env = {**os.environ, "GIT_AUTHOR_NAME": "turingos", "GIT_AUTHOR_EMAIL": "tape@turingos.local",
           "GIT_COMMITTER_NAME": "turingos", "GIT_COMMITTER_EMAIL": "tape@turingos.local"}
    r = subprocess.run(["git", "-C", wt, *a], capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(a)} -> {r.returncode}: {r.stderr}")
    return r

def main() -> int:
    base = tempfile.mkdtemp(prefix="tos_s5_")
    wt = os.path.join(base, "macro"); os.makedirs(wt)
    res = {"steps": {}}
    repo = None
    try:
        login = macro.gh_login(); res["login"] = login
        name = "turingos-s5-" + os.urandom(4).hex()
        repo = macro.create_repo(name); res["repo"] = repo
        res["steps"]["repo_created"] = True

        # base branch (main) with a CI workflow so the PR triggers a check run
        git(wt, "init", "-q"); git(wt, "checkout", "-q", "-b", "main")
        os.makedirs(os.path.join(wt, ".github", "workflows"), exist_ok=True)
        open(os.path.join(wt, "README.md"), "w").write("# turingos s5 disposable\n")
        open(os.path.join(wt, ".github/workflows/ci.yml"), "w").write(CI_YML)
        git(wt, "add", "-A"); git(wt, "commit", "-q", "-m", "base + ci", "--no-gpg-sign")
        macro.push_branch(wt, repo, "main"); res["steps"]["base_pushed"] = True

        # candidate branch (the Macro candidate)
        branch = "turingos/atom-1"
        git(wt, "checkout", "-q", "-b", branch)
        open(os.path.join(wt, "greet.py"), "w").write("def greet():\n    return 'hello, turingos'\n")
        git(wt, "add", "-A"); git(wt, "commit", "-q", "-m", "candidate atom-1", "--no-gpg-sign")
        macro.push_branch(wt, repo, branch); res["steps"]["candidate_pushed"] = True
        tree_oid = git(wt, "rev-parse", f"{branch}^{{tree}}").stdout.strip()
        res["tree_oid"] = tree_oid

        pr = macro.open_pr(repo, head=branch, base="main",
                           title="atom-1: add greet()", body="TuringOS S-5 disposable PR")
        res["pr"] = pr; res["steps"]["pr_opened"] = True

        # observe CI (poll without hanging; python sleep is fine inside this script)
        ci = {"state": "none", "checks": []}
        for _ in range(24):  # up to ~120s
            ci = macro.observe_ci(repo, pr, watch=False)
            if ci["state"] in ("success", "failure") and ci.get("checks"):
                break
            time.sleep(5)
        res["ci"] = ci; res["steps"]["ci_observed"] = bool(ci.get("checks")) or ci["state"] != "none"

        # Tape: boot, import the Macro anchor, record the human-confirm, then merge
        tape = Tape.init(os.path.join(base, "tape"), "W1")
        boot.boot(tape, {"project_id": "s5", "writer_id": "W1"})
        obs_ev = macro.import_pr_observation(tape, repo, pr, tree_oid, ci)
        res["macro_observation_event"] = obs_ev
        # the imported observation records the PR head tree OID (the anchor)
        recorded = tape.read_event(obs_ev)["payload"].get("tree_oid")
        res["steps"]["anchor_recorded"] = (recorded == tree_oid)

        human_confirm = explore.inject_human_steer(tape, {
            "kind": "merge_authorization", "repo": repo, "pr": pr,
            "authorized_by": "operator standing authorization 2026-06-20"})
        res["human_confirm_event"] = human_confirm

        # refusal check: merge WITHOUT a confirm must raise (merge=human-confirmed)
        refused = False
        try:
            macro.merge(repo, pr, human_confirm_event_id="")
        except macro.MacroError:
            refused = True
        res["steps"]["merge_refused_without_confirm"] = refused

        merge_res = macro.merge(repo, pr, human_confirm_event_id=human_confirm)
        res["merge"] = merge_res
        res["steps"]["merged_after_confirm"] = merge_res.get("merged", False)

        passed = all([
            res["steps"].get("pr_opened"),
            res["steps"].get("ci_observed"),
            res["steps"].get("anchor_recorded"),
            res["steps"].get("merge_refused_without_confirm"),
            res["steps"].get("merged_after_confirm"),
        ])
        res["S5_PASS"] = passed
        return 0 if passed else 1
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {e}"
        res["S5_PASS"] = False
        return 1
    finally:
        if repo:
            res["delete"] = macro.delete_repo(repo)  # needs delete_repo scope; honest if missing
        print(json.dumps(res, indent=2))
        shutil.rmtree(base, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
