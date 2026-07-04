from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_p3_first_external_audit_20260704"
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
