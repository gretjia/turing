"""Tests for turingos.cli — the argparse entrypoint that wires the kernel together.

Predicate-first (these were written before cli.py existed). Stdlib unittest ONLY
(pytest is NOT installed). We call cli.main([...]) directly and assert on exit codes,
on the side effects on a real SHA-256 Micro Tape, and on captured stdout.

Each test uses a UNIQUE tmp dir under /tmp/tos_cli_t so parallel agents never collide.
Deterministic git identity is set via env for any git the kernel drives.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from turingos import cli
from turingos.tape import Tape


# Deterministic git identity for any subprocess git the kernel runs during these tests.
os.environ.setdefault("GIT_AUTHOR_NAME", "turingos")
os.environ.setdefault("GIT_AUTHOR_EMAIL", "tape@turingos.local")
os.environ.setdefault("GIT_COMMITTER_NAME", "turingos")
os.environ.setdefault("GIT_COMMITTER_EMAIL", "tape@turingos.local")

_BASE_TMP = "/tmp/tos_cli_t"


def _mkdtemp() -> str:
    Path(_BASE_TMP).mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(dir=_BASE_TMP)


def _run(argv):
    """Run cli.main(argv) capturing stdout; return (exit_code, stdout_text)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(argv)
    return rc, buf.getvalue()


class CliTestBase(unittest.TestCase):
    def setUp(self):
        self.work = _mkdtemp()
        self.tape_dir = str(Path(self.work) / "micro.tape")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write_json(self, name: str, obj) -> str:
        p = Path(self.work) / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return str(p)


class TestTapeInit(CliTestBase):
    def test_tape_init_creates_sha256_repo(self):
        rc, _ = _run(["tape-init", self.tape_dir])
        self.assertEqual(rc, 0)
        # A real SHA-256 Micro repo with the two refs config in place.
        self.assertTrue(Path(self.tape_dir, ".git").exists())
        t = Tape(self.tape_dir, "cli-writer")
        self.assertEqual(t.object_format(), "sha256")

    def test_tape_init_returns_zero(self):
        rc, _ = _run(["tape-init", self.tape_dir])
        self.assertEqual(rc, 0)


class TestAppend(CliTestBase):
    def setUp(self):
        super().setUp()
        rc, _ = _run(["tape-init", self.tape_dir])
        self.assertEqual(rc, 0)

    def test_append_genesis_bootstrap_roundtrips_and_advances_tip(self):
        # First event on a fresh tape MUST be a SystemBootstrapped (writer-establishing). It is a
        # SOVEREIGN_ACCEPT (ADVANCE) event, so the append asserts a Predicate PASS via the flag.
        payload = self._write_json("boot.json", {"writer_id": "cli-writer", "spec": "demo"})
        t = Tape(self.tape_dir, "cli-writer")
        self.assertIsNone(t.tape_tip())  # nothing yet

        rc, out = _run(["append", self.tape_dir, "SystemBootstrapped", payload, "--predicate-pass"])
        self.assertEqual(rc, 0)

        # tape_tip advanced.
        t2 = Tape(self.tape_dir, "cli-writer")
        tip = t2.tape_tip()
        self.assertIsNotNone(tip)

        # The appended event round-trips: walk shows exactly one SystemBootstrapped with our payload.
        events = t2.walk()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "SystemBootstrapped")
        self.assertEqual(events[0]["payload"], {"writer_id": "cli-writer", "spec": "demo"})

        # CLI emitted the new event_id ("mu:"+oid) on stdout.
        self.assertIn("mu:", out)

    def test_append_second_event_advances_tip_again(self):
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        rc, _ = _run(["append", self.tape_dir, "SystemBootstrapped", boot, "--predicate-pass"])
        self.assertEqual(rc, 0)
        tip1 = Tape(self.tape_dir, "cli-writer").tape_tip()

        # A PRESERVE (non-advancing) event: tape_tip still advances, accepted_head must not.
        obs = self._write_json("obs.json", {"atom_id": "atom-1", "intent": "do x"})
        rc, _ = _run(["append", self.tape_dir, "AtomProposed", obs])
        self.assertEqual(rc, 0)
        tip2 = Tape(self.tape_dir, "cli-writer").tape_tip()

        self.assertIsNotNone(tip1)
        self.assertIsNotNone(tip2)
        self.assertNotEqual(tip1, tip2)  # tip advanced

    def test_append_advance_event_without_predicate_pass_fails_nonzero(self):
        # An ADVANCE event with no asserted Predicate PASS is RejectedAppend (a failed accept must
        # be a FailureNode, never a stuck advance) — the CLI surfaces this as a nonzero exit.
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        rc, _ = _run(["append", self.tape_dir, "SystemBootstrapped", boot])
        self.assertNotEqual(rc, 0)

    def test_append_unknown_event_type_fails_nonzero(self):
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        _run(["append", self.tape_dir, "SystemBootstrapped", boot, "--predicate-pass"])
        bad = self._write_json("bad.json", {"x": 1})
        rc, _ = _run(["append", self.tape_dir, "NotARealEvent", bad])
        self.assertNotEqual(rc, 0)

    def test_append_missing_payload_file_fails_nonzero(self):
        rc, _ = _run(["append", self.tape_dir, "SystemBootstrapped",
                      str(Path(self.work) / "does_not_exist.json")])
        self.assertNotEqual(rc, 0)


class TestReplay(CliTestBase):
    def setUp(self):
        super().setUp()
        _run(["tape-init", self.tape_dir])
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        _run(["append", self.tape_dir, "SystemBootstrapped", boot, "--predicate-pass"])

    def test_replay_runs_and_exits_zero(self):
        out_dir = str(Path(self.work) / "replay_out")
        rc, out = _run(["replay", "--tape", self.tape_dir, "--out", out_dir])
        self.assertEqual(rc, 0)
        # An accepted_head line is printed (None on a boot-only tape) and an out file is written.
        self.assertIn("accepted_head", out)
        self.assertTrue(Path(out_dir).exists())

    def test_replay_after_accept_reports_accepted_head(self):
        # Drive a SOVEREIGN_ACCEPT directly via the kernel so replay has an accepted_head.
        t = Tape(self.tape_dir, "cli-writer")
        t.append("CandidateAccepted", {"atom_id": "atom-1", "ok": True},
                 predicate_pass=True)
        out_dir = str(Path(self.work) / "replay_out2")
        rc, out = _run(["replay", "--tape", self.tape_dir, "--out", out_dir])
        self.assertEqual(rc, 0)
        # The on-disk accepted_head must appear in the printed output.
        self.assertIn(t.accepted_head(), out)


class TestHandoff(CliTestBase):
    def setUp(self):
        super().setUp()
        _run(["tape-init", self.tape_dir])
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        _run(["append", self.tape_dir, "SystemBootstrapped", boot, "--predicate-pass"])

    def test_handoff_generate_writes_bundle(self):
        out_dir = str(Path(self.work) / "bundle")
        rc, out = _run(["handoff", "generate", "--tape", self.tape_dir, "--out", out_dir])
        self.assertEqual(rc, 0)
        # The bundle directory + a bare-clone tape.git inside it exist.
        self.assertTrue(Path(out_dir).exists())
        self.assertTrue(Path(out_dir, "tape.git").exists())


class TestPredicateEvaluate(CliTestBase):
    """predicate evaluate wires to predicate.evaluate; exit code reflects PASS/FAIL."""

    def setUp(self):
        super().setUp()
        _run(["tape-init", self.tape_dir])
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        _run(["append", self.tape_dir, "SystemBootstrapped", boot, "--predicate-pass"])

    def test_predicate_evaluate_runs_and_prints_passed(self):
        # A deliberately-incomplete capsule/receipt: evaluate is TOTAL and returns FAIL (not a crash).
        # We only assert the CLI runs the gate and reports a passed verdict + a nonzero exit on FAIL.
        capsule = self._write_json("capsule.json", {"schema_id": "turingos.capsule.v1"})
        receipt = self._write_json("receipt.json", {"schema_id": "turingos.receipt.v1"})
        worktree = str(Path(self.work) / "wt")
        Path(worktree).mkdir(parents=True, exist_ok=True)
        rc, out = _run([
            "predicate", "evaluate",
            "--capsule", capsule,
            "--receipt", receipt,
            "--worktree", worktree,
            "--tape", self.tape_dir,
            "--event-type", "CandidateAccepted",
        ])
        # Gate ran and reported a verdict.
        self.assertIn("passed", out)
        # This incomplete input fails the gate => nonzero exit (PASS would be 0).
        self.assertNotEqual(rc, 0)


class TestPanorama(CliTestBase):
    def setUp(self):
        super().setUp()
        _run(["tape-init", self.tape_dir])
        boot = self._write_json("boot.json", {"writer_id": "cli-writer"})
        _run(["append", self.tape_dir, "SystemBootstrapped", boot, "--predicate-pass"])

    def test_panorama_prints_qt_and_labels(self):
        rc, out = _run(["panorama", "--tape", self.tape_dir])
        self.assertEqual(rc, 0)
        # The panorama surfaces q_t plus the Authorized-vs-Accepted labels.
        self.assertIn("accepted_head", out)
        self.assertIn("q_t", out)


class TestArgparse(CliTestBase):
    def test_no_args_returns_nonzero(self):
        rc, _ = _run([])
        self.assertNotEqual(rc, 0)

    def test_unknown_subcommand_returns_nonzero(self):
        # argparse exits via SystemExit(2) on an unknown subcommand; main must surface nonzero.
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["frobnicate"])
        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
