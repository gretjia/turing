"""M1a canonical substrate gate tests.

These tests bind the M1a contract from the execution playbook: the repository
must carry a local CI gate runner for the canonical-bytes xcheck, singleton
codec lint, AST lint, and refs lint, and every gate must pass a tamper
self-test before the clean repo gate is trusted.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def run_cmd(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class TestM1aGateQuartet(unittest.TestCase):
    def assert_passes_with(self, proc: subprocess.CompletedProcess[str], needle: str) -> None:
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn(needle, proc.stdout)

    def test_gate_runner_self_tests_all_four_gates(self) -> None:
        proc = run_cmd("bash", "tools/ci/run_m1a_gates.sh", "--self-test")
        self.assert_passes_with(proc, "M1A_SELF_TEST_PASS")

    def test_gate_runner_clean_repo_passes_all_four_gates(self) -> None:
        proc = run_cmd("bash", "tools/ci/run_m1a_gates.sh")
        self.assert_passes_with(proc, "M1A_GATES_PASS")

    def test_xcheck_gate_proves_python_and_rust_bytes_match(self) -> None:
        proc = run_cmd("bash", "tools/gates/gate_xcheck_jcs.sh")
        self.assert_passes_with(proc, "XCHECK_PASS")

    def test_singleton_grep_gate_discriminates_tamper_fixture(self) -> None:
        proc = run_cmd("bash", "tools/gates/gate_singleton_codec.sh", "--self-test")
        self.assert_passes_with(proc, "SINGLETON_CODEC_SELF_TEST_PASS")

    def test_ast_gate_discriminates_aliased_json_dumps_tamper(self) -> None:
        proc = run_cmd("python3", "tools/gates/lint_no_second_codec.py", "--self-test")
        self.assert_passes_with(proc, "AST_CODEC_SELF_TEST_PASS")

    def test_ref_lint_discriminates_tamper_fixture(self) -> None:
        proc = run_cmd("bash", "tools/gates/gate_ref_lint.sh", "--self-test")
        self.assert_passes_with(proc, "REF_LINT_SELF_TEST_PASS")


if __name__ == "__main__":
    unittest.main()
