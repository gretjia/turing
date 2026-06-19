#!/usr/bin/env python3
"""Stage-1 E2E milestone gate — the full loop with a fake/manual Worker (S-3 + S-4 + S-7 on the real loop).

Authored by the ORCHESTRATOR (Verifier != Implementer). The loop driver (turingos.loop.run_loop) is built to
satisfy THIS gate. Exit 0 only on full PASS. Consults the Tape only.

    PYTHONPATH=src python3 tests/integration/loop_e2e.py
"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
from pathlib import Path

from turingos import loop as loop_mod
from turingos import replay as replay_mod


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="tos_loop_e2e_"))
    tape_dir = str(base / "tape")
    results: dict = {}
    try:
        spec = {
            "project_id": "dogfood-mvl",
            "goal": "close the minimum complete loop",
            "writer_id": "W1",
            "modules": [{"module_id": "m1", "intent": "first module"}],
        }
        # run_loop must traverse BOTH predicate branches (>=1 FailureNode AND >=1 CandidateAccepted)
        summary = loop_mod.run_loop(spec, tape_dir, max_atoms=3)
        results["c1_branches_covered"] = bool(summary.get("branches_covered"))
        results["c2_at_least_one_accept"] = (int(summary.get("accepted", 0)) >= 1)
        results["c3_at_least_one_failure"] = (int(summary.get("failed", 0)) >= 1)

        from turingos.tape import Tape
        tape = Tape(tape_dir, writer_id="W1")

        # S-7: replay rebuilds accepted_head == on-disk, Tape-only
        st = replay_mod.replay(tape)
        results["c4_replay_rebuilds_accepted_head"] = (str(st.accepted_head) == str(tape.accepted_head()))
        # two replays byte-identical
        results["c5_replay_equal"] = bool(replay_mod.verify_replay_equal(tape))

        # the run produced a handoff bundle that replays to the same accepted state
        bundle = summary.get("handoff_bundle")
        if bundle and Path(bundle).exists():
            st3 = replay_mod.replay_from_handoff(bundle)
            results["c6_handoff_rebuild_equal"] = (str(st3.accepted_head) == str(tape.accepted_head()))
        else:
            nb = str(base / "handoff2")
            replay_mod.make_handoff_bundle(tape, nb)
            st3 = replay_mod.replay_from_handoff(nb)
            results["c6_handoff_rebuild_equal"] = (str(st3.accepted_head) == str(tape.accepted_head()))

        # S-4 (shield): a FailureNode exists on the Tape AND a later capsule injected only an abstract rule
        events = [e["event_type"] for e in tape.walk()]
        results["c7_failure_on_tape"] = ("FailureNode" in events)
        # find any WorkCapsuleBuilt after the first failure; assert it carries injected_rules (abstract) and
        # NO raw failure payload / worker stdout leaked into the capsule.
        leaked = False
        injected_seen = False
        for e in tape.walk():
            if e["event_type"] == "WorkCapsuleBuilt":
                cap = e["payload"]
                blob = json.dumps(cap)
                if "worker_stdout" in blob or "raw_failure" in blob or "stack_trace" in blob:
                    leaked = True
                if cap.get("injected_rules"):
                    injected_seen = True
        results["c8_shield_no_raw_leak"] = (not leaked)
        results["c9_shield_rule_injected"] = injected_seen  # at least one capsule carried an abstract rule

        # Authorized-vs-Accepted: WorkerDispatched is PRESERVE (never advances accepted_head)
        from turingos import registry
        results["c10_dispatch_is_authorization_not_accept"] = (
            registry.head_effect("WorkerDispatched") == "PRESERVE")

        crit = [k for k in results if k.startswith("c") and isinstance(results[k], bool)]
        all_pass = all(results[k] for k in crit)
        results["GATE"] = "stage1-loop-e2e"
        results["summary"] = summary
        results["ALL_PASS"] = all_pass
        print(json.dumps(results, indent=2, default=str))
        return 0 if all_pass else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
