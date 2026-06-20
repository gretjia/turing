"""Unit tests for CliWorkerAdapter using a STUB cli (no live agent calls, deterministic)."""
import os
import shutil
import tempfile
import unittest

from turingos import schemas
from turingos.worker.cli import CliWorkerAdapter, build_prompt

_STUB_OK = """import sys, pathlib
pathlib.Path("out.txt").write_text("ok")
sys.exit(0)
"""
_STUB_FAIL = """import sys
sys.exit(1)
"""

CAPSULE = {
    "schema_id": "turingos.capsule.v1",
    "capsule_id": "cap:" + "a" * 16,
    "atom_id": "atom-1",
    "intent": "write out.txt",
    "allowed_files": ["out.txt"],
    "budget": {"wall_seconds": 60, "max_retries": 1},
    "acceptance_commands": ["test -f out.txt"],
    "context": {"tape_tip": "x", "accepted_head": "y"},
}


class TestCliWorkerAdapter(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="tos_cliadapter_")
        self.stub = os.path.join(self.base, "stub.py")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _adapter(self, body):
        with open(self.stub, "w") as f:
            f.write(body)
        return CliWorkerAdapter("stub", argv_builder=lambda prompt, wt: ["python3", self.stub])

    def test_prompt_includes_scope_and_tests(self):
        p = build_prompt(CAPSULE)
        self.assertIn("out.txt", p)
        self.assertIn("test -f out.txt", p)

    def test_ok_run_builds_valid_receipt_with_candidate(self):
        wt = os.path.join(self.base, "wt_ok")
        r = self._adapter(_STUB_OK).run(CAPSULE, wt)
        schemas.validate_receipt(r)               # adapter-agnostic receipt is schema-valid
        self.assertEqual(r["status"], "ok")
        self.assertIn("out.txt", r["candidate"]["files_touched"])
        self.assertTrue(r["candidate"]["tree_oid"])   # real git tree anchor
        self.assertEqual(r["worker_id"], "stub")
        self.assertTrue(r["no_orphan"])

    def test_failed_run_is_normalized(self):
        wt = os.path.join(self.base, "wt_fail")
        r = self._adapter(_STUB_FAIL).run(CAPSULE, wt)
        self.assertEqual(r["status"], "failed")
        schemas.validate_receipt(r)


if __name__ == "__main__":
    unittest.main()
