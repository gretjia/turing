from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_p3_first_external_audit_20260704"
PASS_CERT = ROOT / (
    "evidence/verification/"
    "m5_p3_first_external_audit_20260704_external_pass/"
    "M5_P3_GROK_PASS_CERTIFICATE.json"
)
BUILD_PACKET = ROOT / "tools/release/build_packet.sh"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m5_p3_first_audit_packet_is_self_contained_and_manifest_bound(tmp_path: Path) -> None:
    assert PACKET.exists()

    manifest_path = PACKET / "PACKET_MANIFEST.json"
    digest_manifest = PACKET / "MANIFEST.sha256"
    reexecution = PACKET / "REEXECUTION.md"
    runbook = PACKET / "AUDITOR_RUNBOOK.md"

    for path in [manifest_path, digest_manifest, reexecution, runbook, PACKET / "CLAIM_BOUNDARY.json"]:
        assert path.exists(), path

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_id"] == "turingos.release_packet.v1"
    assert manifest["gate_id"] == "M5.P3"
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["repo_sha"])
    assert manifest["packet_sha256"].startswith("sha256:")

    required = set(manifest["required_artifacts"])
    assert {
        "AUDITOR_RUNBOOK.md",
        "REEXECUTION.md",
        "CLAIM_BOUNDARY.json",
        "evidence/official_harness_qualification.json",
        "evidence/official_harness_qualification_audit.json",
        "evidence/EXTERNAL_AUDITOR_PROMPT.md",
        "evidence/phase_f_20_repaired_run/evaluation_results.json",
        "evidence/phase_f_20_repaired_run/harness_logs_raw.tar.gz",
    }.issubset(required)

    for line in digest_manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = PACKET / rel
        assert path.exists(), path
        assert sha256(path) == digest, path

    validate_proc = subprocess.run(
        [str(BUILD_PACKET), "--validate", str(PACKET)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert validate_proc.returncode == 0, validate_proc.stderr + validate_proc.stdout

    audit_out = tmp_path / "official_harness_qualification_audit.json"
    audit_proc = subprocess.run(
        [
            "python3",
            "tools/bench/audit_official_harness_qualification.py",
            "--root",
            str(PACKET / "evidence"),
            "--out",
            str(audit_out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert audit_proc.returncode == 0, audit_proc.stderr + audit_proc.stdout
    assert json.loads(audit_out.read_text(encoding="utf-8"))["status"] == "PASS"

    reexecution_text = reexecution.read_text(encoding="utf-8")
    assert "digest-depth" in reexecution_text
    assert "full 20-task replay" in reexecution_text
    assert "Compute your verdict before opening" in reexecution_text
    assert "EXPECTED_VERDICT" in reexecution_text

    runbook_text = runbook.read_text(encoding="utf-8")
    assert "fresh clone" in runbook_text
    assert "no shared conversation state" in runbook_text
    assert "own credentials" in runbook_text
    assert "turingos.closure_certificate.v1" in runbook_text
    assert "This packet does not grant SHIPPED, RELEASED, RATIFIED, M2 enablement, or release eligibility" in runbook_text


def test_m5_p3_external_pass_certificate_is_narrow_and_custody_separated() -> None:
    assert PASS_CERT.exists()
    cert = json.loads(PASS_CERT.read_text(encoding="utf-8"))

    assert cert["schema_id"] == "turingos.closure_certificate.v1"
    assert cert["verdict"] == "PASS"
    assert cert["subject"]["gate_id"] == "M5.P3"
    assert cert["subject"]["repo_url"] == "https://github.com/gretjia/turing"
    assert cert["subject"]["branch"] == "goal/mini-swe-bench-grok-worker"
    assert cert["subject"]["commit_sha"] == "5383e6919590d84fafc46b07e52af1c282dfdc75"
    assert cert["subject"]["packet_root"] == "evidence/verification/m5_p3_first_external_audit_20260704"
    assert (
        cert["subject"]["packet_sha256"]
        == "sha256:6442d1e1773b3f4385e75767c22dfff6469984dbf0ceff2a90f7c56a99b0618c"
    )
    assert cert["subject"]["packet_repo_sha_pin"] == "84a4c5319b0e46917d2333df6033781d3939a23d"

    assert cert["verifier"]["kind"] == "external_cross_family_model"
    assert cert["verifier"]["identity"] == "grok-cursor-external-auditor"
    assert all(cert["verifier"]["custody"].values())

    semantics = cert["status_semantics"]
    assert semantics["certified_closure_level"] == "EXTERNALLY_VERIFIED"
    assert semantics["certified_for_gate"] == "M5.P3"
    assert semantics["implementer_ceiling_was"] == "ADDRESSED"
    assert {
        "SHIPPED",
        "RELEASED",
        "RATIFIED",
        "M2 enablement",
        "release eligibility",
        "OG-10/genesis signature",
        "constitution-byte change",
        "full SWE-bench score claim",
        "leaderboard equivalence claim",
    }.issubset(set(semantics["does_not_grant"]))

    verification = cert["verification"]
    assert verification["digest_manifest_result"] == "PASS"
    assert verification["gate_predicate_result"] == "PASS"
    assert verification["full_docker_replay"] == "NOT_RUN"
    assert verification["audit_script_output"]["phase_f_resolved_count"] == 20
    assert verification["expected_verdict_comparison"]["computed_before_historical_prompt"] is True
    assert verification["expected_verdict_comparison"]["divergence"] is False
    assert all(command["exit_code"] == 0 for command in verification["commands_run"])
    command_text = "\n".join(command["command"] for command in verification["commands_run"])
    assert "sha256sum -c MANIFEST.sha256" in command_text
    assert "build_packet.sh --validate" in command_text
    assert "audit_official_harness_qualification.py" in command_text

    assert "owner commissioned cross-family audit" in cert["findings"]["tier_observation"]
    assert "M5.P4" not in cert["subject"]
    assert "FCE.RUN" not in cert["status_semantics"]["does_not_grant"]
