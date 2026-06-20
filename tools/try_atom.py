#!/usr/bin/env python3
"""try_atom — run ONE real atom of your choosing through the full TuringOS loop with a real Worker.

Boot -> Goal -> Module -> build a Shielded Capsule -> dispatch a real Worker (router fast tier by default)
to an isolated worktree -> import receipt + Macro anchor -> deterministic Predicate -> accept|fail-on-Tape
-> replay. Prints the verdict (Predicate PASS/FAIL with reasons) and the candidate the Worker produced.

Examples:
  PYTHONPATH=src python3 tools/try_atom.py \
      --worker claude --file mathx.py \
      --intent "Create mathx.py with is_prime(n) returning True iff n is a prime > 1" \
      --accept "python3 -c \"import mathx; assert mathx.is_prime(7) and not mathx.is_prime(8)\""

  # multiple acceptance commands + a higher tier:
  PYTHONPATH=src python3 tools/try_atom.py --worker codex --tier standard --file q.py \
      --intent "Create q.py with a Queue class (enqueue/dequeue, FIFO)" \
      --accept "python3 -c \"import q; x=q.Queue(); x.enqueue(1); x.enqueue(2); assert x.dequeue()==1\""

Workers: claude | codex | agy | grok   (must be logged in).  Tiers: fast | standard | deep.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import tempfile

from turingos.tape import Tape
from turingos import boot, capsule as capsule_mod, evidence, predicate, replay as replay_mod
from turingos.worker.cli import CliWorkerAdapter


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run one real atom through the TuringOS loop.")
    ap.add_argument("--worker", default="claude", choices=["claude", "codex", "agy", "grok"])
    ap.add_argument("--file", required=True, action="append", dest="files",
                    help="an allowed file the worker may create/edit (repeatable)")
    ap.add_argument("--intent", required=True, help="what the atom should accomplish")
    ap.add_argument("--accept", required=True, action="append", dest="accept",
                    help="an acceptance command that must exit 0 (repeatable) — the Predicate re-runs it")
    ap.add_argument("--tier", default=None, choices=["fast", "standard", "deep"],
                    help="override the smart router (default: router picks fast)")
    ap.add_argument("--keep", action="store_true", help="keep the worktree + tape for inspection")
    args = ap.parse_args(argv)

    base = tempfile.mkdtemp(prefix="tos_tryatom_")
    try:
        tape = Tape.init(os.path.join(base, "tape"), "W1")
        boot.boot(tape, {"project_id": "tryatom", "writer_id": "W1"})
        boot.accept_goalstate(tape, {"goal": args.intent})
        boot.accept_module_plan(tape, {"module": "m1"})

        atom = {"atom_id": "atom-1", "module_id": "m1", "intent": args.intent,
                "allowed_files": args.files, "acceptance_commands": args.accept}
        if args.tier:
            atom["tier"] = args.tier
        fm = capsule_mod.FailureMemory()
        cap = capsule_mod.build_capsule(tape, atom, failure_memory=fm)

        wt = os.path.join(base, "worktree")
        os.makedirs(wt, exist_ok=True)
        print(f"[dispatch] {args.worker} (tier={args.tier or 'router:fast'}) -> {wt}", flush=True)
        adapter = CliWorkerAdapter(args.worker, tier=args.tier)
        receipt = adapter.run(cap, wt)
        evidence.import_receipt(tape, receipt)
        evidence.import_macro_observation(tape, {"tree_oid": receipt["candidate"]["tree_oid"], "atom_id": "atom-1"})

        pred = predicate.evaluate(capsule=cap, receipt=receipt, worktree=wt, tape=tape,
                                  event_type="CandidateAccepted")
        tape.append("PredicateEvaluated",
                    {"capsule_id": cap["capsule_id"], "passed": bool(pred.passed),
                     "reason_digest": pred.reason_digest})
        if pred.passed:
            tape.append("CandidateAccepted", {"atom_id": "atom-1", "capsule_id": cap["capsule_id"]},
                        predicate_pass=True)
        else:
            tape.append("FailureNode", {"atom_id": "atom-1", "module_id": "m1",
                                        "reason_codes": [r["reason_code"] for r in pred.reasons if not r["ok"]]})

        st = replay_mod.replay(tape)
        print("\n=== VERDICT ===")
        print(json.dumps({
            "predicate_passed": pred.passed,
            "failing_checks": [r["reason_code"] for r in pred.reasons if not r["ok"]],
            "worker_status": receipt["status"],
            "files_touched": receipt["candidate"]["files_touched"],
            "tree_oid": receipt["candidate"]["tree_oid"][:16],
            "accepted_head_after": (str(st.accepted_head)[:16] if st.accepted_head else None),
            "replay_rebuilds_accepted_head": str(st.accepted_head) == str(tape.accepted_head()),
        }, indent=2))
        print("\n=== CANDIDATE (what the worker wrote) ===")
        for f in receipt["candidate"]["files_touched"]:
            p = os.path.join(wt, f)
            if os.path.isfile(p):
                print(f"\n----- {f} -----")
                print(open(p).read())
        if args.keep:
            print(f"\n[kept] worktree={wt}  tape={os.path.join(base, 'tape')}")
        return 0 if pred.passed else 1
    finally:
        if not args.keep:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
