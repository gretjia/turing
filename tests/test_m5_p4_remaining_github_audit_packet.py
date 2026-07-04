from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_p4_m1_m2_closure_20260704"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m5_p4_remaining_packet_is_self_contained_and_digest_bound() -> None:
    packet_json = PACKET / "PACKET.json"
    prompt = PACKET / "AUDITOR_PROMPT_TEMPLATE.md"
    manifest = PACKET / "PACKET_MANIFEST.sha256"
    source_map = PACKET / "SOURCE_MAP.json"
    repo_artifacts = PACKET / "REPO_ARTIFACTS.json"
    m1_check = PACKET / "packet_checks/run_m1_g_recheck.sh"
    m2_check = PACKET / "packet_checks/run_m2_tc5_boundary_check.sh"

    for path in [packet_json, prompt, manifest, source_map, repo_artifacts, m1_check, m2_check]:
        assert path.exists(), path

    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "turingos.m5.p4.github_module_closure_packet.v1"
    assert packet["packet_kind"] == "M5.P4_MODULE_CLOSURE_GITHUB_PACKET"
    assert packet["audit_surface"] == "github_only"
    assert packet["target_branch"] == "goal/mini-swe-bench-grok-worker"
    assert packet["targets"] == ["M1.G", "M2.TC5", "M2.G"]
    assert packet["status_ceiling"] == "ADDRESSED"
    assert packet["closure_certificate_schema_id"] == "turingos.closure_certificate.v1"
    assert packet["m2_tc10_external_action_required"] is True
    assert packet["auditor_must_not_use"] == [
        "implementation chat",
        "local plan directory",
        "agent memory summaries",
        "uncommitted local files",
    ]
    assert packet["packet_local_checks"] == {
        "M1.G": "evidence/verification/m5_p4_m1_m2_closure_20260704/packet_checks/run_m1_g_recheck.sh",
        "M2.TC5/M2.G": "evidence/verification/m5_p4_m1_m2_closure_20260704/packet_checks/run_m2_tc5_boundary_check.sh",
    }

    source_entries = json.loads(source_map.read_text(encoding="utf-8"))
    source_paths = {entry["github_path"] for entry in source_entries}
    required_source_paths = {
        "evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1G_ARTIFACT_ROLLUP.json",
        "evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1G_GATE_VERDICT.json",
        "evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M2_TC5_PACKET_DESCRIPTOR.json",
        "evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M2G_GATE_VERDICT.json",
        "evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M2G_ARTIFACT_ROLLUP.json",
        "evidence/verification/m5_p4_m1_m2_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md",
    }
    assert required_source_paths.issubset(source_paths)
    assert len(source_entries) >= 30
    for entry in source_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    repo_entries = json.loads(repo_artifacts.read_text(encoding="utf-8"))
    repo_paths = {entry["github_path"] for entry in repo_entries}
    required_repo_paths = {
        "evidence/theory/turing_completeness_witness_20260703/packet/M2_TC5_PACKET.json",
        "evidence/theory/turing_completeness_witness_20260703/packet/PACKET_MANIFEST.sha256",
        "evidence/theory/turing_completeness_witness_20260703/verdicts/TC-10.json",
        "tools/theory/audit_tc4_witness.py",
        "tools/theory/build_tc5_packet.py",
        "tools/bench/audit_micro_tape_decision_dag.py",
        "tools/ci/run_m1a_gates.sh",
    }
    assert required_repo_paths.issubset(repo_paths)
    for entry in repo_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = PACKET / rel
        assert path.exists(), path
        assert sha256(path) == digest, path

    subprocess.run([str(m1_check)], cwd=ROOT, check=True)
    subprocess.run([str(m2_check)], cwd=ROOT, check=True)

    prompt_text = prompt.read_text(encoding="utf-8")
    assert "Do not use implementation chat" in prompt_text
    assert "M1.G" in prompt_text
    assert "M2.TC5" in prompt_text
    assert "TC-10" in prompt_text
    assert "ClosureCertificate.v1" in prompt_text
