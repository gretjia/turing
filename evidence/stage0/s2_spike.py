#!/usr/bin/env python3
"""S-2 PRE spike — one active sovereign writer + explicit handoff (no multi-writer).

Loop seam: the writer-authority guard around every Append.
Proves: only the current writer's FF append admits; wrong-writer / non-FF rejected by the GUARD (not by
convention); a HandoffGenerated Tape event changes who the guard treats as writer; NO epoch/lease/fencing
needed. PASS iff all criteria hold (App E S-2). Exit 0 only on full PASS.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "/tmp/turingos_s2"

def jcs(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
def content_digest(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(jcs(payload)).hexdigest()

HEAD_EFFECT = {"SystemBootstrapped": "ADVANCE", "HandoffGenerated": "PRESERVE", "CandidateAccepted": "ADVANCE"}

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "turingos", "GIT_AUTHOR_EMAIL": "tape@turingos.local",
       "GIT_COMMITTER_NAME": "turingos", "GIT_COMMITTER_EMAIL": "tape@turingos.local",
       "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000", "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000"}

def git(*args, check=True):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, env=ENV)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {r.returncode}\n{r.stderr}")
    return r

class GuardReject(Exception):
    pass

def current_writer() -> str:
    """Guard reads the current sovereign writer from the latest boot/HandoffGenerated event on the Tape."""
    log = git("rev-list", "refs/turingos/tape_tip").stdout.split()  # newest first
    for oid in log:
        node = json.loads(git("cat-file", "-p", f"{oid}:node.json").stdout)
        if node["event_type"] == "SystemBootstrapped":
            return node["payload"]["writer_id"]
        if node["event_type"] == "HandoffGenerated":
            return node["payload"]["to_writer"]
    raise RuntimeError("no writer-establishing event")

def guarded_append(event_type: str, payload: dict, *, writer_id: str, force_parent: str | None = None):
    """Local authority guard: FF-only + single-writer identity. Rejects (raises) BEFORE any commit."""
    tip = git("rev-parse", "refs/turingos/tape_tip", check=False).stdout.strip()
    tip = tip if len(tip) > 10 else None
    # GUARD CHECK A: single-writer identity (skip for the bootstrap event that establishes W1)
    if event_type != "SystemBootstrapped":
        cw = current_writer()
        if writer_id != cw:
            raise GuardReject(f"wrong_writer: {writer_id} != current {cw}")
    # GUARD CHECK B: FF-only (parent must == current tape_tip)
    parent = force_parent if force_parent is not None else tip
    if tip is not None and parent != tip:
        raise GuardReject(f"non_ff: parent {parent} != tip {tip}")
    # admitted -> write the commit
    envelope = {"prev_tape_tip": tip or "", "event_schema_id": event_type,
                "payload_hash": content_digest(payload), "head_effect": HEAD_EFFECT[event_type],
                "accepted_head_before": git("rev-parse", "refs/turingos/accepted_head", check=False).stdout.strip(),
                "writer_id": writer_id, "authority_epoch": 0}
    node = {"event_type": event_type, "payload": payload, "envelope": envelope}
    (Path(REPO) / "node.json").write_text(json.dumps(node, indent=2))
    git("add", "node.json")
    git("commit", "-m", f"{event_type} by {writer_id}", "--no-gpg-sign")
    new_tip = git("rev-parse", "HEAD").stdout.strip()
    git("update-ref", "refs/turingos/tape_tip", new_tip)
    if HEAD_EFFECT[event_type] == "ADVANCE":
        git("update-ref", "refs/turingos/accepted_head", new_tip)
    return new_tip

def expect_reject(label, fn):
    try:
        fn()
        return (label, False, "ADMITTED (should have rejected)")
    except GuardReject as e:
        return (label, True, str(e))

def main() -> int:
    shutil.rmtree(REPO, ignore_errors=True)
    subprocess.run(["git", "init", "--object-format=sha256", REPO], capture_output=True, env=ENV, check=True)
    git("config", "receive.denyNonFastForwards", "true")
    results = {}

    # current writer = W1 (from boot event)
    guarded_append("SystemBootstrapped", {"kind": "boot", "writer_id": "W1"}, writer_id="W1")
    tip0 = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()

    # 1. append as W1 (FF, correct parent) -> admitted, tape_tip advances
    guarded_append("CandidateAccepted", {"kind": "work", "n": 1}, writer_id="W1")
    tip1 = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()
    results["w1_ff_admitted"] = (tip1 != tip0)

    # 2. append as W2 (NOT current writer) -> rejected by guard
    lbl, ok, msg = expect_reject("w2_wrong_writer_rejected",
                                 lambda: guarded_append("CandidateAccepted", {"kind": "work", "n": 2}, writer_id="W2"))
    results[lbl] = ok; results[lbl + "_msg"] = msg

    # 3. append as W1 with stale parent (non-FF) -> rejected
    stale = tip0  # parent points at an old tip
    lbl, ok, msg = expect_reject("w1_non_ff_rejected",
                                 lambda: guarded_append("CandidateAccepted", {"kind": "work", "n": 3},
                                                        writer_id="W1", force_parent=stale))
    results[lbl] = ok; results[lbl + "_msg"] = msg

    # 4. emit HandoffGenerated: W1 -> W2 (recorded on Tape, tape_tip advances)
    tip_before_handoff = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()
    guarded_append("HandoffGenerated", {"kind": "handoff", "from_writer": "W1", "to_writer": "W2"}, writer_id="W1")
    tip_after_handoff = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()
    results["handoff_recorded"] = (tip_after_handoff != tip_before_handoff)
    results["handoff_changed_writer"] = (current_writer() == "W2")

    # 5. append as W2 (now current writer, FF) -> admitted
    guarded_append("CandidateAccepted", {"kind": "work", "n": 4}, writer_id="W2")
    tip_after_w2 = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()
    results["w2_admitted_after_handoff"] = (tip_after_w2 != tip_after_handoff)

    # 6. append as W1 (no longer current writer) -> rejected
    lbl, ok, msg = expect_reject("w1_rejected_after_handoff",
                                 lambda: guarded_append("CandidateAccepted", {"kind": "work", "n": 5}, writer_id="W1"))
    results[lbl] = ok; results[lbl + "_msg"] = msg

    # 7. no epoch/lease/fencing field was required for any of the above
    results["no_epoch_lease_fencing_required"] = True  # authority_epoch present but pinned to 0, never enforced

    crit = [k for k in results if isinstance(results[k], bool)]
    all_pass = all(results[k] for k in crit)
    results["SPIKE"] = "S-2"
    results["ALL_PASS"] = all_pass
    print(json.dumps(results, indent=2))
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
