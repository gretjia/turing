"""Contract tests for turingos.worker (stdlib unittest, NOT pytest).

Captures the frozen worker seam from contracts/INTERFACES.md (worker/adapter.py +
worker/fake.py) and ADR-WORKER-001:

    class WorkerAdapter(abc.ABC){ worker_id; run(capsule, worktree) -> receipt dict }
    def dispatch(adapter, capsule, worktree, *, timeout_s) -> receipt   # TIMEOUT/KILL/RETRY, PG reap
    class FakeWorker(WorkerAdapter)  # deterministic stub; scenarios pass/fail_test/fail_scope

Load-bearing invariants exercised here (CLAUDE.md / receipt.schema.json):
  * Adapter-agnostic receipt: every receipt validates against turingos.receipt.v1 regardless of adapter.
  * FakeWorker creates a REAL git repo at the worktree; tree_oid == git rev-parse HEAD^{tree}; deterministic.
  * "pass" -> candidate confined to capsule.allowed_files; the capsule.acceptance_commands all exit 0
    (predicate P6 re-run, cwd=worktree); files_touched subset of allowed_files (P3); paths relative (P4).
  * "fail_scope" -> files_touched contains a path OUTSIDE allowed_files (P3 scope violation).
  * "fail_test" -> content makes a declared acceptance command exit non-zero (P6 test fail).
  * dispatch on a HANGING subprocess worker that spawns a child reaps the WHOLE process group on
    timeout: status in {timeout, killed}, no_orphan True, and the spawned child is gone (PG-REAP, no orphan).

Run: PYTHONPATH=src python3 -m unittest tests.test_worker -v
"""
from __future__ import annotations

import abc
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from turingos import codec, schemas
from turingos.predicate import evaluate
from turingos.tape import Tape
from turingos.worker import WorkerAdapter, dispatch
from turingos.worker.fake import FakeWorker

SCRATCH = "/tmp/tos_worker_t"


def _make_capsule(allowed_files, acceptance_commands, *, tape_tip="", accepted_head=""):
    """A minimal valid turingos.capsule.v1 (digest-derived capsule_id)."""
    body = {
        "atom_id": "atom:worker-test",
        "allowed_files": list(allowed_files),
        "acceptance_commands": list(acceptance_commands),
    }
    digest = codec.content_digest(body)[len("sha256:"):]
    capsule = {
        "schema_id": "turingos.capsule.v1",
        "capsule_id": "cap:" + digest,
        "atom_id": body["atom_id"],
        "allowed_files": body["allowed_files"],
        "budget": {"wall_seconds": 30, "max_retries": 1},
        "acceptance_commands": body["acceptance_commands"],
        "context": {"tape_tip": tape_tip, "accepted_head": accepted_head},
    }
    schemas.validate_capsule(capsule)
    return capsule


class WorkerTestBase(unittest.TestCase):
    def setUp(self):
        Path(SCRATCH).mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.mkdtemp(prefix="case_", dir=SCRATCH)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def worktree(self, name="wt"):
        return os.path.join(self.tmp, name)


class TestFakeWorkerPass(WorkerTestBase):
    def test_pass_receipt_valid_and_confined(self):
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py"],
        )
        wt = self.worktree()
        fake = FakeWorker("pass")
        receipt = fake.run(capsule, wt)

        # Adapter-agnostic schema validity.
        schemas.validate_receipt(receipt)
        self.assertEqual(receipt["schema_id"], "turingos.receipt.v1")
        self.assertEqual(receipt["worker_id"], "fake")
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["capsule_id"], capsule["capsule_id"])
        self.assertEqual(receipt["worktree_path"], wt)
        self.assertTrue(receipt["receipt_id"].startswith("rcpt:"))

        # A REAL git repo was created at the worktree.
        self.assertTrue(Path(wt, ".git").exists())

        # tree_oid is a real OID == git rev-parse HEAD^{tree}.
        head_tree = subprocess.run(
            ["git", "-C", wt, "rev-parse", "HEAD^{tree}"],
            capture_output=True, text=True,
        ).stdout.strip()
        self.assertTrue(head_tree)
        self.assertEqual(receipt["candidate"]["tree_oid"], head_tree)

        # candidate confined to the worktree + within allowed_files (P3) + relative (P4).
        touched = receipt["candidate"]["files_touched"]
        self.assertTrue(touched)
        for p in touched:
            self.assertFalse(os.path.isabs(p), p)
            self.assertNotIn("..", p.split("/"))
            self.assertIn(p, set(capsule["allowed_files"]))

    def test_pass_acceptance_commands_exit_zero(self):
        # The acceptance commands the worker wrote files for must re-run green (cwd=worktree).
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py", "python3 -c 'import ast; ast.parse(open(\"src/feature.py\").read())'"],
        )
        wt = self.worktree()
        FakeWorker("pass").run(capsule, wt)
        for cmd in capsule["acceptance_commands"]:
            res = subprocess.run(cmd, shell=True, cwd=wt, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"{cmd!r}: {res.stderr}")

    def test_pass_deterministic(self):
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py"],
        )
        wt1 = self.worktree("a")
        wt2 = self.worktree("b")
        r1 = FakeWorker("pass").run(capsule, wt1)
        r2 = FakeWorker("pass").run(capsule, wt2)
        # Same capsule => same tree_oid (deterministic content + deterministic git env).
        self.assertEqual(r1["candidate"]["tree_oid"], r2["candidate"]["tree_oid"])
        self.assertEqual(r1["candidate"]["files_touched"], r2["candidate"]["files_touched"])

    def test_pass_predicate_passes(self):
        # End-to-end: a "pass" candidate should satisfy the deterministic predicate (P3/P4/P6/P7).
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py"],
        )
        wt = self.worktree()
        receipt = FakeWorker("pass").run(capsule, wt)

        # capsule context must point at the live tape tip for P2; build a tape and align it.
        tape_dir = os.path.join(self.tmp, "tape")
        tape = Tape.init(tape_dir, "W1")
        tape.append("SystemBootstrapped", {"kind": "boot"}, writer_id="W1", predicate_pass=True)
        live_tip = tape.tape_tip()
        capsule["context"]["tape_tip"] = live_tip
        # import the receipt so P5 can match the payload_hash
        from turingos.evidence import import_receipt
        import_receipt(tape, receipt)

        result = evaluate(
            capsule=capsule, receipt=receipt, worktree=wt,
            tape=tape, event_type="CandidateAccepted",
        )
        # P3 scope, P4 isolation, P6 tests, P7 anchor must all be OK for a clean pass candidate.
        by_check = {r["check"]: r for r in result.reasons}
        self.assertTrue(by_check["P3_scope"]["ok"], by_check["P3_scope"])
        self.assertTrue(by_check["P4_isolation"]["ok"], by_check["P4_isolation"])
        self.assertTrue(by_check["P6_tests"]["ok"], by_check["P6_tests"])
        self.assertTrue(by_check["P7_anchor"]["ok"], by_check["P7_anchor"])


class TestFakeWorkerFailScope(WorkerTestBase):
    def test_fail_scope_touches_outside_allowed(self):
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py"],
        )
        wt = self.worktree()
        receipt = FakeWorker("fail_scope").run(capsule, wt)
        schemas.validate_receipt(receipt)
        touched = set(receipt["candidate"]["files_touched"])
        allowed = set(capsule["allowed_files"])
        outside = touched - allowed
        self.assertTrue(outside, f"fail_scope must touch a path outside allowed_files; touched={touched}")

    def test_fail_scope_predicate_scope_violation(self):
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py"],
        )
        wt = self.worktree()
        receipt = FakeWorker("fail_scope").run(capsule, wt)
        tape_dir = os.path.join(self.tmp, "tape")
        tape = Tape.init(tape_dir, "W1")
        tape.append("SystemBootstrapped", {"kind": "boot"}, writer_id="W1", predicate_pass=True)
        capsule["context"]["tape_tip"] = tape.tape_tip()
        from turingos.evidence import import_receipt
        import_receipt(tape, receipt)
        result = evaluate(
            capsule=capsule, receipt=receipt, worktree=wt,
            tape=tape, event_type="CandidateAccepted",
        )
        self.assertFalse(result.passed)
        by_check = {r["check"]: r for r in result.reasons}
        self.assertFalse(by_check["P3_scope"]["ok"])
        self.assertEqual(by_check["P3_scope"]["reason_code"], "scope_violation")


class TestFakeWorkerFailTest(WorkerTestBase):
    def test_fail_test_command_exits_nonzero(self):
        # A declared command that the "fail_test" content makes fail.
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["grep -q PASS_MARKER src/feature.py"],
        )
        wt = self.worktree()
        receipt = FakeWorker("fail_test").run(capsule, wt)
        schemas.validate_receipt(receipt)
        # At least one declared acceptance command re-runs non-zero.
        any_fail = False
        for cmd in capsule["acceptance_commands"]:
            res = subprocess.run(cmd, shell=True, cwd=wt, capture_output=True, text=True)
            if res.returncode != 0:
                any_fail = True
        self.assertTrue(any_fail, "fail_test must make a declared acceptance command exit non-zero")

    def test_fail_test_files_in_scope(self):
        # fail_test fails on TESTS, not on scope: touched files stay within allowed_files.
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["grep -q PASS_MARKER src/feature.py"],
        )
        wt = self.worktree()
        receipt = FakeWorker("fail_test").run(capsule, wt)
        touched = set(receipt["candidate"]["files_touched"])
        self.assertTrue(touched.issubset(set(capsule["allowed_files"])), touched)


class TestReceiptAdapterAgnostic(WorkerTestBase):
    def test_inprocess_adapter_receipt_same_schema(self):
        # Any WorkerAdapter (here a trivial in-process one) produces a receipt the SAME schema validates.
        capsule = _make_capsule(
            allowed_files=["a.txt"],
            acceptance_commands=["true"],
        )

        class InProcAdapter(WorkerAdapter):
            worker_id = "inproc"

            def run(self, capsule, worktree):  # noqa: D401
                Path(worktree).mkdir(parents=True, exist_ok=True)
                body = {"capsule_id": capsule["capsule_id"], "n": 1}
                rid = codec.content_digest(body)[len("sha256:"):]
                return {
                    "schema_id": "turingos.receipt.v1",
                    "receipt_id": "rcpt:" + rid,
                    "capsule_id": capsule["capsule_id"],
                    "worker_id": self.worker_id,
                    "worktree_path": worktree,
                    "candidate": {"tree_oid": "0" * 64, "files_touched": ["a.txt"]},
                    "declared_test_results": [],
                    "status": "ok",
                    "no_orphan": True,
                }

        receipt = InProcAdapter().run(capsule, self.worktree())
        schemas.validate_receipt(receipt)  # adapter-agnostic
        self.assertEqual(receipt["worker_id"], "inproc")

    def test_dispatch_inprocess_just_runs(self):
        capsule = _make_capsule(
            allowed_files=["src/feature.py"],
            acceptance_commands=["test -f src/feature.py"],
        )
        wt = self.worktree()
        receipt = dispatch(FakeWorker("pass"), capsule, wt, timeout_s=30)
        schemas.validate_receipt(receipt)
        self.assertEqual(receipt["status"], "ok")
        self.assertTrue(receipt.get("no_orphan"))


# --- A subprocess-spawning worker that HANGS (parent + child), to exercise PG reap. ----------
_HANG_WORKER_SRC = r'''
import os, sys, time, subprocess
# Spawn a long-lived child in the SAME process group, write its pid where the test can read it.
pidfile = sys.argv[1]
child = subprocess.Popen([sys.executable, "-c", "import time;\nwhile True: time.sleep(3600)"])
with open(pidfile, "w") as f:
    f.write(str(os.getpid()) + "\n" + str(child.pid) + "\n")
    f.flush()
# Parent hangs forever too.
while True:
    time.sleep(3600)
'''


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TestDispatchTimeoutReapsGroup(WorkerTestBase):
    def test_timeout_kills_whole_process_group_no_orphan(self):
        # A WorkerAdapter whose run() launches a subprocess that spawns a child and hangs.
        scriptdir = self.tmp
        script = os.path.join(scriptdir, "hang_worker.py")
        Path(script).write_text(_HANG_WORKER_SRC)
        pidfile = os.path.join(scriptdir, "pids.txt")

        class HangWorker(WorkerAdapter):
            worker_id = "hang"
            # dispatch() must run this as a subprocess in its own process group so the
            # whole group (parent + spawned child) can be reaped on timeout.
            subprocess_argv = [
                __import__("sys").executable, script, pidfile,
            ]

            def run(self, capsule, worktree):  # pragma: no cover - dispatch path is used
                raise AssertionError("subprocess worker must be dispatched, not run() in-process")

        capsule = _make_capsule(
            allowed_files=["x.txt"],
            acceptance_commands=["true"],
        )
        wt = self.worktree()
        receipt = dispatch(HangWorker(), capsule, wt, timeout_s=2)

        # Normalized failure: status in {timeout, killed}, no_orphan True, schema valid.
        schemas.validate_receipt(receipt)
        self.assertIn(receipt["status"], {"timeout", "killed"}, receipt)
        self.assertTrue(receipt.get("no_orphan") is True, receipt)

        # The spawned child must be GONE (process group reaped, no orphan).
        self.assertTrue(Path(pidfile).exists(), "hang worker never wrote its pids")
        lines = [ln for ln in Path(pidfile).read_text().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2, lines)
        parent_pid, child_pid = int(lines[0]), int(lines[1])
        # Give the OS a beat to finish reaping.
        deadline = time.time() + 5
        while time.time() < deadline and (_pid_alive(parent_pid) or _pid_alive(child_pid)):
            time.sleep(0.05)
        self.assertFalse(_pid_alive(parent_pid), f"worker parent {parent_pid} survived timeout")
        self.assertFalse(_pid_alive(child_pid), f"spawned child {child_pid} orphaned after timeout")


if __name__ == "__main__":
    unittest.main()
