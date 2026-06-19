"""Contract tests for turingos.loop (stdlib unittest, NOT pytest).

Captures the frozen Stage-1 E2E loop-driver contract from contracts/INTERFACES.md (loop.py
section) + src/turingos/PREDICATE.stage1_e2e.md:

    def run_loop(spec, tape_dir, *, worker=None, max_atoms=3) -> dict
        # Drives boot -> goalstate -> module plan -> for each atom: expand -> build shielded
        # capsule (inject only relevant FailureClass rule) -> dispatch worker to an isolated
        # worktree -> import receipt -> predicate.evaluate -> {FAIL: FailureNode + classify ;
        # PASS: CandidateAccepted (advance)} -> reduce/panorama. Then HandoffGenerated.
        # MUST traverse BOTH predicate branches (>=1 FailureNode AND >=1 CandidateAccepted).
        # Returns {accepted, failed, accepted_head, tape_tip, branches_covered, handoff_bundle}.

These tests are the Implementer-side contract. The authoritative MILESTONE gate is
tests/integration/loop_e2e.py (Verifier != Implementer); a separate test here shells out to it
and asserts it prints ALL_PASS true.

Run: PYTHONPATH=src python3 -m unittest tests.test_loop -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from turingos import loop as loop_mod
from turingos import replay as replay_mod
from turingos import registry
from turingos.tape import Tape


_SPEC = {
    "project_id": "dogfood-mvl",
    "goal": "close the minimum complete loop",
    "writer_id": "W1",
    "modules": [{"module_id": "m1", "intent": "first module"}],
}


def _unique_tape_dir() -> str:
    base = tempfile.mkdtemp(prefix="tos_loop_t_")
    return os.path.join(base, "tape"), base


class LoopRunBase(unittest.TestCase):
    """Runs the loop ONCE for the whole class and shares the result (the run is deterministic)."""

    @classmethod
    def setUpClass(cls):
        cls.tape_dir, cls.base = _unique_tape_dir()
        cls.summary = loop_mod.run_loop(_SPEC, cls.tape_dir, max_atoms=3)
        cls.tape = Tape(cls.tape_dir, writer_id="W1")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)


class TestSummaryShape(LoopRunBase):
    def test_summary_has_required_keys(self):
        for key in ("accepted", "failed", "accepted_head", "tape_tip",
                    "branches_covered", "handoff_bundle"):
            self.assertIn(key, self.summary, msg=f"summary missing {key!r}")

    def test_branches_covered_true(self):
        self.assertTrue(self.summary["branches_covered"])

    def test_at_least_one_accept_and_one_failure(self):
        self.assertGreaterEqual(int(self.summary["accepted"]), 1)
        self.assertGreaterEqual(int(self.summary["failed"]), 1)
        # branches_covered must reflect (accepted>=1 and failed>=1)
        self.assertEqual(
            bool(self.summary["branches_covered"]),
            int(self.summary["accepted"]) >= 1 and int(self.summary["failed"]) >= 1,
        )

    def test_refs_match_disk(self):
        self.assertEqual(str(self.summary["accepted_head"]), str(self.tape.accepted_head()))
        self.assertEqual(str(self.summary["tape_tip"]), str(self.tape.tape_tip()))


class TestTapeBranches(LoopRunBase):
    def test_both_event_types_on_tape(self):
        events = [e["event_type"] for e in self.tape.walk()]
        self.assertIn("FailureNode", events)
        self.assertIn("CandidateAccepted", events)

    def test_candidate_accepted_count_matches_summary(self):
        events = [e["event_type"] for e in self.tape.walk()]
        self.assertEqual(events.count("CandidateAccepted"), int(self.summary["accepted"]))
        self.assertEqual(events.count("FailureNode"), int(self.summary["failed"]))

    def test_predicate_evaluated_recorded(self):
        events = [e["event_type"] for e in self.tape.walk()]
        self.assertIn("PredicateEvaluated", events)

    def test_worker_dispatched_is_authorization_not_accept(self):
        # WorkerDispatched is a PRESERVE authorization, never an advance.
        self.assertEqual(registry.head_effect("WorkerDispatched"), "PRESERVE")
        events = [e["event_type"] for e in self.tape.walk()]
        self.assertIn("WorkerDispatched", events)


class TestReplay(LoopRunBase):
    def test_replay_rebuilds_accepted_head(self):
        st = replay_mod.replay(self.tape)
        self.assertEqual(str(st.accepted_head), str(self.tape.accepted_head()))

    def test_replay_equal_byte_identical(self):
        self.assertTrue(replay_mod.verify_replay_equal(self.tape))

    def test_handoff_bundle_replays_to_same_accepted_head(self):
        bundle = self.summary["handoff_bundle"]
        self.assertTrue(bundle and Path(bundle).exists(), msg="handoff bundle missing")
        st = replay_mod.replay_from_handoff(bundle)
        self.assertEqual(str(st.accepted_head), str(self.tape.accepted_head()))


class TestShield(LoopRunBase):
    def test_failure_on_tape(self):
        events = [e["event_type"] for e in self.tape.walk()]
        self.assertIn("FailureNode", events)

    def test_a_capsule_injected_only_abstract_rules_no_raw_leak(self):
        leaked = False
        injected_seen = False
        for e in self.tape.walk():
            if e["event_type"] != "WorkCapsuleBuilt":
                continue
            cap = e["payload"]
            blob = json.dumps(cap)
            if "worker_stdout" in blob or "raw_failure" in blob or "stack_trace" in blob:
                leaked = True
            if cap.get("injected_rules"):
                injected_seen = True
                # injected rules are STRICTLY {failure_class, rule} — no raw keys.
                for rule in cap["injected_rules"]:
                    self.assertEqual(set(rule.keys()), {"failure_class", "rule"})
        self.assertFalse(leaked, msg="raw failure/worker stdout leaked into a capsule")
        self.assertTrue(injected_seen, msg="no capsule carried an injected abstract rule")


class TestFreshProcessRebuild(LoopRunBase):
    def test_fresh_process_rebuilds_from_tape_only(self):
        # A fresh python process, Tape-only, must rebuild the same accepted_head from the bundle.
        bundle = self.summary["handoff_bundle"]
        code = (
            "import sys, json;"
            "from turingos import replay as r;"
            f"st = r.replay_from_handoff({bundle!r});"
            "print(st.accepted_head)"
        )
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        res = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, env=env,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertEqual(res.stdout.strip(), str(self.tape.accepted_head()))


class TestDeterminism(unittest.TestCase):
    def test_two_runs_produce_same_branch_coverage(self):
        d1, b1 = _unique_tape_dir()
        d2, b2 = _unique_tape_dir()
        try:
            s1 = loop_mod.run_loop(_SPEC, d1, max_atoms=3)
            s2 = loop_mod.run_loop(_SPEC, d2, max_atoms=3)
            self.assertEqual(s1["accepted"], s2["accepted"])
            self.assertEqual(s1["failed"], s2["failed"])
            self.assertTrue(s1["branches_covered"])
            self.assertTrue(s2["branches_covered"])
        finally:
            shutil.rmtree(b1, ignore_errors=True)
            shutil.rmtree(b2, ignore_errors=True)


class TestMilestoneGate(unittest.TestCase):
    """The authoritative milestone gate (Verifier != Implementer) must print ALL_PASS true."""

    def test_loop_e2e_gate_all_pass(self):
        repo_root = Path(__file__).resolve().parents[1]
        gate = repo_root / "tests" / "integration" / "loop_e2e.py"
        self.assertTrue(gate.exists(), msg=f"missing gate {gate}")
        env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
        res = subprocess.run(
            [sys.executable, str(gate)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(res.returncode, 0, msg=f"gate exit {res.returncode}\n{res.stdout}\n{res.stderr}")
        payload = json.loads(res.stdout)
        self.assertTrue(payload.get("ALL_PASS"), msg=json.dumps(payload, indent=2))


if __name__ == "__main__":
    unittest.main()
