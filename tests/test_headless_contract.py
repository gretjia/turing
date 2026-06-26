from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
BOOK = REPO.parents[0] / "TOP_ALIGNMENT_PROJECT_BOOK.md"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def packet_digest(path: Path) -> str:
    packet = json.loads(path.read_text(encoding="utf-8"))
    packet.pop("packet_digest", None)
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class HeadlessContractTests(unittest.TestCase):
    def test_phase_capsule_contains_blocking_acceptance_and_forbidden_bytes(self):
        capsule = json.loads((REPO / "evidence/g12/phase_capsule.json").read_text())

        self.assertEqual(capsule["schema_id"], "PhaseCapsule.v1")
        self.assertTrue(capsule["external_verification_required"])
        self.assertIn(str(BOOK), capsule["forbidden_files"])
        self.assertIn("contracts/**", capsule["forbidden_files"])
        self.assertIn("src/**", capsule["forbidden_files"])
        self.assertTrue(any("grok_verify.py" in cmd for cmd in capsule["acceptance_commands"]))
        self.assertTrue(any("python3 -m pytest" == cmd for cmd in capsule["acceptance_commands"]))

    def test_gate_result_pass_invariants_and_not_run_domination(self):
        sys.path.insert(0, str(REPO / "tools/headless"))
        from headless_common import compute_product, write_json

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "sample.json"
            write_json(out, {"ok": True})

            pass_result = {
                "exit_status": 0,
                "reasons": [{"id": "clean_fixture", "verdict": "PASS"}],
                "not_run": [],
                "tool_digest": sha256_path(REPO / "pyproject.toml"),
                "input_digest": sha256_path(REPO / "pyproject.toml"),
                "output_digest": sha256_path(out),
                "stdout_digest": "sha256:" + hashlib.sha256(b"").hexdigest(),
                "stderr_digest": "sha256:" + hashlib.sha256(b"").hexdigest(),
                "tampered_fixture_results": [{"id": "mutant", "verdict": "FAIL"}],
                "clean_fixture_results": [{"id": "clean", "verdict": "PASS"}],
            }
            self.assertEqual(compute_product(pass_result), "PASS")

            blocked = dict(pass_result)
            blocked["not_run"] = ["rust_authority_kernel_missing"]
            self.assertEqual(compute_product(blocked), "NOT_RUN")

            bad_exit = dict(pass_result)
            bad_exit["exit_status"] = 1
            self.assertEqual(compute_product(bad_exit), "FAIL")

    def test_evidence_bundle_reports_rust_kernel_environment(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "evidence_bundle.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/headless/build_evidence_bundle.py",
                    "--book",
                    str(BOOK),
                    "--out",
                    str(out),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
            )

            bundle = json.loads(out.read_text())
            self.assertEqual(bundle["schema_id"], "EvidenceBundle.v1")
            self.assertEqual(bundle["m2_status"], "DISABLED")
            self.assertNotIn("rust_authority_kernel_missing", bundle["not_run"])
            self.assertNotIn("cargo_lock_missing", bundle["not_run"])
            self.assertIn("READY_FOR_HUMAN_GENESIS_SIGNATURE", bundle["state_ceiling"])
            self.assertEqual(bundle["forbidden_claims_present"], [])
            self.assertTrue((Path(td) / "human_decision_ledger.json").exists())
            self.assertTrue((Path(td) / "pack_disposition.json").exists())
            if bundle["not_run"]:
                self.assertNotEqual(result.returncode, 0)
            else:
                self.assertEqual(result.returncode, 0)

    def test_grok_wrapper_emits_schema_valid_not_run_report_when_external_tool_missing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            evidence = tmp / "evidence_bundle.json"
            evidence.write_text(json.dumps({"schema_id": "EvidenceBundle.v1", "gate_results": []}))
            out = tmp / "grok_report.json"

            env = os.environ.copy()
            env["PATH"] = str(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/headless/grok_verify.py",
                    "--candidate",
                    "0" * 40,
                    "--book",
                    str(BOOK),
                    "--evidence",
                    str(evidence),
                    "--out",
                    str(out),
                ],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(out.read_text())
            self.assertEqual(report["schema_id"], "GrokVerificationReport.v1")
            self.assertEqual(report["verdict"], "NOT_RUN")
            self.assertIn("grok_cli_missing", report["not_run"])
            self.assertEqual(report["m2_status"], "DISABLED")
            self.assertEqual(report["forbidden_claims_present"], [])
            self.assertEqual(report["packet_digest"], packet_digest(out))
            gate = json.loads((tmp / "gate_results/G12-A.json").read_text())
            self.assertEqual(gate["schema_id"], "GateResult.v1")
            self.assertEqual(gate["product"], "NOT_RUN")
            self.assertTrue(gate["not_run"])

    def test_claude_wrapper_refuses_without_grok_pass(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            grok_report = tmp / "grok_report.json"
            grok_report.write_text(
                json.dumps({"schema_id": "GrokVerificationReport.v1", "verdict": "NOT_RUN"})
            )
            evidence = tmp / "evidence_bundle.json"
            evidence.write_text(json.dumps({"schema_id": "EvidenceBundle.v1"}))
            out = tmp / "claude_packet.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "tools/headless/claude_final_ratify.py",
                    "--candidate",
                    "0" * 40,
                    "--book",
                    str(BOOK),
                    "--grok-report",
                    str(grok_report),
                    "--evidence",
                    str(evidence),
                    "--out",
                    str(out),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            packet = json.loads(out.read_text())
            self.assertEqual(packet["schema_id"], "FinalRatificationPacket.v1")
            self.assertEqual(packet["verdict"], "NOT_RUN")
            self.assertEqual(packet["reason"], "GROK_NOT_PASS")
            self.assertEqual(packet["m2_status"], "DISABLED")
            self.assertEqual(packet["packet_digest"], packet_digest(out))

    def test_goal_handoff_preserves_state_ceiling_and_digest_fields(self):
        sys.path.insert(0, str(REPO / "tools/headless"))
        from headless_common import write_json

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            evidence = tmp / "evidence_bundle.json"
            grok = tmp / "grok.json"
            claude = tmp / "claude.json"
            out = tmp / "handoff.json"
            write_json(evidence, {"schema_id": "EvidenceBundle.v1", "not_run": ["runsc_missing"]})
            write_json(grok, {"schema_id": "GrokVerificationReport.v1", "verdict": "NOT_RUN"})
            write_json(claude, {"schema_id": "FinalRatificationPacket.v1", "verdict": "NOT_RUN"})

            result = subprocess.run(
                [
                    sys.executable,
                    "tools/goal_handoff.py",
                    "--book",
                    str(BOOK),
                    "--evidence",
                    str(evidence),
                    "--grok-report",
                    str(grok),
                    "--claude-packet",
                    str(claude),
                    "--out",
                    str(out),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            handoff = json.loads(out.read_text())
            self.assertEqual(handoff["schema_id"], "GoalRunHandoff.v1")
            self.assertEqual(handoff["status"], "BLOCKED_NOT_RUN")
            self.assertEqual(handoff["m2_status"], "DISABLED")
            self.assertEqual(handoff["forbidden_claims_present"], [])
            self.assertEqual(handoff["artifacts"]["evidence_bundle_digest"], sha256_path(evidence))
            self.assertEqual(handoff["artifacts"]["grok_report_digest"], sha256_path(grok))
            self.assertEqual(handoff["artifacts"]["claude_packet_digest"], sha256_path(claude))


if __name__ == "__main__":
    unittest.main()
