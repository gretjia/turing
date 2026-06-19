#!/usr/bin/env python3
"""Foundation integration gate — S-1/S-7 (partial) on the REAL kernel.

Authored by the ORCHESTRATOR (Verifier != Implementer): an independent end-to-end check that the assembled
kernel honors the frozen contracts. Run after the foundation workflow:
    PYTHONPATH=src python3 tests/integration/kernel_smoke.py
Exit 0 only on full PASS. Consults the Tape ONLY (no projection/sqlite).
"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
from pathlib import Path

from turingos.tape import Tape
from turingos import replay as replay_mod
from turingos import reduce as reduce_mod


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="tos_kernel_smoke_"))
    repo = str(base / "tape")
    results: dict = {}
    try:
        tape = Tape.init(repo, writer_id="W1")
        results["c1_object_format_sha256"] = (tape.object_format() == "sha256")

        # BOOT/ADOPT/Goal/Module (SOVEREIGN_ACCEPT, predicate PASS)
        tape.append("SystemBootstrapped", {"kind": "boot", "writer_id": "W1", "n": 1}, predicate_pass=True)
        acc_boot = tape.accepted_head()
        tape.append("ProjectAdopted", {"kind": "adopt", "n": 2}, predicate_pass=True)
        tape.append("GoalStateAccepted", {"goal": "close the minimum complete loop", "n": 3}, predicate_pass=True)
        tape.append("ModulePlanAccepted", {"module": "foundation", "n": 4}, predicate_pass=True)
        acc_after_plan = tape.accepted_head()
        results["c2_accept_advances"] = (acc_boot is not None and acc_after_plan != acc_boot)

        # AtomProposed (PROPOSAL) -> tape_tip moves, accepted_head does NOT
        tip_b = tape.tape_tip(); acc_b = tape.accepted_head()
        tape.append("AtomProposed", {"atom": "atom-1", "module": "foundation", "n": 5})
        results["c3_proposal_preserve"] = (tape.tape_tip() != tip_b and tape.accepted_head() == acc_b)

        # FailureNode (OBSERVATION) -> failure-is-state: tape_tip moves, accepted_head does NOT
        tip_f = tape.tape_tip(); acc_f = tape.accepted_head()
        tape.append("FailureNode", {"failure_class": "test_fail", "atom": "atom-1", "n": 6})
        results["c4_failure_is_state"] = (tape.tape_tip() != tip_f and tape.accepted_head() == acc_f)

        # CandidateAccepted (SOVEREIGN_ACCEPT, predicate PASS) -> accepted_head == tape_tip
        tape.append("CandidateAccepted", {"atom": "atom-1", "n": 7}, predicate_pass=True)
        results["c5_candidate_accept_advances"] = (tape.accepted_head() == tape.tape_tip())

        # exactly two refs, no authorization_head
        import subprocess
        refs = [l.split()[-1] for l in subprocess.run(
            ["git", "-C", repo, "for-each-ref", "refs/turingos/"],
            capture_output=True, text=True).stdout.strip().splitlines()]
        results["c6_two_refs"] = (sorted(refs) == ["refs/turingos/accepted_head", "refs/turingos/tape_tip"])

        # replay rebuilds accepted_head == on-disk (Tape-only)
        st = replay_mod.replay(tape)
        on_disk = tape.accepted_head()
        results["c7_replay_rebuilds_accepted_head"] = (str(st.accepted_head) == str(on_disk))

        # q_t populated from the tape
        q = st.q_t if isinstance(st.q_t, dict) else reduce_mod.reduce_qt(tape)
        results["c8_qt_has_goal"] = (q.get("active_goal") is not None)

        # two replays byte-equal
        results["c9_replay_equal"] = bool(replay_mod.verify_replay_equal(tape))

        # handoff bundle replays to same accepted state in a fresh process/dir
        bundle = str(base / "handoff")
        replay_mod.make_handoff_bundle(tape, bundle)
        st2 = replay_mod.replay_from_handoff(bundle)
        results["c10_handoff_rebuild_equal"] = (str(st2.accepted_head) == str(on_disk))

        crit = [k for k in results if k.startswith("c") and isinstance(results[k], bool)]
        all_pass = all(results[k] for k in crit)
        results["GATE"] = "foundation-kernel-smoke"
        results["ALL_PASS"] = all_pass
        print(json.dumps(results, indent=2))
        return 0 if all_pass else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
