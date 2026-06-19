#!/usr/bin/env python3
"""S-1 PRE spike — SHA-256 Micro Tape: append + 2-ref + failure-is-state + replay.

Loop seam: Append(Failure|Accepted) + the substrate under Read/Reduce.
PRE probe on a scratch repo (NOT shipped code). Proves the seam is mechanically real on this host.
PASS iff all 6 criteria hold (App E S-1). Exit 0 only on full PASS.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "/tmp/turingos_s1"
SHA1_REMOTE = "/tmp/turingos_s1_sha1_remote"
SHA256_REMOTE = "/tmp/turingos_s1_sha256_remote"

# minimal turingos.jcs.v1 (throwaway): ASCII keys, no floats, sorted -> RFC8785 order for ASCII keys
def jcs(payload: dict) -> bytes:
    def _check(o):
        if isinstance(o, float):
            raise ValueError("float_violation")
        if isinstance(o, dict):
            for k, v in o.items():
                if not (isinstance(k, str) and k.isascii()):
                    raise ValueError(f"ascii_key_violation:{k!r}")
                _check(v)
        elif isinstance(o, list):
            for v in o:
                _check(v)
    _check(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

def content_digest(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(jcs(payload)).hexdigest()

# 3-class registry subset for the spike
HEAD_EFFECT = {
    "SystemBootstrapped": "ADVANCE",
    "CandidateAccepted": "ADVANCE",
    "FailureNode": "PRESERVE",
}

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "turingos", "GIT_AUTHOR_EMAIL": "tape@turingos.local",
       "GIT_COMMITTER_NAME": "turingos", "GIT_COMMITTER_EMAIL": "tape@turingos.local",
       "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000", "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000"}

def git(*args, check=True, cwd=REPO):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, env=ENV)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {r.returncode}\n{r.stderr}")
    return r

def append_event(event_type: str, payload: dict, *, writer_id="W1"):
    """One micro commit per event. tape_tip moves always; accepted_head only on ADVANCE+pass."""
    he = HEAD_EFFECT[event_type]
    parent = git("rev-parse", "refs/turingos/tape_tip", check=False).stdout.strip()
    parent = parent if parent and "fatal" not in parent and len(parent) > 10 else None
    accepted_before = git("rev-parse", "refs/turingos/accepted_head", check=False).stdout.strip()
    accepted_before = accepted_before if len(accepted_before) > 10 else ""
    envelope = {
        "prev_tape_tip": parent or "",
        "event_schema_id": event_type,
        "payload_hash": content_digest(payload),
        "head_effect": he,                       # registry-derived
        "accepted_head_before": accepted_before,
        "writer_id": writer_id,
        "authority_epoch": 0,
    }
    node = {"event_type": event_type, "payload": payload, "envelope": envelope}
    (Path(REPO) / "node.json").write_text(json.dumps(node, indent=2))
    git("add", "node.json")
    git("commit", "-m", f"{event_type} {envelope['payload_hash']}", "--no-gpg-sign")
    new_tip = git("rev-parse", "HEAD").stdout.strip()
    git("update-ref", "refs/turingos/tape_tip", new_tip)
    # advance accepted_head ONLY on ADVANCE (predicate PASS assumed true for the spike's accept events)
    if he == "ADVANCE":
        git("update-ref", "refs/turingos/accepted_head", new_tip)
    return new_tip

def replay_accepted_head():
    """Walk genesis..tape_tip, recompute digests, re-derive head_effect, rebuild accepted_head. Tape only."""
    log = git("rev-list", "--reverse", "refs/turingos/tape_tip").stdout.split()
    rebuilt = None
    for oid in log:
        node = json.loads(git("cat-file", "-p", f"{oid}:node.json").stdout)
        # recompute content_digest byte-identically
        recomputed = content_digest(node["payload"])
        assert recomputed == node["envelope"]["payload_hash"], f"digest mismatch at {oid}"
        # re-derive head_effect from registry (never trust the envelope's carried value blindly)
        he = HEAD_EFFECT[node["event_type"]]
        assert he == node["envelope"]["head_effect"], f"head_effect mismatch at {oid}"
        if he == "ADVANCE":
            rebuilt = oid
    return rebuilt

def main() -> int:
    results = {}
    for p in (REPO, SHA1_REMOTE, SHA256_REMOTE):
        shutil.rmtree(p, ignore_errors=True)
    subprocess.run(["git", "init", "--object-format=sha256", REPO], capture_output=True, env=ENV, check=True)
    git("config", "receive.denyNonFastForwards", "true")
    git("config", "receive.denyDeletes", "true")

    # criterion 1: object-format == sha256
    fmt = git("rev-parse", "--show-object-format").stdout.strip()
    results["c1_object_format_sha256"] = (fmt == "sha256")

    # build the tape: SystemBootstrapped(ADVANCE) -> FailureNode(PRESERVE) -> CandidateAccepted(ADVANCE)
    c1 = append_event("SystemBootstrapped", {"kind": "boot", "n": 1})
    acc_after_boot = git("rev-parse", "refs/turingos/accepted_head").stdout.strip()
    tip_after_boot = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()

    c2 = append_event("FailureNode", {"kind": "failure", "failure_class": "test_fail", "n": 2})
    tip_after_fail = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()
    acc_after_fail = git("rev-parse", "refs/turingos/accepted_head").stdout.strip()
    # criterion 2: after FailureNode, tape_tip advanced AND accepted_head did NOT move
    results["c2_failure_is_state"] = (tip_after_fail != tip_after_boot and acc_after_fail == acc_after_boot)

    c3 = append_event("CandidateAccepted", {"kind": "accept", "n": 3})
    tip3 = git("rev-parse", "refs/turingos/tape_tip").stdout.strip()
    acc3 = git("rev-parse", "refs/turingos/accepted_head").stdout.strip()
    # criterion 3: after CandidateAccepted, accepted_head == tape_tip
    results["c3_advance_rule"] = (acc3 == tip3 and acc3 == c3)

    # criterion 4: mixed-hash push fails closed; same-hash push exits 0
    subprocess.run(["git", "init", "--bare", "--object-format=sha1", SHA1_REMOTE], capture_output=True, env=ENV, check=True)
    subprocess.run(["git", "init", "--bare", "--object-format=sha256", SHA256_REMOTE], capture_output=True, env=ENV, check=True)
    mixed = subprocess.run(["git", "-C", REPO, "push", SHA1_REMOTE,
                            "refs/turingos/tape_tip:refs/turingos/tape_tip",
                            "refs/turingos/accepted_head:refs/turingos/accepted_head"],
                           capture_output=True, text=True, env=ENV)
    same = subprocess.run(["git", "-C", REPO, "push", SHA256_REMOTE,
                           "refs/turingos/tape_tip:refs/turingos/tape_tip",
                           "refs/turingos/accepted_head:refs/turingos/accepted_head"],
                          capture_output=True, text=True, env=ENV)
    results["c4_mixed_hash_fail_closed"] = (mixed.returncode != 0 and same.returncode == 0)
    results["c4_mixed_exit"] = mixed.returncode
    results["c4_same_exit"] = same.returncode

    # criterion 5: replay rebuilds accepted_head == on-disk, Tape-only, digests byte-identical
    rebuilt = replay_accepted_head()
    on_disk = git("rev-parse", "refs/turingos/accepted_head").stdout.strip()
    results["c5_replay_rebuilds_accepted_head"] = (rebuilt == on_disk)

    # criterion 6: exactly two refs/turingos/*, no authorization_head
    refs = [l.split()[-1] for l in git("for-each-ref", "refs/turingos/").stdout.strip().splitlines()]
    results["c6_exactly_two_refs"] = (sorted(refs) == ["refs/turingos/accepted_head", "refs/turingos/tape_tip"])
    results["c6_no_authorization_head"] = ("refs/turingos/authorization_head" not in refs)
    results["refs"] = refs

    crit = [k for k in results if k.startswith("c") and isinstance(results[k], bool)]
    all_pass = all(results[k] for k in crit)
    results["SPIKE"] = "S-1"
    results["ALL_PASS"] = all_pass
    print(json.dumps(results, indent=2))
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
