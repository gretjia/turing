#!/usr/bin/env python3
"""Stage 3 — private local DOGFOOD: the full loop on REAL atoms with REAL workers (fast tier).

Drives BOOT -> Goal -> Module -> {real atom -> shielded capsule -> REAL worker (router fast tier) -> receipt
+ macro anchor -> deterministic Predicate -> accept|fail-on-tape -> shield} -> replay/handoff. Measures the
REAL first-attempt pass rate at the fast tier (the empirical "is fast good enough" answer) and exercises the
router's retry-escalation (fast -> standard) on any failure. Live worker calls — cost-controlled (fast tier).
    PYTHONPATH=src python3 evidence/stage3/dogfood.py
"""
from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile

from turingos.tape import Tape
from turingos import boot, capsule as capsule_mod, evidence, predicate, replay as replay_mod
from turingos import reduce as reduce_mod, dispatch_router
from turingos.worker.cli import CliWorkerAdapter

ATOMS = [
    {"atom_id": "atom-factorial", "module_id": "m1", "intent": "Create mathx.py exposing factorial(n): iterative non-negative integer factorial.",
     "allowed_files": ["mathx.py"],
     "acceptance_commands": ["python3 -c \"import mathx; assert mathx.factorial(5)==120 and mathx.factorial(0)==1\""]},
    {"atom_id": "atom-slugify", "module_id": "m1", "intent": "Create strutil.py exposing slugify(s): lowercase, replace runs of non-alphanumeric chars with a single '-', strip leading/trailing '-'.",
     "allowed_files": ["strutil.py"],
     "acceptance_commands": ["python3 -c \"import strutil as s; assert s.slugify('Hello, World!')=='hello-world' and s.slugify('  a  b  ')=='a-b'\""]},
    {"atom_id": "atom-parsekv", "module_id": "m1", "intent": "Create parsekv.py exposing parse_kv(text): parse 'k=v' lines into a dict, ignoring blank lines and lines starting with '#'.",
     "allowed_files": ["parsekv.py"],
     "acceptance_commands": ["python3 -c \"import parsekv as p; assert p.parse_kv('a=1\\n\\n# c\\nb=2')=={'a':'1','b':'2'}\""]},
]
WORKERS = ["claude", "codex", "agy"]   # rotate real vendors (adapter-agnostic at the seam)


def _run_atom(tape, atom, fm, worker_id, base, attempt):
    cap = capsule_mod.build_capsule(tape, atom, failure_memory=fm)   # fast tier (risk low, unless retry rules present)
    tier = dispatch_router.select_tier(cap)
    tape.append("WorkerDispatched", {"capsule_id": cap["capsule_id"], "worker_id": worker_id,
                                     "worker_kind": "cli", "tier": tier})
    wt = os.path.join(base, f"{atom['atom_id']}_{attempt}_{worker_id}")
    os.makedirs(wt, exist_ok=True)
    receipt = CliWorkerAdapter(worker_id).run(cap, wt)
    evidence.import_receipt(tape, receipt)
    evidence.import_macro_observation(tape, {"tree_oid": receipt["candidate"]["tree_oid"],
                                             "atom_id": atom["atom_id"], "worker_id": worker_id})
    pred = predicate.evaluate(capsule=cap, receipt=receipt, worktree=wt, tape=tape, event_type="CandidateAccepted")
    tape.append("PredicateEvaluated", {"capsule_id": cap["capsule_id"], "passed": bool(pred.passed),
                                       "reason_digest": pred.reason_digest})
    reason_codes = [r.get("reason_code") for r in pred.reasons if not r.get("ok")]
    return cap, receipt, pred, tier, reason_codes, wt


def main() -> int:
    base = tempfile.mkdtemp(prefix="tos_dogfood_")
    out = {"atoms": [], "tiers_used": []}
    try:
        tape = Tape.init(os.path.join(base, "tape"), "W1")
        boot.boot(tape, {"project_id": "dogfood", "writer_id": "W1"})
        boot.accept_goalstate(tape, {"goal": "dogfood: deliver small real utilities via the loop"})
        boot.accept_module_plan(tape, {"module": "m1"})
        fm = capsule_mod.FailureMemory()

        first_try_pass = 0
        accepted = 0
        failed_nodes = 0
        for i, atom in enumerate(ATOMS):
            worker_id = WORKERS[i % len(WORKERS)]
            rec = {"atom": atom["atom_id"], "worker": worker_id, "attempts": []}
            passed = False
            for attempt in range(2):   # first try + one retry (router escalates on retry)
                cap, receipt, pred, tier, reasons, wt = _run_atom(tape, atom, fm, worker_id, base, attempt)
                out["tiers_used"].append(tier)
                rec["attempts"].append({"attempt": attempt, "tier": tier, "passed": bool(pred.passed),
                                        "status": receipt["status"], "reason_codes": reasons,
                                        "files_touched": receipt["candidate"]["files_touched"]})
                if pred.passed:
                    tape.append("CandidateAccepted", {"atom_id": atom["atom_id"], "capsule_id": cap["capsule_id"]},
                                predicate_pass=True)
                    accepted += 1
                    if attempt == 0:
                        first_try_pass += 1
                    passed = True
                    break
                # FAIL: failure-is-state + shield (classify -> abstract rule for the retry capsule)
                fn = {"atom_id": atom["atom_id"], "module_id": atom["module_id"],
                      "reason_code": (reasons[0] if reasons else "unknown"), "reason_codes": reasons}
                tape.append("FailureNode", fn)
                failed_nodes += 1
                fm.classify(fn)   # the next capsule for this atom inherits the abstract rule -> router escalates
            rec["final_pass"] = passed
            out["atoms"].append(rec)

        # S-7 on the dogfood tape: replay + handoff rebuild
        st = replay_mod.replay(tape)
        out["replay_rebuilds_accepted_head"] = (str(st.accepted_head) == str(tape.accepted_head()))
        out["replay_equal"] = bool(replay_mod.verify_replay_equal(tape))
        bundle = os.path.join(base, "handoff")
        replay_mod.make_handoff_bundle(tape, bundle)
        st2 = replay_mod.replay_from_handoff(bundle)
        out["handoff_rebuild_equal"] = (str(st2.accepted_head) == str(tape.accepted_head()))

        out["n_atoms"] = len(ATOMS)
        out["accepted"] = accepted
        out["first_attempt_pass"] = first_try_pass
        out["first_attempt_pass_rate"] = round(first_try_pass / len(ATOMS), 3)
        out["failure_nodes"] = failed_nodes
        out["q_t_active_goal"] = reduce_mod.reduce_qt(tape).get("active_goal")
        out["DOGFOOD_PASS"] = (accepted == len(ATOMS) and out["replay_rebuilds_accepted_head"]
                               and out["replay_equal"] and out["handoff_rebuild_equal"])
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["DOGFOOD_PASS"] else 1
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
        print(json.dumps(out, indent=2, default=str))
        return 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
