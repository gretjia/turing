from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_g_module_gate_20260704"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m5_g_github_packet_is_self_contained_and_digest_bound() -> None:
    packet_json = PACKET / "PACKET.json"
    prompt = PACKET / "AUDITOR_PROMPT_TEMPLATE.md"
    manifest = PACKET / "PACKET_MANIFEST.sha256"
    source_map = PACKET / "SOURCE_MAP.json"
    check = PACKET / "packet_checks/run_m5_g_rollup_check.sh"

    for path in [packet_json, prompt, manifest, source_map, check]:
        assert path.exists(), path

    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "turingos.m5.g.github_module_gate_packet.v1"
    assert packet["packet_kind"] == "M5.G_MODULE_GATE_GITHUB_PACKET"
    assert packet["audit_surface"] == "github_only"
    assert packet["target_branch"] == "goal/mini-swe-bench-grok-worker"
    assert packet["target_gate"] == "M5.G"
    assert packet["status_ceiling"] == "ADDRESSED"
    assert packet["closure_certificate_schema_id"] == "turingos.closure_certificate.v1"
    assert packet["auditor_must_not_use"] == [
        "implementation chat",
        "local plan directory",
        "agent memory summaries",
        "uncommitted local files",
    ]
    assert packet["packet_local_checks"] == {
        "M5.G": "evidence/verification/m5_g_module_gate_20260704/packet_checks/run_m5_g_rollup_check.sh"
    }
    assert "M5.G" in packet["gate_verdicts"]

    source_entries = json.loads(source_map.read_text(encoding="utf-8"))
    github_paths = {entry["github_path"] for entry in source_entries}
    required_paths = {
        "evidence/verification/m5_g_module_gate_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_ARTIFACT_ROLLUP.json",
        "evidence/verification/m5_g_module_gate_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_GATE_VERDICT.json",
        "evidence/verification/m5_g_module_gate_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M5G_EXTERNAL_HANDOFF_PACKET.json",
        "evidence/verification/m5_g_module_gate_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m5_verification/tests/test_m5_g_rollup.sh",
        "evidence/verification/m5_g_module_gate_20260704/repo_artifacts/evidence/verification/m5_p3_first_external_audit_20260704_external_pass/M5_P3_GROK_PASS_CERTIFICATE.json",
        "evidence/verification/m5_g_module_gate_20260704/repo_artifacts/evidence/verification/m5_p4_module_closure_20260704_r2_external_pass/M5_P4_GROK_PASS_CERTIFICATE.json",
    }
    assert required_paths.issubset(github_paths)

    assert len(source_entries) >= 50
    for entry in source_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = PACKET / rel
        assert path.exists(), path
        assert sha256(path) == digest, path

    subprocess.run([str(check)], cwd=ROOT, check=True)

    prompt_text = prompt.read_text(encoding="utf-8")
    assert "Do not use implementation chat" in prompt_text
    assert "M5.G" in prompt_text
    assert "ClosureCertificate.v1" in prompt_text
    assert "M5.G is not externally verified by this packet" in prompt_text
