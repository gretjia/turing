"""Contract tests for turingos.predicate (stdlib unittest, NOT pytest).

Captures the frozen predicate-kernel contract from contracts/INTERFACES.md (predicate.py
section) + contracts/predicate_set.md:

    @dataclass(frozen=True) PredicateResult{passed, reasons, reason_digest}
    def evaluate(*, capsule, receipt, worktree, tape, event_type) -> PredicateResult
    CHECK_CODES = (...)

The predicate is a deterministic, MECHANICAL boolean gate f: X -> {0,1} over Tape bytes.
It runs P0 (codec guard) + P1..P9 ONLY. NO quality / taste / UI / subjective check anywhere
(release-audit 临时违宪 #5). It is PURE: it never writes the tape (no append, no ref move).

Determinism: two evaluations over identical inputs yield identical boolean AND identical
reason_digest (= sha256(JCS(sorted reason records))).

This negative matrix asserts each fault surfaces the CORRECT reason_code, and the clean
PASS case yields passed=True.

Run: PYTHONPATH=src python3 -m unittest tests.test_predicate -v
"""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from turingos import codec, predicate
from turingos import evidence
from turingos.predicate import PredicateResult, evaluate, CHECK_CODES
from turingos.tape import Tape


# Deterministic git identity for any scratch Macro worktree the tests build.
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "tester",
    "GIT_AUTHOR_EMAIL": "tester@turingos.local",
    "GIT_COMMITTER_NAME": "tester",
    "GIT_COMMITTER_EMAIL": "tester@turingos.local",
    "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000",
}


def _git(repo: str, *args: str) -> str:
    env = {**os.environ, **_GIT_ENV}
    res = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, env=env
    )
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {res.returncode}: {res.stderr.strip()}")
    return res.stdout


def _reasons_by_check(result: PredicateResult) -> dict:
    return {r["check"]: r for r in result.reasons}


def _failed_codes(result: PredicateResult) -> set:
    return {r["reason_code"] for r in result.reasons if not r["ok"] and r["reason_code"]}


class PredicateTestBase(unittest.TestCase):
    """Builds a fully-consistent PASS scenario, then each negative test mutates one thing."""

    def setUp(self):
        # UNIQUE scratch dir per test so parallel agents / parallel cases never collide.
        self.root = tempfile.mkdtemp(prefix="tos_predicate_t_")

        # --- Macro worktree: a real git repo with one tracked file. -------------------------
        self.worktree = os.path.join(self.root, "worktree")
        os.makedirs(self.worktree, exist_ok=True)
        _git(self.worktree, "init")
        _git(self.worktree, "config", "user.name", "tester")
        _git(self.worktree, "config", "user.email", "tester@turingos.local")
        # the file the candidate "touched" — relative path, inside scope.
        touched_rel = "src/foo.py"
        fpath = Path(self.worktree) / touched_rel
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text("print('ok')\n", encoding="utf-8")
        _git(self.worktree, "add", "-A")
        _git(self.worktree, "commit", "--no-gpg-sign", "-m", "candidate")
        self.tree_oid = _git(self.worktree, "rev-parse", "HEAD^{tree}").strip()
        self.touched_rel = touched_rel

        # --- Micro Tape: boot + import a macro observation (anchor) + import the receipt. ----
        self.repo = os.path.join(self.root, "micro_tape")
        self.tape = Tape.init(self.repo, "W1")
        self.tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        tip = self.tape.tape_tip()
        acc = self.tape.accepted_head()

        # The capsule (built against the live tape state). schema-valid turingos.capsule.v1.
        self.capsule = {
            "schema_id": "turingos.capsule.v1",
            "capsule_id": "cap:cafef00d",
            "atom_id": "atom-1",
            "allowed_files": [touched_rel, "src/bar.py"],
            "forbidden_files": ["secrets.env"],
            "budget": {"wall_seconds": 30, "max_retries": 1},
            "acceptance_commands": ["true"],  # exit 0 -> P6 passes
            "context": {"tape_tip": tip, "accepted_head": acc},
        }

        # The receipt the worker self-reported. schema-valid turingos.receipt.v1.
        self.receipt = {
            "schema_id": "turingos.receipt.v1",
            "receipt_id": "rcpt:deadbeef",
            "capsule_id": "cap:cafef00d",
            "worker_id": "fake",
            "worktree_path": self.worktree,
            "candidate": {
                "tree_oid": self.tree_oid,
                "files_touched": [touched_rel],
            },
            "status": "ok",
        }

        # Macro anchor on the tape: tree_oid must equal the receipt's candidate tree_oid (P7).
        evidence.import_macro_observation(self.tape, {"tree_oid": self.tree_oid})
        # Import the receipt LAST so it is the latest WorkerReceiptImported (P5 target).
        evidence.import_receipt(self.tape, self.receipt)

        self.event_type = "CandidateAccepted"  # a SOVEREIGN_ACCEPT (exercises P9)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _evaluate(self, *, capsule=None, receipt=None, worktree=None, event_type=None):
        return evaluate(
            capsule=capsule if capsule is not None else self.capsule,
            receipt=receipt if receipt is not None else self.receipt,
            worktree=worktree if worktree is not None else self.worktree,
            tape=self.tape,
            event_type=event_type if event_type is not None else self.event_type,
        )


class TestCleanPass(PredicateTestBase):
    def test_clean_case_passes(self):
        result = self._evaluate()
        self.assertTrue(
            result.passed,
            msg=f"expected PASS; failing reasons: {[r for r in result.reasons if not r['ok']]}",
        )
        # Every reason record is well-formed.
        for r in result.reasons:
            self.assertIn("check", r)
            self.assertIn("ok", r)
            self.assertIn("reason_code", r)
            self.assertIn("detail", r)
        # passed == all reasons ok
        self.assertEqual(result.passed, all(r["ok"] for r in result.reasons))

    def test_result_is_frozen_dataclass(self):
        result = self._evaluate()
        self.assertIsInstance(result, PredicateResult)
        self.assertIsInstance(result.passed, bool)
        self.assertIsInstance(result.reasons, tuple)
        self.assertIsInstance(result.reason_digest, str)
        self.assertTrue(result.reason_digest.startswith("sha256:"))
        # frozen: cannot reassign
        with self.assertRaises(Exception):
            result.passed = False  # type: ignore[misc]

    def test_evaluate_does_not_write_tape(self):
        # PURE: evaluate must not append / move a ref.
        tip_before = self.tape.tape_tip()
        acc_before = self.tape.accepted_head()
        self._evaluate()
        self.assertEqual(self.tape.tape_tip(), tip_before)
        self.assertEqual(self.tape.accepted_head(), acc_before)


class TestDeterminism(PredicateTestBase):
    def test_identical_inputs_identical_passed_and_digest(self):
        a = self._evaluate()
        b = self._evaluate()
        self.assertEqual(a.passed, b.passed)
        self.assertEqual(a.reason_digest, b.reason_digest)

    def test_identical_inputs_failure_case_deterministic(self):
        # A failing case must ALSO be byte-deterministic in (passed, reason_digest).
        bad = copy.deepcopy(self.receipt)
        bad["candidate"]["files_touched"] = ["outside/evil.py"]
        a = self._evaluate(receipt=bad)
        b = self._evaluate(receipt=bad)
        self.assertFalse(a.passed)
        self.assertEqual(a.passed, b.passed)
        self.assertEqual(a.reason_digest, b.reason_digest)

    def test_digest_matches_independent_recompute(self):
        result = self._evaluate()
        # The digest is sha256(JCS(sorted reason records)). Recompute it the contract way:
        sorted_reasons = sorted(
            ({"check": r["check"], "ok": r["ok"],
              "reason_code": r["reason_code"], "detail": r["detail"]} for r in result.reasons),
            key=lambda r: r["check"],
        )
        expected = codec.content_digest({"reasons": sorted_reasons})
        self.assertEqual(result.reason_digest, expected)


class TestCheckCodes(unittest.TestCase):
    def test_check_codes_present(self):
        for code in (
            "schema_invalid", "parent_mismatch", "scope_violation", "isolation_violation",
            "receipt_hash_mismatch", "test_fail", "anchor_mismatch", "replay_mismatch",
            "advance_rule_violation", "ascii_key_violation", "float_violation",
        ):
            self.assertIn(code, CHECK_CODES)


class TestNegativeReceiptHash(PredicateTestBase):
    def test_mutated_receipt_byte_fails_hash(self):
        # Mutate ONE field of the receipt AFTER it was imported: recomputed digest != imported hash.
        mutated = copy.deepcopy(self.receipt)
        mutated["worker_id"] = "tampered"
        result = self._evaluate(receipt=mutated)
        self.assertFalse(result.passed)
        self.assertIn("receipt_hash_mismatch", _failed_codes(result))


class TestNegativeScope(PredicateTestBase):
    def test_files_touched_outside_allowed_fails_scope(self):
        bad = copy.deepcopy(self.receipt)
        bad["candidate"]["files_touched"] = ["src/foo.py", "totally/outside.py"]
        result = self._evaluate(receipt=bad)
        self.assertFalse(result.passed)
        self.assertIn("scope_violation", _failed_codes(result))

    def test_files_touched_in_forbidden_fails_scope(self):
        # Even an allowed-listed path is a scope violation if it is also forbidden.
        bad = copy.deepcopy(self.capsule)
        bad["allowed_files"] = ["src/foo.py", "secrets.env"]
        bad["forbidden_files"] = ["secrets.env"]
        rcpt = copy.deepcopy(self.receipt)
        rcpt["candidate"]["files_touched"] = ["secrets.env"]
        result = self._evaluate(capsule=bad, receipt=rcpt)
        self.assertFalse(result.passed)
        self.assertIn("scope_violation", _failed_codes(result))


class TestNegativeIsolation(PredicateTestBase):
    def test_dotdot_path_fails_isolation(self):
        bad = copy.deepcopy(self.capsule)
        bad["allowed_files"] = ["../escape.py"]
        rcpt = copy.deepcopy(self.receipt)
        rcpt["candidate"]["files_touched"] = ["../escape.py"]
        result = self._evaluate(capsule=bad, receipt=rcpt)
        self.assertFalse(result.passed)
        self.assertIn("isolation_violation", _failed_codes(result))

    def test_absolute_path_fails_isolation(self):
        bad = copy.deepcopy(self.capsule)
        bad["allowed_files"] = ["/etc/passwd"]
        rcpt = copy.deepcopy(self.receipt)
        rcpt["candidate"]["files_touched"] = ["/etc/passwd"]
        result = self._evaluate(capsule=bad, receipt=rcpt)
        self.assertFalse(result.passed)
        self.assertIn("isolation_violation", _failed_codes(result))


class TestNegativeAnchor(PredicateTestBase):
    def test_empty_tree_oid_fails_anchor(self):
        # An empty tree_oid in the receipt candidate fails P7 (anchor_mismatch).
        bad = copy.deepcopy(self.receipt)
        bad["candidate"]["tree_oid"] = ""
        result = self._evaluate(receipt=bad)
        self.assertFalse(result.passed)
        self.assertIn("anchor_mismatch", _failed_codes(result))

    def test_altered_tree_oid_fails_anchor(self):
        # tree_oid that does not match the imported MacroObservation anchor.
        bad = copy.deepcopy(self.receipt)
        bad["candidate"]["tree_oid"] = "f" * 64
        result = self._evaluate(receipt=bad)
        self.assertFalse(result.passed)
        self.assertIn("anchor_mismatch", _failed_codes(result))


class TestNegativeTestFail(PredicateTestBase):
    def test_acceptance_command_exit_1_fails_tests(self):
        bad = copy.deepcopy(self.capsule)
        bad["acceptance_commands"] = ["false"]  # exit 1
        # Re-import a receipt matching this new capsule so P5 still passes — but here the test
        # under examination is P6, so use the SAME receipt (its hash is independent of acceptance).
        result = self._evaluate(capsule=bad)
        self.assertFalse(result.passed)
        self.assertIn("test_fail", _failed_codes(result))


class TestNegativeAsciiKey(PredicateTestBase):
    def test_non_ascii_key_in_capsule_fails_codec_guard(self):
        bad = copy.deepcopy(self.capsule)
        bad["wörker"] = "x"  # non-ASCII load-bearing key
        result = self._evaluate(capsule=bad)
        self.assertFalse(result.passed)
        self.assertIn("ascii_key_violation", _failed_codes(result))


class TestNegativeParent(PredicateTestBase):
    def test_wrong_tape_tip_fails_parent(self):
        bad = copy.deepcopy(self.capsule)
        # an OID that is neither the live tape_tip nor an ancestor of it.
        bad["context"]["tape_tip"] = "0" * 64
        result = self._evaluate(capsule=bad)
        self.assertFalse(result.passed)
        self.assertIn("parent_mismatch", _failed_codes(result))


class TestAdvanceRule(PredicateTestBase):
    def test_non_accept_event_advance_check_ok(self):
        # For a non-SOVEREIGN_ACCEPT event the advance rule check is OK by construction.
        result = self._evaluate(event_type="WorkerReceiptImported")
        by = _reasons_by_check(result)
        # find the advance-rule reason record (by its reason_code namespace).
        advance = [r for r in result.reasons if r["check"].lower().startswith("p9")
                   or "advance" in r["check"].lower()]
        self.assertTrue(advance, msg=f"no advance-rule reason record found in {list(by)}")
        self.assertTrue(advance[0]["ok"])


class TestNoTasteInGate(unittest.TestCase):
    """Meta-test: the predicate source contains NO subjective / taste check substrings."""

    def test_source_has_no_taste_substrings(self):
        src_path = Path(predicate.__file__)
        text = src_path.read_text(encoding="utf-8")
        for forbidden in ("quality", "taste", "looks_good", "subjective", "reviewer_opinion"):
            self.assertNotIn(
                forbidden, text,
                msg=f"forbidden subjective substring {forbidden!r} present in predicate.py "
                    f"(the gate is mechanical-only; release-audit 临时违宪 #5)",
            )


if __name__ == "__main__":
    unittest.main()
